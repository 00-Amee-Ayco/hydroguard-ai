"""Run with .venv/bin/python -m scripts.ingest_knowledge. Local export only."""
import argparse
import json
from pathlib import Path
from hydroguard.ingestion.pipeline import ingest, load_passages, retrieve_passages


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/knowledge"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/knowledge"))
    parser.add_argument("--catalog", type=Path)
    parser.add_argument("--max-chars", type=int, default=1200)
    parser.add_argument("--query", default="water baseline groundwater surface water")
    args = parser.parse_args()
    result = ingest(args.input, args.output, args.catalog, args.max_chars)
    passages = load_passages(args.output / "passages.jsonl")
    hits = retrieve_passages(passages, args.query)
    # Full text stays in ignored private output files, not terminal logs.
    (args.output / "water_preview.json").write_text(json.dumps({
        "mode": "local_retrieval_preview_not_zetaris", "query": args.query,
        "passages": hits, "limitations": "Reference retrieval only; no project disclosure or approved impact finding."},
        ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"documents": result["documents"], "passages": result["passages"],
                      "review_flags": sum(len(item.get("review_flags", [])) for item in result["inventory"]),
                      "local_preview_hits": len(hits), "zetaris_registered": False}, indent=2))
    return 1 if any(item["status"] == "failed" for item in result["inventory"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
