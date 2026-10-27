"""Prepare documented S3 file-table registration; query only after registration.

No storage upload, creation, secret-bearing SQL, or silent local fallback occurs here.
"""
from hashlib import sha256
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
from scripts.zetaris_smoke import Config

IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


def registration_plan(passages: Path, s3_uri: str, database: str = "hydroguard_knowledge") -> dict:
    uri = urlsplit(s3_uri)
    if (uri.scheme != "s3a" or not uri.netloc or not uri.path or uri.query or uri.fragment
            or not re.fullmatch(r"[A-Za-z0-9_/-]+", uri.netloc + uri.path.removesuffix(".jsonl"))):
        raise ValueError("Supply an engine-reachable s3a://bucket/key.jsonl without credentials or SQL quoting")
    if not IDENTIFIER.fullmatch(database):
        raise ValueError("Invalid database identifier")
    table = "passages_" + sha256(passages.read_bytes()).hexdigest()[:16]
    return {"dry_run": True, "database": database, "table": table,
            "limitations": "Upload snapshot privately to the supplied engine-reachable location first. Private S3 credentials/connector options must be configured on the instance. Inspect existing database/table before creating; never overwrite an existing snapshot.",
            "statements": [f'CREATE LIGHTNING DATABASE {database} DESCRIBE BY "HydroGuard knowledge evidence"',
                           f'CREATE LIGHTNING FILESTORE TABLE {table} FROM {database} FORMAT JSON OPTIONS (PATH "{s3_uri}")'],
            "verification_query": f"SELECT chunk_id, document_id, original_filename, source_type, page, locator, text FROM {database}.{table} LIMIT 1"}


def query_registered_passage(config: Config, table: str, records: dict[str, dict], chunk_id: str) -> dict:
    """Real REST query; returned text/provenance must match the exported record."""
    if len(table.split(".")) != 2 or not all(IDENTIFIER.fullmatch(part) for part in table.split(".")):
        raise ValueError("Supply a qualified database.table")
    expected = records[chunk_id]
    if not re.fullmatch(r"chunk-[0-9a-f]{64}", chunk_id):
        raise ValueError("Invalid citation ID")
    fields = ("chunk_id", "document_id", "original_filename", "source_type", "title", "page", "locator", "text")
    sql = f"SELECT {', '.join(fields)} FROM {table} WHERE chunk_id = '{chunk_id}' LIMIT 1"
    try:
        with httpx.Client(timeout=config.timeout, follow_redirects=False) as client:
            response = client.post(config.base_url + "/sql-editor/sqls/run", headers={
                "Authorization": "Bearer " + config.api_key, "X-Org-ID": config.org_id,
                "X-Request-ID": str(uuid4())}, json={"queryId": str(uuid4()), "sql": sql, "source": "SqlEditor", "limit": 1})
            if response.status_code != 200:
                raise RuntimeError(f"Zetaris HTTP {response.status_code}; body omitted")
            rows = response.json().get("data")
    except (httpx.HTTPError, ValueError):
        raise RuntimeError("Zetaris query failed or returned invalid JSON; credentials and response omitted") from None
    expected_row = [expected[field] for field in fields]
    # Zetaris may return numeric page values as strings. Do not relax text/ID checks.
    if isinstance(rows, list) and len(rows) == 1 and len(rows[0]) == len(fields):
        index = fields.index("page")
        if expected["page"] is not None and str(rows[0][index]) == str(expected["page"]):
            rows[0][index] = expected["page"]
    if rows != [expected_row]:
        raise RuntimeError("Zetaris passage/provenance did not match the local citation registry")
    return {"verified": True, "chunk_id": chunk_id, "record": expected, "query": sql}
