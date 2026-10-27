"""Fictional project fixtures and simulated transports; live proof is a separate CLI."""
import json
from pathlib import Path
import httpx
import pytest
from hydroguard.cases.riverside import prepare, CASE_ID, PROJECT_NAME, CLAIM
from hydroguard.cases.water_case import unresolved_water_finding
from hydroguard.ingestion.pipeline import load_passages
from hydroguard.data.zetaris import ZetarisEvidenceRetriever, CaseScopedRetriever, FIELDS, ZetarisRetrievalError
from hydroguard.evidence.models import ProjectClaim
from hydroguard.services.investigation import InvestigationService, RunRequest
from scripts.zetaris_smoke import Config
from scripts.register_riverside import plan


@pytest.fixture
def fixture_case(tmp_path):
    root=tmp_path/"riverside"
    manifest=prepare(root)
    records=load_passages(root/"processed/passages.jsonl")
    return root,manifest,records


def claim(case_id=CASE_ID):
    return ProjectClaim(claim_id=case_id,project_name=PROJECT_NAME,domain="Water",text=CLAIM,citation_ids=())


def project_adapter(records, trace=None, mutate=None):
    fields=FIELDS+("case_id","is_synthetic")
    def handler(request):
        body=json.loads(request.content)
        assert "source_type = 'project'" in body["sql"]
        assert f"case_id = '{CASE_ID}'" in body["sql"]
        assert "is_synthetic = true" in body["sql"]
        rows=[]
        for record in records.values():
            record={**record,**(mutate or {})}
            rows.append([record[field] for field in fields])
        return httpx.Response(200,json={"data":rows})
    return ZetarisEvidenceRetriever(Config("https://test/api/v1.0","SECRET","1"),
        table="HYDROGUARD.riverside_project_test",project_case_id=CASE_ID,
        trace=trace,transport=httpx.MockTransport(handler))


def test_pdf_ingestion_and_json_array_are_idempotent(fixture_case):
    root,manifest,records=fixture_case
    assert len(records)==2
    assert {r["page"] for r in records.values()}=={1,2}
    assert all(r["source_type"]=="project" and r["is_synthetic"] and r["case_id"]==CASE_ID for r in records.values())
    text=" ".join(r["text"] for r in records.values())
    assert "SYNTHETIC PROJECT DISCLOSURE" in text
    assert "120 cubic metres per day" in text
    assert "0.8 cubic metres per second" in text
    assert "complete dry-season water balance is not provided" in text
    assert "Quantified existing-user abstraction evidence is not provided" in text
    assert prepare(root)==manifest
    array=json.loads((root/"processed"/manifest["filename"]).read_text())
    assert len(array)==2 and {r["chunk_id"] for r in array}==set(records)
    _,sql=plan(root)
    assert 'multiLine "true"' in sql and manifest["path"] in sql


def test_project_adapter_preserves_synthetic_project_provenance(fixture_case):
    _,_,records=fixture_case
    sources=project_adapter(records).retrieve(claim())
    assert set(sources)==set(records)
    assert all(s.kind=="project" and s.provenance=="synthetic" and s.is_synthetic for s in sources.values())
    assert all(s.case_id==CASE_ID and s.text==records[s.chunk_id]["text"] for s in sources.values())


@pytest.mark.parametrize("mutation",[{"case_id":"other-case"},{"is_synthetic":False},{"source_type":"regulatory"}])
def test_mismatched_project_rows_fail_closed(fixture_case, mutation):
    _,_,records=fixture_case
    with pytest.raises(ZetarisRetrievalError):
        project_adapter(records,mutate=mutation).retrieve(claim())


def test_composite_retrieval_does_not_leak_other_case(fixture_case):
    _,_,records=fixture_case
    class Regulatory:
        def retrieve(self,claim):return {}
    merged=CaseScopedRetriever(Regulatory(),project_adapter(records),CASE_ID)
    assert merged.retrieve(claim("other-case"))=={}
    assert len(merged.retrieve(claim()))==2


def test_gap_is_computed_from_returned_disclosure_not_case_id(fixture_case):
    _,_,records=fixture_case
    sources=project_adapter(records).retrieve(claim())
    finding=unresolved_water_finding(claim(),sources)
    assert "does not sufficiently establish" in finding.text
    assert any("dry-season" in gap for gap in finding.gaps)
    assert finding.assessment_basis_ids==()
    modified={key:source.model_copy(update={"text":"Synthetic disclosure has changed and makes no explicit omission declaration."}) for key,source in sources.items()}
    changed=unresolved_water_finding(claim(),modified)
    assert changed.text!=finding.text
    assert not any("explicitly not provided" in gap for gap in changed.gaps)


def test_case_service_retains_gate_and_never_invents_critic(fixture_case, monkeypatch,tmp_path):
    _,_,records=fixture_case
    monkeypatch.setenv("SAMPLE_MODE","false")
    monkeypatch.setenv("HYDROGUARD_LOG_DIR",str(tmp_path/"logs"))
    request=RunRequest(project_claim={"claim_id":CASE_ID,"project_name":PROJECT_NAME,"text":CLAIM},domain="Water",case_context={},evidence_references=[])
    result=InvestigationService(lambda trace:project_adapter(records,trace)).run(request)
    assert result.audit.claim.citation_ids==tuple(records)
    assert result.critic is None and result.gate.passed is False
    assert result.status=="unresolved" and result.community_question is None
    assert result.audit.assessment_bases==()
    assert any("no dry-season legal requirement" in gap.lower() for gap in result.finding.gaps)
    events=[json.loads(line) for line in (tmp_path/"logs"/f"{result.run_id}.jsonl").read_text().splitlines()]
    assert any(e["event"]=="consumed_project_disclosure" and e["row_count"]==2 for e in events)
    assert not any(e["agent"]=="Evidence Critic" for e in events)
