# HydroGuard

**See the claim. Trace the evidence. Challenge the gap. Know what to ask next.**

> **Status:** Hackathon MVP in development. Features and sponsor integrations must be verified in the local environment. This README is a starter template, not evidence that integrations are complete.

HydroGuard is an AI-assisted **evidence-auditing and consultation-preparation** tool for people and communities taking part in the Philippine Environmental Impact Assessment (EIA) process.

It helps users review project disclosures across **Water, Land, Air, and People**, identify what evidence supports a claim, surface unresolved gaps, and draft defensible questions and next steps for consultation. HydroGuard does **not** determine whether a project is safe, unlawful, compliant, or deserving of approval.

## Implemented offline evidence-auditing slice

The sample audit accepts a typed claim or CLI claim text and domain. It performs
lexical retrieval over bundled synthetic records, evaluates explicit evidence
criteria, computes a finding, runs an offline rule-based Critic, and independently
validates the result through the deterministic gate. Decisions do not branch on
fixture IDs or exact example sentences. No LLM is trained or invoked.

```bash
SAMPLE_MODE=true .venv/bin/python -m hydroguard.services.audit --domain Water
SAMPLE_MODE=true .venv/bin/python -m hydroguard.services.audit --domain Land
SAMPLE_MODE=true .venv/bin/python -m hydroguard.services.audit --domain Air --claim "Project dust emissions will not affect nearby air quality receptors."
```

JSON output contains the actual retrieved sources, claim, applicable synthetic
assessment basis, findings, Critic decisions, gate results, and community question.
Every citation resolves against these records, preserving document/page/chunk
provenance. Synthetic review criteria are not legal requirements.

The offline Critic is labeled `offline_rule_based`, with `live_inference=false`
and no verified model identity. It computes decisions from evidence-policy checks;
it is not independent scientific expertise or live NVIDIA/Meterless inference.
The gate separately executes those checks, rejects harm and illegality claims,
and binds approvals to the finding content/revision and evidence context.
Evidence gaps are computed from missing curated `evidence_items` required by the
assessment basis. Complete coverage produces a qualified evidence inventory,
not assurance of safety. Questions are emitted only for gate-approved findings.

Python callers may supply `run_sample_audit(claim, registry=..., bases=...,
preliminary=...)`. A rejected preliminary finding is revised once from reviewed
evidence; history remains in memory. The default run starts directly from the
computed finding and does not manufacture an overclaim. Unmatched claims or
missing citations/bases fail closed and receive no consultation question.

Limitations: retrieval is lexical and domain-scoped; evidence coverage uses
curated structured facts, not general semantic interpretation of arbitrary PDFs.
Changing prose alone does not extract new evidence items. New evidence must be
represented accurately in both source text and curated facts. People assessments,
PDF ingestion, Streamlit UI, persistent World Model, reports, and sponsor
integrations remain planned. The API and its per-run tracing are implemented below. This task does not establish full hackathon compliance.

The CLI reads `SAMPLE_MODE` from the process environment (default `true`), not
`.env`. `SAMPLE_MODE=false` raises “Live mode is not implemented”; no silent fallback
occurs. Sponsor fields in `.env.example` remain unused placeholders.

```bash
source .venv/bin/activate
python -m pytest -v
```

Root `app.py` remains an empty scaffold.

## Run the FastAPI interface

From the repository root:

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
python run.py
```

The API listens on `http://127.0.0.1:8000`; interactive request documentation is
available at `/docs`. `run.py` loads local `.env` without overriding process
variables. Sample mode defaults to true and needs no sponsor credentials.

```bash
curl http://127.0.0.1:8000/health
curl -X POST http://127.0.0.1:8000/run -H 'Content-Type: application/json' --data-binary @input_examples/water.json
```

`GET /health` reports process health, sample/live-unavailable mode, execution
availability, and explicitly unverified sponsor integrations. It performs no
sponsor calls. `POST /run` accepts:

- `project_claim`: `claim_id`, `project_name`, and nonblank `text`.
- `domain`: `Water`, `Land`, or `Air`.
- `case_context`: `stage` (`scoping`, `consultation`, or `review`) and optional
  private `community_notes`. Stage qualifies the question; notes are accepted
  but are not interpreted by the offline evidence rules or recorded in traces.
- `evidence_references`: source IDs from the bundled registry, restricting the
  retrieval pool. An empty list searches all bundled records for the domain.
  Unknown, cross-domain, and assessment-basis-only references are rejected.

Responses contain `run_id`, `status`, `finding`, resolved `citations`, `critic`,
`gate`, `community_question`, and the complete `audit` history. A blocked gate
returns `status=unresolved` and no question, rather than publishing a conclusion.
Invalid requests return 422; unsupported live execution returns 503. Unexpected
failures return a sanitized 500. This local judge/demo interface has no deployment
authentication or access controls.

