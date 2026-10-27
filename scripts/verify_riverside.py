"""Real FastAPI -> Investigator -> Zetaris Riverside case check; no sample fallback."""
import json
import os
from pathlib import Path
from fastapi.testclient import TestClient
from hydroguard.api import app
from hydroguard.services.investigation import RunResponse
from hydroguard.ingestion.pipeline import load_passages


def main():
    if os.environ.get("SAMPLE_MODE", "true").lower() != "false":
        raise SystemExit("Set SAMPLE_MODE=false explicitly")
    root=Path("data/cases/riverside")
    manifest=json.loads((root/"manifest.json").read_text())
    os.environ["ZETARIS_PROJECT_TABLE"]=manifest["table"]
    os.environ["ZETARIS_PROJECT_CASE_ID"]=manifest["case_id"]
    body={"project_claim":{"claim_id":manifest["case_id"],"project_name":manifest["project_name"],"text":manifest["claim"]},
          "domain":"Water","case_context":{"stage":"scoping","community_notes":"Entire project is fictional."},"evidence_references":[]}
    with TestClient(app) as client:
        response=client.post("/run",json=body)
    if response.status_code!=200:
        print(json.dumps({"integration":"FAILED","http_status":response.status_code,"fallback":False}));return 1
    result=RunResponse.model_validate(response.json())
    local=load_passages(root/"processed/passages.jsonl")
    project=[source for source in result.citations if source.kind=="project"]
    regulatory=[source for source in result.citations if source.source_type=="regulatory"]
    if len(project)!=len(local) or not regulatory:
        print(json.dumps({"integration":"FAILED","reason":"missing project or regulatory rows"}));return 1
    for source in project:
        expected=local[source.chunk_id]
        if source.text!=expected["text"] or source.page!=expected["page"] or source.document_id!=expected["document_id"]:
            raise RuntimeError("Project citation mismatch")
        if source.case_id!=manifest["case_id"] or source.is_synthetic is not True:raise RuntimeError("Project scope mismatch")
    if result.gate.passed or result.critic is not None:raise RuntimeError("Unexpected approval without live Critic")
    (root/"live_result.json").write_text(result.model_dump_json(indent=2)+"\n")
    print(json.dumps({"integration":"PASS: retrieval and qualified unresolved finding", "run_id":result.run_id,
        "project_table":manifest["table"],"project_rows":len(project),"regulatory_rows":len(regulatory),
        "source_ids":[s.source_id for s in result.citations],"finding":result.finding.text,
        "gate_passed":result.gate.passed,"status":result.status,"critic_invoked":False},indent=2))
    return 0


if __name__=="__main__":raise SystemExit(main())
