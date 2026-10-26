import json
import pytest
from fastapi.testclient import TestClient
from hydroguard.api import app
from hydroguard.data.sample import project_claim
from hydroguard.services.audit import run_sample_audit
from hydroguard.services.investigation import RunRequest, InvestigationService
from hydroguard.services.trace import RunTrace


def request():
    claim = project_claim()
    return RunRequest(project_claim={k: getattr(claim, k) for k in ("claim_id", "project_name", "text")},
                      domain="Water", case_context={"community_notes": "SECRET resident and token=private"},
                      evidence_references=["sample-project-1"])


@pytest.fixture(autouse=True)
def offline(monkeypatch, tmp_path):
    monkeypatch.setenv("SAMPLE_MODE", "true")
    monkeypatch.setenv("HYDROGUARD_LOG_DIR", str(tmp_path))


def test_per_run_jsonl_matches_stdout_and_actual_result(tmp_path, capsys):
    result = InvestigationService().run(request())
    lines = capsys.readouterr().out
    assert lines == (tmp_path / f"{result.run_id}.jsonl").read_text()
    events = [json.loads(line) for line in lines.splitlines()]
    assert all(e["run_id"] == result.run_id for e in events)
    assert [e["sequence"] for e in events] == list(range(1, len(events) + 1))
    assert {"Case Planner", "Evidence Investigator", "Evidence Critic", "Deterministic Evidence Gate"} <= {e["agent"] for e in events}
    critique = next(e for e in events if e["event"] == "offline_policy_critique")
    gate = next(e for e in events if e["event"] == "validate_finding")
    assert critique["decision"] == result.critic.decision
    assert gate["passed"] == result.gate.passed
    assert set(critique["source_ids"]) == {s.source_id for s in result.citations}
    assert events[-1]["status"] == result.status
    assert "SECRET" not in lines and "private" not in lines
    assert "model_identity" not in lines and "Zetaris" not in lines
    other = InvestigationService().run(request())
    assert other.run_id != result.run_id


def test_exception_trace_does_not_invent_later_events(monkeypatch, capsys):
    import hydroguard.services.audit as audit
    def fail(*args):
        raise ValueError("secret token and private community")
    monkeypatch.setattr(audit, "retrieve", fail)
    with pytest.raises(ValueError):
        InvestigationService().run(request())
    output = capsys.readouterr().out
    events = [json.loads(line) for line in output.splitlines()]
    assert events[-1]["event"] == "run_failed"
    assert not any(e["event"] in ("offline_policy_critique", "validate_finding", "lexical_retrieval") for e in events)
    assert "secret" not in output and "private" not in output


def test_revision_trace_is_real_not_canned(capsys):
    trace = RunTrace()
    first = run_sample_audit().history[-1].finding
    preliminary = first.model_copy(update={"claim_type": "definitive_harm", "text": "The project causes harm."})
    result = run_sample_audit(preliminary=preliminary, trace=trace)
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    gates = [e for e in events if e["event"] == "validate_finding"]
    assert [e["passed"] for e in gates] == [r.gate.passed for r in result.history] == [False, True]
    assert any(e["decision"] == "retry" for e in events if "decision" in e)
    assert max(e["retry"] for e in events) == 1


def test_invalid_payload_never_echoes_secrets(capsys):
    response = TestClient(app).post("/run", json={"domain": "SECRET token"})
    assert response.status_code == 422
    assert "SECRET" not in response.text
    assert "SECRET" not in capsys.readouterr().out


def test_unknown_source_identifiers_are_redacted(capsys):
    trace = RunTrace()
    trace.emit("Evidence Investigator", "lexical_retrieval", source_ids=["SECRET-personal-source"])
    line = capsys.readouterr().out
    assert "SECRET" not in line
    assert json.loads(line)["source_ids"] == ["[redacted]"]


def test_extra_field_names_do_not_leak_private_values():
    response = TestClient(app).post("/run", json={"SECRET-private-key": "private credential"})
    assert response.status_code == 422
    assert "SECRET" not in response.text
    assert "private credential" not in response.text


def test_live_unavailable_trace_does_not_claim_offline_execution(monkeypatch, capsys):
    from hydroguard.services.audit import LiveModeUnavailable
    monkeypatch.setenv("SAMPLE_MODE", "false")
    with pytest.raises(LiveModeUnavailable):
        InvestigationService().run(request())
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert all(event["mode"] == "live_unavailable" for event in events)
    assert [event["event"] for event in events] == ["run_started", "run_failed"]