`InvestigationService` wraps the existing audit workflow. API runs emit genuine
JSONL events to stdout and `logs/<run_id>.jsonl` (`HYDROGUARD_LOG_DIR` overrides the
directory). Events include timestamps, sequence, actual Planner/Investigator/
Critic/gate/action operations, source IDs, handoffs, branch decisions, retries,
and terminal status. No retry, sponsor call, or World Model event is invented.
The Python audit helper can take `trace=RunTrace()`; the existing standalone CLI
keeps its JSON-only output unless a trace is explicitly supplied.

Raw claims, project/community identifiers, community notes, credentials, and
exception text are omitted from traces. Source IDs outside the public bundled
registry are redacted. Validation errors omit input values and field locations;
HTTP access logging is disabled to avoid logging request URLs. Responses still
contain the caller's claim and should be handled as private case data. Local
logs remain ignored by Git.

Three structured requests are in `input_examples/{water,land,air}.json`. Their
matching `output_examples/*.json` were generated by executing the actual API via
FastAPI's in-process HTTP client, not by composing response fixtures. Regenerate:

```bash
SAMPLE_MODE=true python -m scripts.generate_examples
```

Generation emits real traces and assigns new run IDs. Runtime application modules
never load output examples as responses. Tests compare new computed responses
with saved examples after excluding the intentionally unique run ID.

## Intended users
Affected residents, barangay leaders, farmers, fisherfolk organizations, Indigenous community representatives, NGOs, and community advisers preparing for scoping or environmental consultation.

## MVP features
- **Community Evidence Assistant:** Questions answered using retrieved project, government, and scientific sources with citation provenance.
- **Evidence Ledger:** Per-claim record of source citations, assessment basis, evidence strength, limitations, Critic decisions, and gate results.
- **Critic + deterministic gate:** NVIDIA Nemotron (via Nightshift) reviews proposed findings; rules independently block unsupported claims.
- **Meterless World Model replanning:** Rejections update case state, which guides a targeted follow-up Zetaris query.
- **Community Consultation Brief:** DOCX export of approved/qualified findings, community questions, and appropriate next steps using a supported template.
- **Evidence View:** Technical audit trail behind community-facing conclusions.

Only mark individual features above as **implemented** after real execution and tests; until then they describe intended MVP scope.

## Architecture and remaining targets

The final architecture uses a modular Python application: FastAPI exposes
`GET /health` and `POST /run`, and Streamlit provides the human-facing UI. Both
must use the same `InvestigationService`. Case Planner, Evidence Investigator,
Evidence Critic, and Community Action Planner roles perform observable handoffs
and decisions, with at most two automatic reinvestigation retries.

A distinct PDF ingestion pipeline retains page provenance and stable chunk/citation
IDs before indexing project, regulatory, technical-guideline, and scientific sources
through Zetaris. No LLM training or fine-tuning is planned.

FastAPI, `InvestigationService`, `run.py`, and per-run JSONL tracing are implemented
for offline execution. The ingestion pipeline, Streamlit workflow, Docker
packaging, persistent Engine, and live sponsor integrations remain planned.


```text
Project PDFs + community context
              |
      Claim extraction
              |
      Zetaris retrieval  <-----+  (re-query if missing evidence)
              |               |
         Evidence Ledger      |
              |               |
    Evidence Critic (Nemotron | via Meterless Nightshift)
              |               |
   Deterministic evidence gate|
          /         \         |
      approved     blocked     |
          |          |         |
  Community Action  World Model+
          |          |
    Consultation Brief / Evidence View
```

**Zetaris:** live data layer for project, regulatory, and scientific evidence.  
**Meterless World Model:** versioned, persistent investigation state and replanning.  
**Meterless Nightshift:** primary AI inference gateway.  
**NVIDIA Nemotron:** adversarial Evidence Critic through Nightshift.

## Requirements
- Python **3.11+**
- Git
- A working Python package installer (`pip`)
- For **live mode:** authorized Zetaris and Meterless Nightshift access, a working World Model implementation, and an available NVIDIA Nemotron model routed through Nightshift
- For **sample mode:** bundled synthetic source records and computed offline rules (CLI and API slices)

## Installation from a clean clone

```bash
git clone https://github.com/YOUR_USERNAME/hydroguard-ai.git
cd hydroguard-ai
python3 -m venv .venv
source .venv/bin/activate  # macOS/Linux
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
```

On Windows, activate with `.venv\\Scripts\\activate` instead.

> Replace `YOUR_USERNAME` with the actual public repository owner. Ensure `.env.example` exists and contains **placeholders only**. Do not commit `.env`.

### Configure environment

The application-level environment variables proposed for this project are:

```dotenv
SAMPLE_MODE=true
ZETARIS_BASE_URL=
ZETARIS_API_TOKEN=
NIGHTSHIFT_BASE_URL=
NIGHTSHIFT_API_KEY=
NIGHTSHIFT_MODEL=
```

These are **HydroGuard configuration conventions**, not verified vendor environment variable names. Adapt the corresponding application adapters to your HackOS setup guide. Configure NVIDIA credentials in Nightshift's **Providers** tab, not in this project.

