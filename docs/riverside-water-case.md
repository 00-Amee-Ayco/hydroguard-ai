# Riverside Water evidence case

## Scope and result

Riverside Industrial Development is entirely fictional. No real company,
community, watercourse, measurement or project is represented. Its synthetic
project disclosure is combined with an authentic user-supplied regulatory
reference; the two source types are never relabeled as each other.

**Verified:** PDF generation -> existing ingestion pipeline -> private DFFS
upload -> separate project file table -> both tables queried through the shared
Evidence Investigator -> qualified unresolved finding -> unchanged gate rejection.
This is an end-to-end evidence/retrieval case, not a completed approval workflow.

Actual live `/run` ID: `38fe7f51-9ade-4478-ba3e-1aa15a11cec0`.
HTTP 200, 2 project passages and 1 regulatory passage were consumed. The ignored
JSONL trace logs both actual SQL requests/results, all source IDs, project and
regulatory consumption, unresolved applicability and the gate rejection.
No Nightshift, Nemotron or World Model execution occurred.

## Synthetic disclosure

The source is `data/cases/riverside/source/project/riverside_disclosure.pdf`.
Both pages are prominently marked synthetic. The PDF was rendered and visually
checked. It contains:

- Page 1: illustrative demand of 120 cubic metres/day; fictional three-visit
  wet-season observations and an illustrative 0.8 cubic metre/second observation;
  assurance that existing water users will not be adversely affected.
- Page 2: explicit declaration that a complete dry-season water balance and
  quantified existing-user abstraction evidence are not supplied; limits on
  what can be inferred from that absence.

These are fictional case inputs, not fabricated real study results. No regulatory
text was created or rewritten. The generator reuses a matching source PDF and
refuses to overwrite a document with different text. Ingestion produces two
page-local passages with stable document/chunk IDs, `source_type=project`,
`is_synthetic=true` and `case_id=riverside-water`.

Project citation IDs:

- PDF page 1: `chunk-e0c0052d89b36783315b1614c5ae244019d5fde8fb50d633c9e264c6af8fade1`
- PDF page 2: `chunk-cb8d9f9776e2fc12869ec448c7a1b067bec37c7e2e8ab0c9604ac028045aedf2`

Both pages' returned text/document IDs/page indices matched the local extraction
exactly. This is a separate verification, not a local fallback for live queries.

## Actual registration and parser limitation

Verified working table: `HYDROGUARD.riverside_project_793177886737a17b`.
Verified file path: `dffs://riverside_project_793177886737a17b.json`.
The file was uploaded using the actual instance OpenAPI's multipart
`POST /api/v1.0/ndp-files/save`, `path=/file-store`, `files=<snapshot>`.

Executed after the dry run:

```sql
CREATE LIGHTNING FILESTORE TABLE riverside_project_793177886737a17b
FROM HYDROGUARD FORMAT JSON
OPTIONS (PATH "dffs://riverside_project_793177886737a17b.json",
         inferSchema "true", multiLine "true")
```

The existing HYDROGUARD database was reused; no database or authentic regulatory
table was altered. The registrar checks the file/table before creation, never
overwrites an upload, and refuses an existing table with a different path.
Success requires SELECT to return the expected row count and exact IDs/text/page/
source type/case/synthetic markers. HTTP 200 alone is insufficient.

**Observed failed first attempt:** the initial JSONL table
`HYDROGUARD.riverside_project_4e89abfaf8745b51` exposed only the first record
(`COUNT(*)=1`). It was reported as failed verification, not successful ingestion.
A JSON-array snapshot with explicit multiline parsing then exposed both records.
The original JSONL exports and citation IDs were not changed by this transport
repackaging. The incomplete table/file remain untouched and are not configured
for this case. Removal would require a separate approved cleanup; no DROP was run.

## Actual retrieval

Regulatory table: `HYDROGUARD.regulatory`. The existing bounded Water query
returned one authentic passage, PDF page 197:

