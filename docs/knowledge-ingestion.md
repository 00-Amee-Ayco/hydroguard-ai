# Curated knowledge ingestion

**Current update:** the user registered `HYDROGUARD.regulatory`; live application
retrieval now returns one verified Water passage through the shared Investigator.
See [live regulatory retrieval](live-zetaris-retrieval.md) for the actual schema,
SQL, source ID, trace and remaining investigation blockers. The earlier storage
probe below is historical; it no longer represents the current registration state.

This pipeline reads the user's files. It never generates regulatory texts or
substitutes sample evidence. It is independent of `/run` and the sample adapter.

## Observed inventory and limits

One PDF was supplied under `data/knowledge/regulatory/`: the Revised Procedural
Manual for DAO 2003-30 (6,649,616 bytes, 247 PDF pages). No scientific, project,
community or DOCX source was present. There is no project disclosure on which to
base the proposed Water-impact investigation. Retrieval of a general reference
is not an applicability decision or an approved impact finding.

PDF page 1 is an image-only cover, excluded from text passages and flagged for
OCR/manual review. Visual review verified the title, DENR Environmental Management
Bureau attribution, and publication month August 2007. This is not an effective
date or verification of current regulatory applicability. Original PDF URL and
licence remain unverified. No bibliographic values are inferred from file dates.
Manual cover observations are stored in the ignored local metadata catalog with
page references; no OCR text was invented.

## Execute

```bash
.venv/bin/python -m scripts.ingest_knowledge --catalog data/knowledge/metadata.json
```

`--catalog` is optional. Without it, titles fall back to filenames (explicitly
unverified), source type comes from the regulatory/scientific/project/community
folder label, and unverified author/date/URL fields stay null. The local catalog
maps relative file paths to `Metadata` fields in `hydroguard/ingestion/pipeline.py`.
Curated title/author/date/URL values require a corresponding verification-reference
field. Record licence restrictions in `licence` and `licence_reference`; unknown
licences remain unverified. Verify source rights before redistribution or indexing
outside an authorised private environment.

Outputs under the ignored `data/processed/knowledge/` directory:

- `inventory.json`: filenames, sizes, document hashes, extraction status/review flags.
- `documents.json`: complete source metadata, aliases, extraction/chunk policy.
- `passages.jsonl`: one JSON record per passage, appropriate for a JSON file table.
- `passages.csv`: quoted UTF-8 CSV alternative; text may contain embedded newlines.
- `water_preview.json`: explicitly LOCAL lexical retrieval preview with actual text
  and citations. This is not Zetaris retrieval or an agent finding.

The actual supplied PDF yielded 1,701 passages and five Water preview hits.
Two consecutive runs produced byte-identical exports. Re-running regenerates
snapshots, not append-only duplicates; identical file content is indexed once and
aliases are retained. Output is atomically replaced per file; concurrent ingestion
runs against the same output directory are not supported.

Document IDs are SHA-256 content IDs. Chunk IDs include document ID, policy, page/
paragraph locator, character offsets, and exact extracted text hash. New document
bytes invalidate citations; metadata correction does not relabel identical passages.
Chunk size is bounded and passages never cross PDF page or DOCX paragraph boundaries.

PDF `page` is the 1-based physical PDF page index, not necessarily the printed page
label. Text extraction uses PyMuPDF sorted reading order; complex columns, tables,
equations, hyphenation, and existing OCR layers need human checking. Textless pages
or pages dominated by raster imagery are flagged and omitted. This is a conservative
scan heuristic, not a complete OCR-quality detector; legitimate illustrated pages
can be flagged. No automatic OCR is attempted.

DOCX uses python-docx: `page=null`; locators identify 1-based body paragraph numbers
or table/row/cell/paragraph coordinates. Sections are preceding heading paths, not
invented Word page or layout-section numbers. Empty paragraphs count in body
numbering. Merged cells are not duplicated; headers/footers, textboxes, nested
tables, tracked-change text and embedded objects require manual review.

## Initial Zetaris verification and storage blocker (historical)

