# HydroGuard

**See the claim. Trace the evidence. Challenge the gap. Know what to ask next.**

> **Status:** Hackathon MVP in development. Features and sponsor integrations must be verified in the local environment. This README is a starter template, not evidence that integrations are complete.

HydroGuard is an AI-assisted **evidence-auditing and consultation-preparation** tool for people and communities taking part in the Philippine Environmental Impact Assessment (EIA) process.

It helps users review project disclosures across **Water, Land, Air, and People**, identify what evidence supports a claim, surface unresolved gaps, and draft defensible questions and next steps for consultation. HydroGuard does **not** determine whether a project is safe, unlawful, compliant, or deserving of approval.

## Implemented offline evidence-auditing slice

The repository now includes a synthetic water-claim audit, Pydantic records, an
independent deterministic gate, and a two-entry in-memory revision history.
Run it from the repository root after installing the requirements:

```bash
SAMPLE_MODE=true .venv/bin/python -m hydroguard.services.audit
```

The command prints JSON containing the source registry, fictional project claim,
synthetic assessment basis, both findings, prerecorded Critic responses, gate
results, and the consultation question. Every source is synthetic; the assessment
basis is an exercise criterion, not a Philippine legal provision.

The preliminary finding, “The project will cause community water shortages.”,
is rejected. The revised finding is:

> The disclosed evidence does not sufficiently establish that existing water users will remain unaffected during dry-season conditions.

The gate checks finding and project citations, cited assessment-basis records,
current-revision Critic approval and its content fingerprint, explicit gaps and
limitations, and the allowed claim type. This first slice permits only the exact
reviewed Water evidence-gap wording. It blocks all definitive harm and illegality
findings regardless of strength labels or Critic approval. It does not perform
general semantic validation of arbitrary findings or source content.

The consultation question requests a dry-season water balance addressing supply,
project demand, existing users, and their protection during dry periods. It is
returned only after the final gate passes.

**All Critic responses and the revision step are prerecorded sample behavior.**
No live model, Zetaris query, World Model, autonomous replanning, DOCX export,
or Streamlit workflow is implemented by this slice. History is returned as JSON,
not persisted to a database. Land, Air, and People have scope-rejection tests,
not implemented assessment workflows.

This command reads `SAMPLE_MODE` from the process environment, defaulting to
`true`; it does not load `.env`. Setting `SAMPLE_MODE=false` raises an explicit
“Live mode is not implemented” error. Existing `.env.example` integration fields
remain future configuration conventions and are unused here.

Run tests with the virtual environment activated:

```bash
source .venv/bin/activate
python -m pytest -v
```

The remaining MVP features and sponsor integrations below are target architecture,
not verified implementations. Root `app.py` remains an empty scaffold.

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

## Target architecture (planned)

The final architecture uses a modular Python application: FastAPI exposes
`GET /health` and `POST /run`, and Streamlit provides the human-facing UI. Both
must use the same `InvestigationService`. Case Planner, Evidence Investigator,
Evidence Critic, and Community Action Planner roles perform observable handoffs
and decisions, with at most two automatic reinvestigation retries.

A distinct PDF ingestion pipeline retains page provenance and stable chunk/citation
IDs before indexing project, regulatory, technical-guideline, and scientific sources
through Zetaris. No LLM training or fine-tuning is planned.

FastAPI, `InvestigationService`, the ingestion pipeline, `run.py`, Docker packaging,
and JSONL runtime tracing are not implemented. FastAPI is not yet declared in
`requirements.txt`. Future tracing must emit genuine, redacted events to stdout
and `logs/`, including run IDs, operations, decisions, handoffs, and retries.


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
- For **sample mode:** included synthetic fixtures and prerecorded Critic results (CLI slice only)

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

### Sample mode: current fixture and required replacement

The current CLI is a fixed synthetic regression/demo fixture with prerecorded
Critic responses and final revision text. It is preserved, labeled, and does not
satisfy the final input-dependent sample-mode requirement.

The target `SAMPLE_MODE=true` workflow must work without sponsor credentials using
bundled source records and offline adapters that compute investigation decisions
from inputs and evidence. It must not replay prerecorded critiques or final
outputs by example ID, wording, or scenario label. Offline execution must be
clearly distinguished from live sponsor integration.

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

## Three example inputs and expected behavior

| Input | Expected behavior (not a measured output) |
|---|---|
| “Does the project show a dry-season water balance?” | Cite examined pages and distinguish missing material from proof that no study exists. |
| “Will the project cause water shortages?” | Reject an unsupported categorical conclusion and state the specific missing evidence. |
| “What should we ask during public scoping?” | Generate stage-appropriate questions linked to approved/qualified Evidence Ledger findings. |

Replace this table with **actual captured sample outputs** before submitting.

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

- Current implementation is one fixed synthetic **water-availability** fixture. Input-dependent investigations remain planned; Land, Air, and People currently have scope-rejection tests only.
- Evidence not found in reviewed documents does not prove the evidence does not exist elsewhere.
- The product is not a replacement for professional environmental assessment, legal advice, or government decision-making.
- Arbitrary DOCX templates, scanned/OCR-only PDFs, and large-scale source ingestion may require further work.

## Roadmap
Expand to wider project/EIA coverage, multilingual community workflows, stronger retrieval and citation verification, multiple case histories, expert directories, and richer report templates.

## License
Add a `LICENSE` file appropriate for this repository before submission.
