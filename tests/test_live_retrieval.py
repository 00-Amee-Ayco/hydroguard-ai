"""Synthetic transport tests only; genuine integration is run separately by CLI."""
import json
from pathlib import Path
from uuid import UUID
import httpx
import pytest
from fastapi.testclient import TestClient
from hydroguard.api import app
from hydroguard.agents.investigator import EvidenceInvestigator
from hydroguard.data.sample import project_claim
from hydroguard.data.zetaris import (FIELDS, ZetarisEvidenceRetriever, ZetarisRetrievalError,
                                    ZetarisConfigurationError, regulatory_query)
from hydroguard.services.investigation import InvestigationService, RunRequest
from scripts.zetaris_smoke import Config

RECORD = {"chunk_id":"chunk-"+"a"*64, "document_id":"doc-"+"b"*64,
          "title":"Synthetic transport fixture, not a regulation", "page":"197",
          "text":"Synthetic water transport-test passage only.", "source_type":"regulatory",
          "original_filename":"transport-fixture.pdf", "locator":"pdf-page:197",
          "issuing_body_or_author":None,"publication_or_effective_date":None,"original_source_url":None}


@pytest.fixture(autouse=True)
def environment(monkeypatch, tmp_path):
    monkeypatch.setenv("SAMPLE_MODE","false")
    monkeypatch.setenv("HYDROGUARD_LOG_DIR",str(tmp_path))


def adapter(handler, trace=None):
    return ZetarisEvidenceRetriever(Config("https://instance.test/api/v1.0","SECRET","1"),
                                    trace=trace, transport=httpx.MockTransport(handler))


def request():
    body=json.loads(Path("input_examples/water.json").read_text())
    body["evidence_references"]=[]
    return RunRequest.model_validate(body)


def success(req):
    assert req.headers["Authorization"] == "Bearer SECRET"
    UUID(req.headers["X-Request-ID"])
    body=json.loads(req.content)
    UUID(body["queryId"])
    assert "HYDROGUARD.regulatory" in body["sql"] and body["limit"] == 10
    return httpx.Response(200,json={"data":[[RECORD[field] for field in FIELDS]]})


def test_investigator_consumes_live_contract_without_project_inference():
    sources=EvidenceInvestigator(adapter(success)).investigate(project_claim())
    source=sources[RECORD["chunk_id"]]
    assert source.source_id == source.chunk_id == RECORD["chunk_id"]
    assert source.text == RECORD["text"] and source.document_id == RECORD["document_id"]
    assert source.page == 197 and source.locator == "pdf-page:197"
    assert source.source_type == "regulatory" and source.provenance == "government"
    assert source.kind == "basis" and source.evidence_items == ()


def test_service_records_ledger_and_real_query_events(tmp_path, capsys):
    result=InvestigationService(lambda trace: adapter(success,trace)).run(request())
    assert result.citations and result.status == "unresolved"
    assert result.critic is None and not result.gate.passed and result.community_question is None
    assert result.audit.claim.citation_ids == ()
    assert result.audit.history[-1].critic is None
    assert any("project-specific" in gap for gap in result.finding.gaps)
    output=capsys.readouterr().out
    assert "SECRET" not in output and RECORD["text"] not in output
    events=[json.loads(line) for line in (tmp_path/f"{result.run_id}.jsonl").read_text().splitlines()]
    sql=next(event for event in events if event["event"] == "zetaris_sql_completed")
    assert sql["row_count"] == 1 and sql["source_ids"] == [RECORD["chunk_id"]]
    assert sql["http_status"] == 200 and "SELECT" in sql["sql"]
    assert any(event["event"] == "consumed_regulatory_records" for event in events)
    assert not any(event["agent"] == "Evidence Critic" for event in events)


def test_empty_results_remain_unresolved_without_sample_fallback():
    result=InvestigationService(lambda trace: adapter(lambda req:httpx.Response(200,json={"data":[]}),trace)).run(request())
    assert result.citations == () and not result.gate.passed
    assert result.status == "unresolved" and result.critic is None
    assert "No relevant regulatory" in result.finding.gaps[0]


@pytest.mark.parametrize("status", [401,403,500])
def test_http_failures_no_fallback_or_secret_leak(status):
    retriever=adapter(lambda req:httpx.Response(status,text="SECRET raw failure"))
    with pytest.raises(ZetarisRetrievalError) as error:
        retriever.retrieve(project_claim())
    assert f"HTTP {status}" in str(error.value) and "SECRET" not in str(error.value)


@pytest.mark.parametrize("error_type", [httpx.ConnectError,httpx.ReadTimeout])
def test_transport_failures_no_fallback(error_type):
    def fail(req):raise error_type("SECRET network details",request=req)
    with pytest.raises(ZetarisRetrievalError) as exc:
        adapter(fail).retrieve(project_claim())
    assert "SECRET" not in str(exc.value)


@pytest.mark.parametrize("field,value", [("chunk_id","invented"),("document_id",None),
                                          ("source_type","project"),("page",None),("text","")])
def test_invalid_citation_records_are_rejected(field,value):
    changed={**RECORD,field:value}
    retriever=adapter(lambda req:httpx.Response(200,json={"data":[[changed[f] for f in FIELDS]]}))
    with pytest.raises(ZetarisRetrievalError):retriever.retrieve(project_claim())


def test_duplicate_citations_fail_closed():
    row=[RECORD[f] for f in FIELDS]
    with pytest.raises(ZetarisRetrievalError,match="Duplicate"):
        adapter(lambda req:httpx.Response(200,json={"data":[row,row]})).retrieve(project_claim())


def test_sql_has_only_allowed_public_terms():
    claim=project_claim(text="water SECRET person O'Brien; DROP TABLE x")
    query=regulatory_query("HYDROGUARD.regulatory",claim)
    assert "SECRET" not in query and "DROP" not in query and "O'Brien" not in query
    assert "LIKE '%water%'" in query
    assert regulatory_query("HYDROGUARD.regulatory",project_claim("Air")) != query
    with pytest.raises(ZetarisConfigurationError):regulatory_query("bad; DROP TABLE x",claim)


def test_api_live_response_preserves_public_request_schema(monkeypatch):
    import hydroguard.api as api
    monkeypatch.setattr(api,"service",InvestigationService(lambda trace:adapter(success,trace)))
    response=TestClient(app).post("/run",json=request().model_dump(mode="json"))
    assert response.status_code == 200
    assert response.json()["citations"][0]["source_id"] == RECORD["chunk_id"]
    assert response.json()["critic"] is None and response.json()["gate"]["passed"] is False


def test_api_live_failure_is_502(monkeypatch):
    import hydroguard.api as api
    monkeypatch.setattr(api,"service",InvestigationService(lambda trace:adapter(lambda req:httpx.Response(401),trace)))
    response=TestClient(app).post("/run",json=request().model_dump(mode="json"))
    assert response.status_code == 502 and "no sample fallback" in response.text


def test_configured_table_is_loaded_from_selected_env_file(tmp_path, monkeypatch):
    path=tmp_path/".env.local"
    path.write_text("ZETARIS_REST_URL=https://test/api/v1.0\nZETARIS_API_KEY=SECRET\nZETARIS_ORG_ID=1\nZETARIS_REGULATORY_TABLE=APP.references\n")
    monkeypatch.setenv("ZETARIS_ENV_FILE",str(path))
    monkeypatch.delenv("ZETARIS_REGULATORY_TABLE",raising=False)
    assert ZetarisEvidenceRetriever.from_environment().table == "APP.references"
