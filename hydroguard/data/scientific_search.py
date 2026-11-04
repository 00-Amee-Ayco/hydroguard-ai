"""Read-only scientific abstract lookup from a separate Zetaris File Store table.

Only fixed, public terms reach SQL. This is NOT project evidence or /run input.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
from uuid import uuid4

import httpx
from dotenv import dotenv_values
from fastapi import APIRouter, HTTPException, Query

from scripts.zetaris_smoke import Config, SmokeError

router = APIRouter()
SCIENTIFIC_FIELDS = ("study_id", "entry_number", "section", "title", "abstract",
                     "operational_utility", "apa_citation", "doi_url", "source_type")
TOPIC_TERMS = {
    "Water": ("water", "groundwater", "river", "drinking", "wastewater", "flood", "hydrology", "mercury"),
    "Land": ("land", "soil", "erosion", "mining", "biodiversity", "habitat"),
    "Air": ("air", "emission", "particulate", "pollution", "noise", "climate"),
    "People": ("health", "community", "social", "participation", "stakeholder", "livelihood"),
}


def make_scientific_sql(table: str, domain: str, query: str, limit: int = 10) -> tuple[str, list[str]]:
    """Build safe, bounded SQL from fixed topic words; no user text interpolation."""
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*\.[A-Za-z][A-Za-z0-9_]*", table):
        raise ValueError("Invalid scientific table identifier")
    if domain not in TOPIC_TERMS or not 1 <= limit <= 20:
        raise ValueError("Unsupported scientific search domain or limit")
    if not re.fullmatch(r"[a-zA-Z\s-]{2,120}", query):
        raise ValueError("Use letters, spaces and hyphens only")
    words = set(re.findall(r"[a-z]+", query.lower()))
    recognized = [term for term in TOPIC_TERMS[domain] if term in words]
    if not recognized:
        raise ValueError("No supported research topic terms for this domain")
    conditions = " OR ".join(
        f"LOWER(abstract) LIKE '%{term}%' OR LOWER(title) LIKE '%{term}%'"
        for term in recognized
    )
    sql = (f"SELECT {', '.join(SCIENTIFIC_FIELDS)} FROM {table} "
           f"WHERE ({conditions}) ORDER BY entry_number LIMIT {limit}")
    return sql, recognized


@router.get("/evidence/scientific-search")
def scientific_search(query: str = Query(min_length=2, max_length=120),
                      domain: str = Query(default="Water")):
    if os.getenv("SAMPLE_MODE", "true").lower() == "true":
        raise HTTPException(status_code=409, detail="Live Zetaris search requires SAMPLE_MODE=false")
    env_file = Path(os.getenv("ZETARIS_ENV_FILE", ".env.local"))
    values = dotenv_values(env_file, interpolate=False)
    table = os.getenv("ZETARIS_SCIENTIFIC_TABLE") or values.get("ZETARIS_SCIENTIFIC_TABLE") or "HYDROGUARD.scientific_abstracts"
    try:
        sql, recognized = make_scientific_sql(table, domain, query)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid query/domain or scientific table configuration") from None
    try:
        config = Config.load(env_file)
    except (SmokeError, OSError):
        raise HTTPException(status_code=503, detail="Live Zetaris configuration unavailable") from None
    try:
        with httpx.Client(timeout=config.timeout, follow_redirects=False, trust_env=False) as http:
            response = http.post(
                config.base_url + "/sql-editor/sqls/run",
                headers={"Authorization": "Bearer " + config.api_key,
                         "X-Org-ID": config.org_id, "X-Request-ID": str(uuid4())},
                json={"queryId": str(uuid4()), "sql": sql, "source": "SqlEditor", "limit": 10},
            )
        if response.status_code != 200:
            raise ValueError("Non-200 Zetaris response")
        payload = response.json()
        rows = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(rows, list) or len(rows) > 10:
            raise ValueError("Invalid Zetaris response shape")
        results = []
        for row in rows:
            if not isinstance(row, list) or len(row) != len(SCIENTIFIC_FIELDS):
                raise ValueError("Invalid scientific row shape")
            record = dict(zip(SCIENTIFIC_FIELDS, row))
            entry = str(record.get("entry_number") or "").strip()
            # Exclude the two malformed rows observed during initial CSV registration.
            if not entry.isdigit() or not 1 <= int(entry) <= 238:
                continue
            results.append({key: (str(value) if value is not None else "")
                            for key, value in record.items()})
    except (httpx.HTTPError, ValueError, TypeError):
        raise HTTPException(status_code=502, detail="Live scientific lookup failed; check table columns and registration") from None
    return {"origin": "live_zetaris", "source_type": "scientific_abstract",
            "domain": domain, "supported_terms_used": recognized,
            "result_count": len(results), "results": results,
            "note": "Research abstracts only; not verified full papers or project-specific evidence."}
