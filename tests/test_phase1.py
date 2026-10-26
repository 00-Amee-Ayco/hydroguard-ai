"""Phase 1 acceptance checks against actual TestClient runs and JSONL files."""
import json
from datetime import datetime
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from hydroguard.api import app
from hydroguard.data.sample import source_registry, assessment_bases
from hydroguard.evidence.assessment import context_fingerprint
from hydroguard.evidence.gate import evaluate_finding
from hydroguard.services.investigation import RunRequest, RunResponse

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    "water": ("Insufficient", ("dry-season water balance", "existing water users")),
    "air": ("Weak", ("receptor inventory",)),
    "land": ("Weak", ("slope stability assessment",)),
}


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("SAMPLE_MODE", "true")
    monkeypatch.setenv("HYDROGUARD_LOG_DIR", str(tmp_path))
    with TestClient(app) as client:
        yield client


def example(name):
    path = ROOT / "input_examples" / f"{name}.json"
    assert path.is_file()
    body = json.loads(path.read_text())
    RunRequest.model_validate(body)
    return body


@pytest.mark.parametrize("name", EXPECTED)
def test_examples_have_authentic_traces_and_resolved_records(client, tmp_path, capsys, name):
    response = client.post("/run", json=example(name))
    assert response.status_code == 200
    result = RunResponse.model_validate(response.json())
    UUID(result.run_id)
    assert result.status == "completed" and result.gate.passed
    assert result.finding.claim_type == "evidence_gap"
    assert (result.finding.strength.value, result.finding.gaps) == EXPECTED[name]
    sources = {source.source_id: source for source in result.audit.sources}
    bases = {basis.basis_id: basis for basis in result.audit.assessment_bases}
    registry, basis_registry = source_registry(), assessment_bases()
    for source in sources.values():
        assert registry[source.source_id] == source
        assert source.document_id and source.chunk_id and source.page > 0
        assert source.provenance == "synthetic"
    assert set(result.audit.claim.citation_ids) <= sources.keys()
    for record in result.audit.history:
        assert set(record.finding.citation_ids) <= sources.keys()
        for basis_id in record.finding.assessment_basis_ids:
            basis = bases[basis_id]
            assert basis == basis_registry[basis_id]
            assert set(basis.citation_ids) <= sources.keys()
            assert basis.domain == result.audit.claim.domain
        assert record.critic.finding_id == record.finding.finding_id
        assert record.critic.revision == record.finding.revision
        assert record.critic.finding_fingerprint == record.finding.fingerprint()
        assert record.critic.evidence_fingerprint == context_fingerprint(sources, bases, result.audit.claim)
        assert record.critic.response_origin == "offline_rule_based"
        assert record.critic.live_inference is False
        assert evaluate_finding(record.finding, record.critic, sources, bases, result.audit.claim) == record.gate
    raw = (tmp_path / f"{result.run_id}.jsonl").read_text()
    assert raw == capsys.readouterr().out
    events = [json.loads(line) for line in raw.splitlines()]
    assert len(events) == 8
    assert all(event["run_id"] == result.run_id and event["mode"] == "offline_rule_based" for event in events)
    assert [event["sequence"] for event in events] == list(range(1, 9))
    times = [datetime.fromisoformat(event["timestamp"]) for event in events]
    assert times == sorted(times)
    retrieval = next(event for event in events if event["event"] == "lexical_retrieval")
    assert set(retrieval["source_ids"]) == set(result.finding.citation_ids)
    critique = next(event for event in events if event["event"] == "offline_policy_critique")
    assert critique["decision"] == result.critic.decision
    assert set(critique["source_ids"]) == sources.keys()
    gate = next(event for event in events if event["event"] == "validate_finding")
    assert gate["passed"] == result.gate.passed
    assert events[-1]["status"] == result.status
    assert all(event["retry"] == 0 for event in events)
    assert [event["handoff"] for event in events if "handoff" in event] == [
        "Evidence Investigator", "Evidence Critic", "Deterministic Evidence Gate", "Community Action Planner"]
    assert not any("model_identity" in event or "World Model" in event["agent"] for event in events)


def test_examples_are_meaningfully_input_dependent(client):
    results = [client.post("/run", json=example(name)).json() for name in EXPECTED]
    assert len({tuple(result["finding"]["gaps"]) for result in results}) == 3
    assert len({tuple(result["finding"]["citation_ids"]) for result in results}) == 3
    assert len({tuple(result["finding"]["assessment_basis_ids"]) for result in results}) == 3
    assert len({result["community_question"] for result in results}) == 3
    for result in results:
        assert all(gap in result["community_question"] for gap in result["finding"]["gaps"])


@pytest.mark.parametrize("name", EXPECTED)
def test_whitespace_is_normalized_only_for_display(client, name):
    body = example(name)
    original = body["project_claim"]["text"]
    body["project_claim"]["text"] = " \t" + original.replace(" ", " \n\t ") + " \n"
    result = client.post("/run", json=body).json()
    assert result["gate"]["passed"]
    assert result["audit"]["claim"]["text"] == body["project_claim"]["text"]
    for value in (result["finding"]["text"], result["community_question"]):
        assert value == " ".join(value.split())
        assert "\\n" not in value and "\\t" not in value
        assert original in value


@pytest.mark.parametrize("name", EXPECTED)
def test_approval_is_not_a_safety_determination(client, name):
    result = RunResponse.model_validate(client.post("/run", json=example(name)).json())
    assert result.finding.claim_type == "evidence_gap"
    assert "does not sufficiently substantiate" in result.finding.text
    assert "No harm or legal determination" in result.finding.limitations[0]
    # Even an approval for this exact altered content cannot authorize a safety claim.
    safety = result.finding.model_copy(update={"text": "The project is safe and legally compliant."})
    approval = result.critic.model_copy(update={"finding_fingerprint": safety.fingerprint()})
    sources = {source.source_id: source for source in result.audit.sources}
    bases = {basis.basis_id: basis for basis in result.audit.assessment_bases}
    assert not evaluate_finding(safety, approval, sources, bases, result.audit.claim).passed
