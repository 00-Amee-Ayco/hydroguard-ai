"""Explicit dry-run plan or real read-only retrieval; never auto-registers/uploads."""
import argparse
import json
from pathlib import Path
from hydroguard.ingestion.pipeline import load_passages, retrieve_passages
from hydroguard.ingestion.zetaris import registration_plan, query_registered_passage
from scripts.zetaris_smoke import Config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--passages", type=Path, default=Path("data/processed/knowledge/passages.jsonl"))
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan-s3-uri")
    mode.add_argument("--query-table")
    parser.add_argument("--env-file", type=Path, default=Path(".env.local"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/knowledge/zetaris_result.json"))
    args = parser.parse_args()
    if args.plan_s3_uri:
        print(json.dumps(registration_plan(args.passages, args.plan_s3_uri), indent=2))
        return 0
    records = load_passages(args.passages)
    hits = retrieve_passages(records, "water baseline groundwater surface water", limit=1)
    if not hits:
        raise SystemExit("No local Water passage available for verification; no query sent")
    try:
        result = query_registered_passage(Config.load(args.env_file), args.query_table, records, hits[0]["chunk_id"])
    except Exception:
        raise SystemExit("Live passage verification failed. No fallback or success claimed; check table registration, credentials, permissions, connectivity and provenance.") from None
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"verified": True, "chunk_id": result["chunk_id"], "text_saved_privately": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
