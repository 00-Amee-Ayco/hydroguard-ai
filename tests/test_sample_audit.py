import pytest

from hydroguard.data.sample import HARM_FINDING, project_claim, source_registry, assessment_bases
from hydroguard.evidence.models import AuditResult
from hydroguard.services.audit import run_sample_audit


@pytest.fixture(autouse=True)
def sample_mode(monkeypatch):
    monkeypatch.setenv("SAMPLE_MODE", "true")


def test_sample_investigation_returns_question_and_history():
    baseline = run_sample_audit()
    initial = baseline.history[-1].finding.model_copy(update={"text": HARM_FINDING, "claim_type": "definitive_harm"})
    result = run_sample_audit(preliminary=initial)
    first, revised = result.history
    assert first.finding.text == HARM_FINDING
    assert first.critic.decision == "reject"
    assert not first.gate.passed
    assert "dry-season water balance" in revised.finding.text
    assert revised.finding.revision == first.finding.revision + 1
    assert revised.critic.decision == "approve"
    assert revised.gate.passed
    assert result.consultation_question
    assert "dry-season water balance" in result.consultation_question
    assert AuditResult.model_validate_json(result.model_dump_json()) == result


def test_no_credentials_or_live_inference(monkeypatch):
    for key in ("ZETARIS_API_TOKEN", "NIGHTSHIFT_API_KEY", "NEMOTRON_MODEL"):
        monkeypatch.delenv(key, raising=False)
    result = run_sample_audit()
    assert result.mode == "Sample / Synthetic"
    for revision in result.history:
        assert revision.critic.response_origin == "offline_rule_based"
        assert revision.critic.live_inference is False
        assert revision.critic.model_identity == "unverified; no model invoked"


def test_live_mode_fails_clearly(monkeypatch):
    monkeypatch.setenv("SAMPLE_MODE", "false")
    with pytest.raises(RuntimeError, match="Live mode is not implemented"):
        run_sample_audit()


def test_question_is_withheld_if_final_gate_blocks(monkeypatch):
    import hydroguard.services.audit as audit
    from hydroguard.evidence.models import GateResult

    monkeypatch.setattr(audit, "evaluate_finding", lambda finding, *args: GateResult(
        finding_id=finding.finding_id, revision=finding.revision, passed=False, reasons=("Blocked",)))
    assert audit.run_sample_audit().consultation_question is None


@pytest.mark.parametrize("domain,expected", [
    ("Water", ("dry-season water balance", "existing water users")),
    ("Land", ("slope stability assessment",)),
    ("Air", ("receptor inventory",)),
])
def test_distinct_input_dependent_investigations(domain, expected):
    result = run_sample_audit(project_claim(domain))
    finding = result.history[-1].finding
    assert result.history[-1].gate.passed
    assert finding.gaps == expected
    assert domain in finding.text
    assert all(source.domain == domain for source in result.sources)
    assert all(item in result.consultation_question for item in expected)
    ids = {s.source_id for s in result.sources}
    assert set(finding.citation_ids) <= ids
    assert all(set(b.citation_ids) <= ids for b in result.assessment_bases)


def test_changed_evidence_changes_critique_and_finding():
    from hydroguard.ai.sample import sample_critic
    registry = source_registry()
    original = run_sample_audit(project_claim("Land"), registry=registry)
    source = registry["sample-land-project"]
    registry[source.source_id] = source.model_copy(update={
        "text": source.text + " Additional synthetic slope stability assessment is now disclosed.",
        "evidence_items": ("erosion baseline", "slope stability assessment"),
    })
    updated = run_sample_audit(project_claim("Land"), registry=registry)
    final = updated.history[-1]
    assert final.gate.passed
    assert final.finding.gaps == ()
    assert final.finding.claim_type == "evidence_summary"
    assert original.history[-1].finding.text != final.finding.text
    assert "monitored" in updated.consultation_question
    critique = sample_critic(original.history[-1].finding, {s.source_id:s for s in updated.sources},
                             {b.basis_id:b for b in updated.assessment_bases}, updated.claim)
    assert critique.decision == "reject"


def test_changed_query_changes_retrieval():
    relevant = run_sample_audit(project_claim("Air", "dust emissions"))
    unrelated = run_sample_audit(project_claim("Air", "underwater archaeology"))
    assert relevant.history[-1].gate.passed
    assert not unrelated.history[-1].gate.passed
    assert unrelated.consultation_question is None
    assert {s.source_id for s in relevant.sources} != {s.source_id for s in unrelated.sources}


def test_renamed_ids_do_not_select_outputs():
    registry = source_registry()
    renamed = {"renamed-" + k: s.model_copy(update={"source_id": "renamed-" + k}) for k,s in registry.items()}
    bases = {"renamed-" + k: b.model_copy(update={"basis_id": "renamed-" + k,
             "citation_ids": tuple("renamed-" + c for c in b.citation_ids)}) for k,b in assessment_bases().items()}
    original = run_sample_audit(project_claim("Air"))
    result = run_sample_audit(project_claim("Air").model_copy(update={"claim_id": "arbitrary"}), registry=renamed, bases=bases)
    assert result.history[-1].gate.passed
    assert result.history[-1].finding.text == original.history[-1].finding.text
    assert result.consultation_question == original.consultation_question