## Planned UI entry point (not implemented)

Root `app.py` is empty; the following is a future UI command, not a working
HydroGuard workflow. Use the implemented offline audit command above today.


```bash
python -m streamlit run app.py
```

Then open the local URL printed by Streamlit (commonly `http://localhost:8501`).

### Sample mode: input-dependent offline adapters

The implemented CLI computes lexical retrieval, evidence coverage, critique,
validation, and questions from inputs and retrieved synthetic records. The three
domain examples above use different evidence coverage. Offline adapters do not
establish any sponsor integration. See the implementation limits above.

### Live mode (not implemented)

The current CLI fails explicitly when the process environment sets
`SAMPLE_MODE=false`. The target live workflow requires real configured sponsor
services and indexed evidence, with no silent fallback to sample mode. No sponsor
integration is verified by the existing fixture.

## Planned demonstration (not yet implemented end to end)

**Synthetic case:** A proposed industrial development states that its water demand will not materially affect existing domestic and agricultural water users. The disclosed materials include annual demand figures and wet-season observations, but no sufficient dry-season water balance.

1. Upload the project material and provide local community context.
2. Ask HydroGuard: **“What evidence supports the claim that existing users will not be affected?”**
3. Inspect the Zetaris-retrieved project passage and relevant assessment basis.
4. Review the proposed finding and Nemotron Critic decision.
5. Show the World Model recording a rejected overclaim and requesting additional evidence.
6. Show the second, targeted Zetaris retrieval and the qualified evidence-gap finding.
7. Generate a Community Consultation Brief and inspect the detailed Evidence View.

The correct conclusion is **not** that the project necessarily causes water shortages. It is that the available disclosed evidence may not substantiate the project's assurance, if that is what the audited materials establish.

## Three executed sample inputs and matching results

Executed locally using `project_claim(domain)` and `run_sample_audit(claim)`:

- **Water:** “Project water demand will not significantly affect existing water users.”
  Gate passed a qualified gap finding with **Insufficient** evidence; missing items:
  `dry-season water balance`, `existing water users`. The question requests those
  records and their implications for affected users.
- **Land:** “Earthworks will not increase erosion or slope instability.”
  Gate passed a qualified gap finding with **Weak** evidence; the erosion baseline
  is present but `slope stability assessment` is missing. The question requests
  that assessment.
- **Air:** “Project dust emissions will not affect nearby air quality receptors.”
  Gate passed a qualified gap finding with **Weak** evidence; particulate baseline
  and dispersion assessment are present but `receptor inventory` is missing.
  The question requests that inventory.

These are actual offline result summaries, not live sponsor outputs. Rerun the
CLI commands above to inspect full findings, citations, and generated questions.

## Evidence strengths

- **Strong:** Direct, relevant and sufficiently supported for the specific finding.
- **Moderate:** Meaningful support with important qualifications.
- **Weak:** Some evidence, insufficient for the stronger conclusion.
- **Insufficient:** Not enough applicable evidence was identified.

Findings must pass the independent deterministic evidence gate before they are published as affirmative conclusions. Unresolved issues may be shown as clearly labeled questions or gaps.

## Tests

```bash
python -m pytest -q
```

Before submission, document how to execute:
1. Real Zetaris query smoke test.
2. Real Nightshift/Nemotron inference test with verified model identity.
3. Official **Meterless World Model** conformance tests.
4. Replanning integration test (rejection changes the next query).
5. Report-generation validation.
6. Clean-clone sample mode test.

Add exact commands and their **actual pass/fail outcomes** once verified. Do not include fictional traces or claims.

## Sponsor integration evidence

Add sanitized, genuine traces in `evidence/integration_traces/` after running the application. For each request, show (as available):
- Zetaris query metadata, retrieved chunk IDs, source and page numbers.
- World Model version, events and state transitions.
- Nightshift request metadata, resolved model identity and response status.
- Critic decision, gate failures, retry intent, and revised finding.

Never commit tokens, secrets, personal details, or confidential project documents.

## Repository hygiene and security

- GitHub repository must be **public** for judging.
- `.env` and local credentials must be excluded via `.gitignore`.
- `.env.example` must contain placeholders only.
- Use synthetic or appropriately licensed documents for public demo data.
- Preserve source citations, provenance, and regulatory version information.
- Human technical/legal review is still required for consequential decisions.

## Known limitations

- Current implementation supports bounded offline Water, Land, and Air investigations over curated synthetic records. People and general document interpretation remain unimplemented.
- Evidence not found in reviewed documents does not prove the evidence does not exist elsewhere.
- The product is not a replacement for professional environmental assessment, legal advice, or government decision-making.
- Arbitrary DOCX templates, scanned/OCR-only PDFs, and large-scale source ingestion may require further work.

## Roadmap
Expand to wider project/EIA coverage, multilingual community workflows, stronger retrieval and citation verification, multiple case histories, expert directories, and richer report templates.

## License
Add a `LICENSE` file appropriate for this repository before submission.
