"""Exercise the real shared Investigator service, save private rows, print only IDs."""
import json
import os
from pathlib import Path
from hydroguard.services.investigation import RunRequest, RunResponse
from hydroguard.api import app
from fastapi.testclient import TestClient


def main():
    if os.environ.get("SAMPLE_MODE", "true").lower() != "false":
        raise SystemExit("Set SAMPLE_MODE=false explicitly; no sample fallback is permitted")
    # Reuse the public Water request, explicitly omit synthetic reference IDs.
    payload = json.loads(Path("input_examples/water.json").read_text())
    payload["evidence_references"] = []
    request = RunRequest.model_validate(payload)
    try:
        with TestClient(app) as client:
            response = client.post("/run", json=request.model_dump(mode="json"))
        if response.status_code != 200:
            print(json.dumps({"retrieval":"FAILED", "http_status":response.status_code, "fallback":False}))
            return 1
        result = RunResponse.model_validate(response.json())
    except Exception as error:
        print(json.dumps({"retrieval":"FAILED", "error_type":type(error).__name__, "details":"omitted; no fallback"}))
        return 1
    output = Path("data/processed/knowledge/live_investigator_result.json")
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(result.model_dump_json(indent=2)+"\n")
    print(json.dumps({"run_id":result.run_id,"retrieval":"PASS" if result.citations else "EMPTY",
                      "rows":len(result.citations),"source_ids":[s.source_id for s in result.citations],
                      "investigation_status":result.status,"gate_passed":result.gate.passed,
                      "critic_invoked":result.critic is not None},indent=2))
    return 0 if result.citations else 1


if __name__ == "__main__":
    raise SystemExit(main())
