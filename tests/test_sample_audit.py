import pytest

from hydroguard.data.sample import GAP_FINDING, HARM_FINDING
from hydroguard.evidence.models import AuditResult
from hydroguard.services.audit import run_sample_audit


@pytest.fixture(autouse=True)
def sample_mode(monkeypatch):
    monkeypatch.setenv("SAMPLE_MODE", "true")


def test_sample_investigation_returns_question_and_history():
    result = run_sample_audit()
    first, revised = result.history
    assert first.finding.text == HARM_FINDING
    assert first.critic.decision == "reject"
    assert not first.gate.passed
    assert revised.finding.text == GAP_FINDING
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
        assert revision.critic.response_origin == "prerecorded_fixture"
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