The official [file ingestion guide](https://github.com/zetaris/getting-started/blob/main/open_data/parquet_csv/HOWTO.md)
documents `CREATE LIGHTNING DATABASE` followed by
`CREATE LIGHTNING FILESTORE TABLE ... FORMAT JSON/CSV OPTIONS (PATH ...)`.
The demonstrated paths are S3/S3-compatible locations readable by the engine;
a laptop path or OneDrive folder is not a documented registration target.

A fresh OpenAPI specification was retrieved from the configured instance using
Basic authentication: HTTP 200. It documents multipart upload via
`POST /api/v1.0/workspace/files/save` with `path` and `files` form fields.
That endpoint's existence does not establish a SQL-readable workspace storage
mapping; workspace uploads and Data Fabric file-store uploads are separate. The initial read-only list request with empty path returned HTTP 400. A later
probe using `path=/` succeeded; see the current registration probe below. The Basic-auth spec remains outside the repo under `/tmp`.

Actual bearer-authenticated `SELECT 1` returned `1` (HTTP 200), and
`SHOW LIGHTNING DATABASES` succeeded (three databases; no `hydroguard_knowledge`).
No structured evidence table is registered and **no live passage retrieval has
been verified**. No SQL literal echo or sample output is counted as retrieval.

Next prerequisite: an authorised private S3/S3-compatible URI and instance storage
configuration, or verified documentation mapping workspace uploads to engine paths.
No endpoint/path/credential mapping is guessed and no full text is publicly hosted.
Once a real storage URI is available, prepare a reviewable dry run:

```bash
.venv/bin/python -m scripts.knowledge_zetaris --plan-s3-uri 's3a://YOUR_PRIVATE_BUCKET/knowledge/passages.jsonl'
```

This example URI is a placeholder, not a configured path. The command does not
connect, upload, or create. It emits a content-addressed table name and registration
SQL. Inspect existing objects first, configure private storage access on the
instance, and obtain the user's go-ahead before uploading or creating anything.
The plan does not supply S3 keys or silently mark the corpus public. There is no
automatic apply command or destructive update path.

After authorised registration, verify one real Water passage:

```bash
.venv/bin/python -m scripts.knowledge_zetaris --query-table 'hydroguard_knowledge.TABLE_FROM_THE_APPROVED_PLAN' --env-file .env.local
```

The query command uses the documented REST SQL endpoint with UUID request/query
IDs. It compares the returned citation ID, document ID, filename, source type,
title, PDF page and locator, and passage text with the local registry; it saves
full results privately and prints only verification metadata. If the table is
missing, permission denied, the network fails, or provenance differs, it fails
without local fallback. This command has not passed a live passage query yet.

## Earlier ten-passage registration probe: BLOCKED (historical)

A fresh instance OpenAPI specification was fetched successfully. Besides workspace
uploads it documents `POST /api/v1.0/ndp-files/save` (multipart `path` and `files`)
and `GET /api/v1.0/ndp-files/list?path=...`. These endpoints were discovered in the
actual specification, not invented. The account can list and upload files to
both services; no permission denial was observed for these operations.

Ten genuine Water-related regulatory passages were selected deterministically
from the local registry, preserving all original chunk/document IDs, exact text,
physical PDF page, title, source type, and provenance. The private JSONL subset is
`hydroguard_water_9ea86d7aed6dae9f.jsonl` (24,688 bytes). Original documents and
full-corpus exports were not changed. No full text was printed in reports.

Dry-run upload plans were saved and inspected before executing uploads. The
actual HTTP 200 responses used a `SaveSuccess` wrapper around `fileName`;
HTTP 200 alone was not treated as a table registration. One copy now exists in
the private workspace root and one in Data Fabric's logical `/file-store`.
No overwrite, delete, database creation or table creation was performed.
The two private copies are intentionally left intact for the next setup step.

Observed checks:

- `GET /workspace/files/list?path=/`: HTTP 200; upload appears there.
- `GET /ndp-files/list?path=/`: HTTP 200; contains `file-store` and a trust-store
  directory. The trust store was not inspected.
- `GET /ndp-files/list?path=/file-store`: HTTP 200; uploaded subset appears.
- File-list responses have `path: null`; no physical URI is exposed.
- `GET /storage-setting`: HTTP 200, zero configured settings.
- `GET /compute/platform/config`: HTTP 200; no workspace/file-store mapping
  appeared in the returned configuration. Configuration secrets were not logged.
- `LIST HDFS FILES "/file-store"`: HTTP 400; parser requires `OPTIONS`.
- `LIST HDFS FILES "/file-store" OPTIONS ()`: HTTP 200, zero rows.
- Actual final smoke: metadata HTTP 200; `SELECT 1` returned `[["1"]]`.
- Database inventory still has NY_TAXI, POKEAPI_REST, and TPCDS_DB; no HydroGuard
  evidence table was created or registered.

The engine-visible `/file-store` is therefore not established as the logical NDP
file-store path. This may require a shared-volume mapping or another configured
storage connector; the probe does not assert which infrastructure component is
missing. Prefixing an unverified URI scheme, creating a table against a guessed
path, or returning SQL literals would not verify registration, so none was done.

**Evidence retrieval result: BLOCKED.** Registered table/source: none. Genuine
passages retrieved by SQL: 0. Source IDs returned by a passage query: none.
The subset's existing local IDs are not reported as live retrieved source IDs.
The Evidence Investigator, sample adapter, `/run`, and deterministic gate were
left intact; no live adapter is wired up before verified retrieval succeeds.

### Next specific UI action

Following Zetaris's official
[File System guide](https://kbase.zetaris.com/knowledge/file-system-overview) and
[connection guide](https://kbase.zetaris.com/knowledge/connect):

1. Open the **Data Fabric File System** (not the script/workspace file browser).
   Confirm `hydroguard_water_9ea86d7aed6dae9f.jsonl` in `/file-store`.
2. In Fabric Builder/Data Explorer's virtual file-source area, start the **File
   Store** registration wizard. Use JSON and the platform/Data Fabric storage
   option if offered, then browse to that existing file. Suggested source/table
   names for a future approved registration: `hydroguard_knowledge` and
   `water_passages_9ea86d7aed6dae9f` (these are NOT existing objects).
3. Request the wizard's data preview before completing registration. Obtain the
   exact engine-readable path or generated SQL from the wizard. No API keys or
   other credentials should be copied into chat, reports, or generated SQL.
4. If the file cannot be browsed or previewed, the instance administrator must
   map Data Fabric file storage into the SQL engine or configure a private
   S3/S3-compatible connection and provide the engine-readable URI. Uploading to
   the workspace again will not fix the demonstrated path mismatch.
5. After a successful preview and approval of the concrete registration plan,
   register and run an actual SELECT, comparing returned passages/provenance to
   the local registry. Only then connect the live Investigator adapter.

These steps follow vendor documentation; this session did not manipulate the
UI or claim its wizard preview succeeded. Diagnostic artifacts and API responses
are saved privately under `data/processed/knowledge/`, including
`registration_probe.json`, both upload plans/results, and storage probes.

## Validation and security

`data/knowledge/` and `data/processed/` are gitignored, including raw documents,
local catalog, passages and retrieval results. Do not force-add these directories
or publish licence-unverified text. No source documents were deleted or modified.
No existing audit models, sample adapters, FastAPI routes, secrets or dependencies
were changed by this ingestion slice.

Tests use explicitly synthetic parser fixtures in temporary directories, never
replacement regulatory documents. The live-query transport test is mocked and
is not sponsor-integration evidence.

```bash
source .venv/bin/activate
python -m pytest -v
```

Observed result: 107 passed, 0 failed, 8 dependency deprecation warnings. This
includes PDF/DOCX extraction, image-only-page review, page/paragraph provenance,
chunk offsets/stability, idempotence, duplicate-content handling, source-type
filtering, citation resolution, and matching remote-query response validation.
Existing API and sample-audit tests continue to pass.
