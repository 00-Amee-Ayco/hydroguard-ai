import pytest

from hydroguard.ai.sample import sample_critic
from hydroguard.data.sample import HARM_FINDING, assessment_bases, project_claim, source_registry
from hydroguard.evidence.gate import evaluate_finding
from hydroguard.evidence.models import EvidenceStrength
from hydroguard.services.audit import run_sample_audit


@pytest.fixture
def finding(monkeypatch):
    monkeypatch.setenv("SAMPLE_MODE", "true")
    return run_sample_audit().history[-1].finding


def approve(finding, sources=None, bases=None, claim=None):
    return sample_critic(finding, source_registry() if sources is None else sources,
                         assessment_bases() if bases is None else bases,
                         current_claim() if claim is None else claim)


def current_claim():
    return run_sample_audit().claim


def gate(finding, *, critic=None, sources=None, bases=None):
    sources = source_registry() if sources is None else sources
    bases = assessment_bases() if bases is None else bases
    claim = current_claim()
    return evaluate_finding(finding, critic or approve(finding, sources, bases, claim), sources, bases, claim)


@pytest.mark.parametrize("changes,reason", [
    ({"citation_ids": ()}, "Missing finding source citation"),
    ({"citation_ids": ("nonexistent",)}, "Invalid finding citation ID"),
    ({"assessment_basis_ids": ()}, "Missing assessment basis"),
    ({"assessment_basis_ids": ("nonexistent",)}, "Invalid assessment basis"),
    ({"gaps": ()}, "Explicit evidence gaps"),
    ({"limitations": ()}, "Explicit evidence gaps"),
    ({"claim_id": "other"}, "current project claim"),
])
def test_missing_or_invalid_evidence_blocked(finding, changes, reason):
    result = gate(finding.model_copy(update=changes))
    assert not result.passed
    assert any(reason in item for item in result.reasons)


@pytest.mark.parametrize("strength", list(EvidenceStrength))
def test_harm_blocked_even_with_critic_approval(finding, strength):
    harm = finding.model_copy(update={"text": HARM_FINDING, "claim_type": "definitive_harm", "strength": strength})
    approval = approve(harm).model_copy(update={"decision": "approve"})
    result = gate(harm, critic=approval)
    assert not result.passed
    assert any("Definitive harm" in item for item in result.reasons)


def test_harm_mislabeled_as_gap_blocked(finding):
    harm = finding.model_copy(update={"text": HARM_FINDING})
    approval = approve(harm).model_copy(update={"decision": "approve"})
    assert not gate(harm, critic=approval).passed


@pytest.mark.parametrize("changes", [{"revision": 2}, {"finding_id": "other"}, {"finding_fingerprint": "wrong"}])
def test_stale_or_mismatched_critic_blocked(finding, changes):
    approval = approve(finding).model_copy(update=changes)
    result = gate(finding, critic=approval)
    assert not result.passed
    assert "Stale or mismatched Critic approval." in result.reasons


def test_same_revision_content_change_invalidates_approval(finding):
    approval = approve(finding)
    changed = finding.model_copy(update={"limitations": ("Changed review scope.",)})
    assert not gate(changed, critic=approval).passed


@pytest.mark.parametrize("decision", ["reject", "narrow", "reinvestigate"])
def test_nonapproval_blocked(finding, decision):
    assert not gate(finding, critic=approve(finding).model_copy(update={"decision": decision})).passed


def test_missing_critic_blocked(finding):
    assert not evaluate_finding(finding, None, source_registry(), assessment_bases(), current_claim()).passed


def test_invalid_basis_citation_blocked(finding):
    bases = assessment_bases()
    bases["dry-season-review"] = bases["dry-season-review"].model_copy(update={"citation_ids": ("missing",)})
    assert not gate(finding, bases=bases).passed


def test_deleted_registry_record_blocked(finding):
    registry = source_registry()
    del registry["sample-project-1"]
    assert not gate(finding, sources=registry).passed


def test_qualified_gap_passes(finding):
    result = gate(finding)
    assert result.passed
    assert result.reasons == ()


@pytest.mark.parametrize("domain", ["Land", "Air", "People"])
def test_other_domains_cannot_reuse_water_approval(finding, domain):
    claim = current_claim().model_copy(update={"domain": domain})
    assert not evaluate_finding(finding, approve(finding), source_registry(), assessment_bases(), claim).passed


def test_noncompliance_blocked_even_with_approval(finding):
    illegal = finding.model_copy(update={"claim_type": "illegality", "text": "The project violates environmental regulations."})
    assert not gate(illegal, critic=approve(illegal).model_copy(update={"decision": "approve"})).passed


def test_changed_source_invalidates_approval(finding):
    approval = approve(finding)
    registry = source_registry()
    registry["sample-project-1"] = registry["sample-project-1"].model_copy(update={"text": "Updated disclosure"})
    result = gate(finding, critic=approval, sources=registry)
    assert not result.passed
    assert "Stale evidence context in Critic approval." in result.reasons


def test_inapplicable_basis_blocked(finding):
    bases = assessment_bases()
    bases["dry-season-review"] = bases["dry-season-review"].model_copy(update={"domain": "Air"})
    assert not gate(finding, bases=bases).passed
