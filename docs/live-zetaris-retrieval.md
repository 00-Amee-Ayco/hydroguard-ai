# Verified live regulatory retrieval

**Update:** optional case-scoped synthetic project retrieval is now implemented
for Riverside. See [the Water case](riverside-water-case.md). It retrieves both
source types through Zetaris, proposes a qualified unresolved disclosure gap,
and preserves the gate. Regulatory-only operation described below still works.

## Actual table and schema

Read-only discovery on the configured instance confirmed:

- `SHOW LIGHTNING DATABASES`: `HYDROGUARD` exists.
- `SHOW LIGHTNING TABLES HYDROGUARD`: `regulatory` is a JSON filestore table with
  registered path `dffs://hydroguard_water_9ea86d7aed6dae9f.jsonl`.
- `DESCRIBE DATASOURCE TABLE HYDROGUARD.regulatory` and the REST columns endpoint
  both returned its schema.

This was manually registered by the user; HydroGuard did not create or modify it.
The stored path is now observed metadata, not an inferred storage mapping.

The table has `chunk_id`, `document_id`, `title`, `page` (long), `text`,
`source_type`, `original_filename`, `locator`, author/date/URL fields and their
verification references, licence fields and extraction offsets. It does NOT
have an independent `source_id` or `provenance` column.

Mapping into existing citation schemas:

- `source_id = chunk_id`: a lossless citation alias of the actual returned key;
  HydroGuard does not generate a new source ID.
- `source_type=regulatory` maps to `provenance=government`, `kind=basis`.
  These are retrieved references, not automatically applicable assessment bases.
- Document/chunk IDs, title, exact text, physical PDF page and filename are retained.
- Source author, publication date, URL and paragraph/page locator are retained
  in additive optional citation fields. No dates, URLs or provisions are inferred.
- This adapter requires nonempty text and valid ingested content IDs and PDF page;
  DOCX-only/null-page rows are not supported by this PDF-focused adapter yet.

## Application integration

`EvidenceInvestigator` consumes an `EvidenceRetriever` contract. Sample retrieval
wraps the existing offline retrieval function; live retrieval uses only Zetaris
REST. The shared `InvestigationService` selects sample mode exactly as before,
or the live retriever when `SAMPLE_MODE=false`. No local source file or sample
registry is used as a live retrieval fallback. The live adapter does not need
`data/processed/knowledge/passages.jsonl` to query the registered table.

The `/run` request schema is unchanged. In live mode, use `evidence_references=[]`
to retrieve references or actual returned chunk IDs, rather than sample fixture
IDs. Unknown requested references fail explicitly. Responses add optional source
metadata; `critic` is nullable because no Critic runs in the current live path.
`AuditResult` is the current per-claim Evidence Ledger: live records, unresolved
finding, missing conditions and gate result are retained in its history.

Live mode currently returns HTTP 200 with `status=unresolved` for successful or
empty retrieval, no community question, and `gate.passed=false`. It explicitly
reports missing project disclosure, reviewed regulatory applicability/assessment
basis and live Critic approval. The existing deterministic gate is unchanged.
It rejects the unapproved finding. No offline Critic is substituted, no invented
impact is asserted, and no reference is relabeled as project-supplied evidence.

Connection/timeouts/HTTP failures return sanitized HTTP 502; missing/invalid
connection configuration returns 503. Malformed rows and duplicate IDs fail closed.
Empty results stay empty and unresolved. Health reports `live_retrieval_only`,
with full investigation execution unavailable and sponsor compliance unverified.
No Nightshift, Nemotron or World Model implementation was added.

## Run

Keep credentials in `.env.local`:

- `ZETARIS_REST_URL`, `ZETARIS_API_KEY`, `ZETARIS_ORG_ID` are required.
- `ZETARIS_REGULATORY_TABLE` defaults to the verified `HYDROGUARD.regulatory`.
- `ZETARIS_ENV_FILE` optionally selects another private config path.
- Process environment overrides the corresponding file variables.

```bash
SAMPLE_MODE=false .venv/bin/python -m scripts.verify_live_retrieval
SAMPLE_MODE=false .venv/bin/python run.py
```

The smoke CLI sends the existing Water request through FastAPI TestClient to the
real shared service and real REST endpoint. It explicitly omits synthetic fixture
reference IDs. It saves full results only to the ignored
`data/processed/knowledge/live_investigator_result.json`. The terminal prints only
execution metadata and citation IDs, not source text or credentials.

The actual Water query is:

```sql
SELECT chunk_id, document_id, title, page, text, source_type,
       original_filename, locator, issuing_body_or_author,
       publication_or_effective_date, original_source_url
FROM HYDROGUARD.regulatory
WHERE source_type = 'regulatory'
  AND (LOWER(text) LIKE '%water%'
       OR LOWER(text) LIKE '%demand%'
       OR LOWER(text) LIKE '%users%')
ORDER BY chunk_id LIMIT 10
```

Queries are input-dependent within a bounded public topic vocabulary. Only those
fixed topic words and validated table identifiers appear in SQL; private/free-form
claim text is never put in a query or log. This is lexical substring retrieval,
not semantic relevance or legal-applicability validation. One statement is sent
per request, through the verified `/api/v1.0/sql-editor/sqls/run`, with bearer
key, organisation header, UUID request ID/query ID, `source=SqlEditor`, limit 10,
verified TLS and bounded timeout; redirects are not followed.

## Actual integration result

**Retrieval PASS:** live `/run` returned HTTP 200 and one real passage:

`chunk-896f3cda0c6530a65e9e1e642155bea4557fa63f54652fa7a6770339fc7ef8c8`

The retrieved text, document ID, filename and PDF page 197 were compared to the
actual local extraction and matched exactly. That comparison was a separate check,
not a local fallback used by the adapter.

Verified run ID: `0bb400f1-2408-482c-90bc-f9d2e8a6c0e4`. Its ignored JSONL trace
contains the real SQL/query ID, HTTP 200, row count/source ID, Investigator consumed
records event and unchanged gate rejection. No Critic/model event was invented.
A sandbox-blocked attempt was reported as a failed retrieval; the approved network
retry succeeded. No claim is made that the complete corpus or ten passages were
returned: this query returned exactly ONE row.

The overall investigation remains unresolved. Next work is project-specific
source ingestion and reviewed assessment-basis applicability, followed separately
by live Critic integration. Do not weaken the gate to publish the reference as a
project impact conclusion.

## Regression checks

Full command: `.venv/bin/python -m pytest -v`.

Observed result: **125 passed, 0 failed, 8 dependency deprecation warnings**.
Transport tests use labeled synthetic fixtures to test schema mapping, citation
IDs, empty results, invalid records, HTTP/timeout/connection failures, SQL safety,
trace integrity and API behavior. They are not counted as real integration proof.
Sample examples were regenerated by actual sample execution because citation
responses now include additive optional metadata. Existing sample decisions,
questions and gate behavior remain intact; saved outputs are never read at runtime.