`chunk-896f3cda0c6530a65e9e1e642155bea4557fa63f54652fa7a6770339fc7ef8c8`

Project query:

```sql
SELECT chunk_id, document_id, title, page, text, source_type,
       original_filename, locator, issuing_body_or_author,
       publication_or_effective_date, original_source_url, case_id, is_synthetic
FROM HYDROGUARD.riverside_project_793177886737a17b
WHERE source_type = 'project'
  AND case_id = 'riverside-water' AND is_synthetic = true
ORDER BY chunk_id LIMIT 10
```

Project retrieval is enabled only for this configured case ID and Water domain;
other cases receive no Riverside passages. Wrong case/synthetic markers, source
types, duplicate IDs, malformed records, errors and timeouts fail closed. No
synthetic local adapter is ever used as a live failure fallback. `SAMPLE_MODE`
behavior and the public `/run` request schema remain unchanged.

## Assessment and gate boundary

Visual review of physical PDF page 197 (printed page 187) identified an Annex
2-28 example review-summary form with illustrative concerns and responses. It
does not establish a case-applicable dry-season balance or existing-user
abstraction requirement for this fictional industrial proposal. HydroGuard
creates NO applicable AssessmentBasis from that passage.

The proposed finding is computed from the two explicit omission declarations
in the actual retrieved project text, not from the case ID or saved outputs:

> The disclosed project evidence does not sufficiently establish that existing water users will remain unaffected during dry-season conditions.

This is an **Insufficient evidence-gap finding**, not harm, non-compliance or an
inference that studies do not exist elsewhere. Regulatory applicability is
explicitly unresolved. The ledger retains all three citations, project-only
claim citations, declared gaps, limitations, `critic=null` and gate failures.
The existing gate was not modified. No approval or consultation question is
published: a reviewed assessment basis and current-revision Critic approval
are absent, and the current proposed narrative is not promoted past the gate's
independent derivation policy. A live Critic alone would not establish the
missing basis or satisfy every gate condition.

The next blocker is a defensible, source-cited and case-applicable assessment
basis plus a live Critic integration and compatible validated finding derivation.
Missing disclosure is not automatically a statutory requirement. Those next
steps must preserve the current independent gate rather than bypass it.

## Reproduce

```bash
.venv/bin/python -m scripts.prepare_riverside
.venv/bin/python -m scripts.register_riverside
.venv/bin/python -m scripts.register_riverside --apply
SAMPLE_MODE=false .venv/bin/python -m scripts.verify_riverside
.venv/bin/python -m pytest -v
```

`prepare` generates only clearly labeled fiction and uses the existing ingestion
pipeline. The registrar defaults to a dry run. `--apply` uploads/registers the
named snapshot and verifies it; it does not modify any existing object. All source
PDFs, extracted text and result files stay under ignored `data/cases/`.

For a running API, set these privately in `.env.local` (or process environment):

```dotenv
ZETARIS_PROJECT_TABLE=HYDROGUARD.riverside_project_793177886737a17b
ZETARIS_PROJECT_CASE_ID=riverside-water
```

The existing REST credentials remain in `.env.local`. Set `SAMPLE_MODE=false` in
the process environment to run live. Use claim ID `riverside-water`, project name
`Riverside Industrial Development (fictional)`, the assurance from the disclosure,
Water domain, and empty evidence references for retrieval. The verification CLI
constructs that request from the local manifest and exercises the real FastAPI
route using TestClient with actual Zetaris access.

Tests observed: **133 passed, 0 failed, 8 dependency warnings**. Eight added case
checks cover PDF/extraction/snapshot idempotence, project provenance, three
scope-marker failures, cross-case isolation, input-dependent omission handling,
and unchanged gate/no-fabricated-Critic behavior. Existing sample/API regressions
also pass. Transport simulations are not counted as live integration evidence.
