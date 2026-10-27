"""Dry-run first; --apply uploads and registers only the prepared synthetic snapshot."""
import argparse
import json
import re
from pathlib import Path
from uuid import uuid4
import httpx
from scripts.zetaris_smoke import Config
from hydroguard.ingestion.pipeline import load_passages


def plan(root: Path):
    manifest=json.loads((root/"manifest.json").read_text())
    if not re.fullmatch(r"HYDROGUARD\.riverside_project_[0-9a-f]{16}", manifest["table"]):
        raise ValueError("Invalid case-scoped table name")
    if not re.fullmatch(r"riverside_project_[0-9a-f]{16}\.json", manifest["filename"]):
        raise ValueError("Invalid snapshot filename")
    if manifest["path"] != "dffs://" + manifest["filename"]:
        raise ValueError("Snapshot path differs from verified dffs mapping")
    table=manifest["table"].split(".")[1]
    sql=(f'CREATE LIGHTNING FILESTORE TABLE {table} FROM HYDROGUARD FORMAT JSON '
         f'OPTIONS (PATH "{manifest["path"]}", inferSchema "true", multiLine "true")')
    return manifest,sql


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",type=Path,default=Path("data/cases/riverside"))
    parser.add_argument("--env-file",type=Path,default=Path(".env.local"))
    parser.add_argument("--apply",action="store_true")
    args=parser.parse_args()
    manifest,sql=plan(args.root)
    print(json.dumps({"dry_run":not args.apply,"table":manifest["table"],"path":manifest["path"],
                      "synthetic_project_passages":manifest["passages"],"registration_sql":sql},indent=2))
    if not args.apply:return 0
    config=Config.load(args.env_file,timeout=30)
    payload=(args.root/"processed"/manifest["filename"]).read_bytes()
    import hashlib
    if hashlib.sha256(payload).hexdigest()!=manifest["sha256"]:raise RuntimeError("Snapshot checksum mismatch")
    expected=load_passages(args.root/"processed"/"passages.jsonl")
    with httpx.Client(timeout=30,follow_redirects=False) as client:
        def headers():return {"Authorization":"Bearer "+config.api_key,"X-Org-ID":config.org_id,"X-Request-ID":str(uuid4())}
        def checked(response,label):
            print(json.dumps({"operation":label,"http_status":response.status_code}))
            if response.status_code!=200:
                (args.root/"registration_failure.json").write_text(json.dumps({"operation":label,"status":response.status_code,"body":response.json()},indent=2))
                raise RuntimeError(f"{label}: HTTP {response.status_code}; body saved privately")
            return response.json()
        def query(statement):
            return checked(client.post(config.base_url+"/sql-editor/sqls/run",headers=headers(),
                json={"queryId":str(uuid4()),"sql":statement,"source":"SqlEditor","limit":20}),"SQL").get("data")
        files=checked(client.get(config.base_url+"/ndp-files/list",headers=headers(),params={"path":"/file-store"}),"file listing")
        if not any(item.get("fileName")==manifest["filename"] for item in files):
            result=checked(client.post(config.base_url+"/ndp-files/save",headers=headers(),data={"path":"/file-store"},
                files={"files":(manifest["filename"],payload,"application/x-ndjson")}),"upload")
            if not any(item.get("SaveSuccess",{}).get("fileName")==manifest["filename"] for item in result.get("results",[])):
                raise RuntimeError("Upload did not confirm SaveSuccess")
        tables=query("SHOW LIGHTNING TABLES HYDROGUARD")
        name=manifest["table"].split(".")[1]
        existing=next((row for row in tables if row[0]==name),None)
        if existing and existing[2]!=manifest["path"]:raise RuntimeError("Existing table has a different path; refusing reuse")
        if not existing:query(sql)
        fields=("chunk_id","document_id","page","text","source_type","case_id","is_synthetic")
        rows=query(f"SELECT {', '.join(fields)} FROM {manifest['table']} ORDER BY chunk_id LIMIT 20")
        if not isinstance(rows,list) or len(rows)!=len(expected):raise RuntimeError("Registered row count mismatch")
        for row in rows:
            record=dict(zip(fields,row))
            local=expected[record["chunk_id"]]
            if any(record[k]!=local[k] for k in ("chunk_id","document_id","text","source_type","case_id")):
                raise RuntimeError("Registered passage or provenance mismatch")
            if str(record["page"])!=str(local["page"]) or str(record["is_synthetic"]).lower()!='true':
                raise RuntimeError("Registered page or synthetic marker mismatch")
    result={"registered":True,"table":manifest["table"],"rows_verified":len(rows),"source_ids":list(expected)}
    (args.root/"registration_result.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))
    return 0


if __name__=="__main__":
    try:raise SystemExit(main())
    except (httpx.HTTPError,RuntimeError,ValueError,KeyError) as error:
        print(json.dumps({"registered":False,"error_type":type(error).__name__,"details":str(error) if isinstance(error,RuntimeError) else "omitted"}))
        raise SystemExit(1)
