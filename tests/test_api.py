import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from hydroguard.api import app


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("SAMPLE_MODE", "true")
    monkeypatch.setenv("HYDROGUARD_LOG_DIR", str(tmp_path))
    return TestClient(app)


def payload(domain="Water"):
    from hydroguard.data.sample import project_claim
    claim = project_claim(domain)
    return {"project_claim": {"claim_id": claim.claim_id, "project_name": claim.project_name, "text": claim.text},
            "domain": domain, "case_context": {"stage": "scoping", "community_notes": "private community detail"},
            "evidence_references": ["sample-project-1" if domain == "Water" else f"sample-{domain.lower()}-project"]}


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["execution_available"] is True
    assert response.json()["sponsor_integrations_verified"] is False


@pytest.mark.parametrize("domain", ["Water", "Land", "Air"])
def test_run_domains(client, domain):
    response = client.post("/run", json=payload(domain))
    assert response.status_code == 200
    body = response.json()
    assert body["gate"]["passed"]
    assert body["status"] == "completed"
    assert body["critic"]["response_origin"] == "offline_rule_based"
    assert "During scoping" in body["community_question"]
    ids = {source["source_id"] for source in body["citations"]}
    assert set(body["finding"]["citation_ids"]) <= ids
    assert body["finding"]["text"] == body["audit"]["history"][-1]["finding"]["text"]


@pytest.mark.parametrize("field,value", [("domain", "Ocean"), ("project_claim", {}),
                                           ("case_context", "bad"), ("evidence_references", "bad")])
def test_invalid_request(client, field, value):
    body = payload()
    body[field] = value
    assert client.post("/run", json=body).status_code == 422


def test_blank_claim(client):
    body = payload()
    body["project_claim"]["text"] = " "
    assert client.post("/run", json=body).status_code == 422


@pytest.mark.parametrize("refs", [["nonexistent"], ["sample-land-project"], ["sample-basis-1"]])
def test_invalid_evidence_reference(client, refs):
    body = payload()
    body["evidence_references"] = refs
    assert client.post("/run", json=body).status_code == 422


def test_live_fails_transparently(client, monkeypatch):
    monkeypatch.setenv("SAMPLE_MODE", "false")
    assert client.get("/health").json()["execution_available"] is False
    assert client.post("/run", json=payload()).status_code == 503


def test_unmatched_claim_is_unresolved(client):
    body = payload()
    body["project_claim"]["text"] = "underwater archaeology"
    response = client.post("/run", json=body)
    assert response.status_code == 200
    assert response.json()["status"] == "unresolved"
    assert response.json()["community_question"] is None


def test_actual_examples_match_computed_results(client):
    for file in Path("input_examples").glob("*.json"):
        actual = client.post("/run", json=json.loads(file.read_text())).json()
        recorded = json.loads((Path("output_examples") / file.name).read_text())
        actual.pop("run_id")
        recorded.pop("run_id")
        assert actual == recorded
    assert len(list(Path("input_examples").glob("*.json"))) == 3


def test_runtime_does_not_read_recorded_outputs(client, monkeypatch):
    original = Path.open
    def guarded(path, *args, **kwargs):
        if "output_examples" in path.parts:
            raise AssertionError("Runtime attempted to read recorded output")
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "open", guarded)
    assert client.post("/run", json=payload()).json()["gate"]["passed"]


def test_unexpected_failure_is_sanitized(client, monkeypatch):
    import hydroguard.services.audit as audit
    def fail(*args):
        raise ValueError("SECRET community and credential")
    monkeypatch.setattr(audit, "retrieve", fail)
    response = client.post("/run", json=payload())
    assert response.status_code == 500
    assert "SECRET" not in response.text


def test_internal_runtime_error_is_not_reported_as_live_unavailable(client, monkeypatch):
    import hydroguard.services.audit as audit
    def fail(*args):
        raise RuntimeError("SECRET internal processing failure")
    monkeypatch.setattr(audit, "retrieve", fail)
    response = client.post("/run", json=payload())
    assert response.status_code == 500
    assert "SECRET" not in response.text
    assert "Live execution" not in response.text
