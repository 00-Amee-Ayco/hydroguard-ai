# HydroGuard — Codex Engineering Instructions

## Mission
Build HydroGuard, a Philippine Environmental Impact Assessment (EIA) evidence-auditing and consultation-preparation assistant for affected communities. Deadline: **27 October 2026 at 23:45 UTC**. Prioritize a working, reproducible, auditable MVP over breadth.

**Core user story:** As an affected stakeholder preparing for environmental consultation, I want to provide project documents and community context so that I can understand possible impacts across **Water, Land, Air, and People**, identify claims that remain unsupported, prioritize issues, and prepare defensible consultation questions and next actions.

**Product promise:** See the claim. Trace the evidence. Challenge the gap. Know what to ask next.

## Architecture status and scope
These instructions define the final target architecture and the Open Agent Hackathon 2026 requirements supplied for this project. They are not evidence of implementation or independently verified official compliance. Consult the official rules and participant setup guide for authoritative submission and sponsor details; do not invent missing requirements or APIs.

The existing implementation is a fixed, synthetic water-audit fixture with Pydantic records, citation checks, a deterministic gate, and in-memory revision history. Its Critic responses and revision are prerecorded. Preserve useful code and tests, but do not present that fixture as the required input-dependent sample agent or as sponsor integration. API, UI, ingestion, live adapters, persistent Engine, tracing, and reports remain planned until implemented and verified.

## User-facing workflows
1. **Community Evidence Assistant:** Provide project documents and community context to a conversational, case-specific research assistant grounded in project materials, Philippine environmental regulations, technical guidelines, and scientific papers. Ask questions, inspect claims and their supporting or missing evidence, and access page-level source citations.
2. **Evidence View:** Inspect the Evidence Ledger, applicable assessment bases, source chunks, evidence-strength classification, Critic decision, deterministic gate result, and revision history.
3. **Community Consultation Brief:** Generate an editable DOCX report from a supported template with validated findings, unresolved questions, citations, and stage-appropriate actions. Preserve template formatting where feasible.

These workflows must support Philippine EIA stages without asserting definitive legal entitlements, approval outcomes, non-compliance, or environmental harm.

## Essential evidence-control loop
`Project claim -> Zetaris evidence retrieval -> Evidence Ledger -> Nemotron Evidence Critic via Nightshift -> Deterministic Evidence Gate -> (approved finding OR World Model update and bounded replanning) -> Community action -> Consultation Brief`

- Extract material claims from project disclosures across Water, Land, Air, and People.
- Retrieve project evidence, applicable EIA/regulatory assessment bases, and relevant scientific sources. Differentiate source types and their provenance.
- Store the **Evidence Ledger** with source references, gaps, limitations, revision IDs, and final decision.
- Classify evidence strength as **Strong, Moderate, Weak, or Insufficient**. Do not invent confidence percentages.
- A weak/insufficient evidentiary basis may support a carefully worded *evidence-gap* finding, but not a definitive claim of harm.
- The Critic may approve, narrow/downgrade, reject, or request reinvestigation.
- The deterministic gate must independently reject a finding if citations, cited assessment basis, current-revision Critic decision, or allowed claim-type conditions fail. Never treat LLM approval as sufficient by itself.
- On rejection, update the **Meterless World Model** with the missing evidence and required action. The Planner must read that changed state and generate a different, targeted Zetaris retrieval intent. Limit automatic reinvestigation to two retries. If evidence is still insufficient, output an explicitly unresolved finding.
- Never use fixed demo scripts to masquerade as real agent behavior.

## Knowledge base and document ingestion
- Implement a distinct ingestion pipeline, separate from investigation orchestration and UI.
- Extract PDF text with document and page provenance; chunk it with stable citation IDs and retain source version information.
- Index and retrieve project, regulatory, technical-guideline, and scientific materials through Zetaris in live mode. Keep source types and synthetic status distinguishable throughout retrieval, the ledger, and reports.
- Preserve exact source text and page/section references where available; never invent regulatory requirements, applicability, or citations.
- Do not train or fine-tune an LLM for the hackathon. Use retrieval and the configured inference gateway.

## Mandatory hackathon technology — real functionality required
- **Zetaris:** Mandatory live data layer. Query indexed project documents, research/regulatory chunks, and structured evidence through an authenticated, documented Zetaris connection. Log safe query metadata and source IDs. Do not silently use local CSV in live mode.
- **Meterless World Model:** Mandatory working Meterless Engine. Follow the official reference implementation/specification and relevant conformance tests. Persist versioned case entities, relationships, decisions, provenance, and read surfaces. Critic-driven state changes must change actual agent behavior. A plain Python dictionary does not qualify on its own.
- **Meterless Nightshift:** Primary AI inference gateway for all live LLM tasks. Do not call direct model providers in the application.
- **NVIDIA Nemotron:** Route Evidence Critic inference through Nightshift using a model available in the participant environment. Capture actual provider/model identity from returned metadata or authoritative Nightshift traces; mark it unverified if unavailable. Never hardcode claims that the model ran.
- **Codex:** Development tool only, not part of HydroGuard's runtime.

Follow the participant setup guide for credentials, endpoints, and engine APIs. Never invent vendor methods or report passing conformance without running it.

## Final application architecture and layout
- Python 3.11+, FastAPI, Streamlit, Pydantic, Pandas, PyMuPDF, HTTPX, python-dotenv, python-docx/docxtpl, Pytest.
- Modular monolith: `hydroguard/ingestion`, `data`, `agents`, `evidence`, `world_model`, `ai`, `services`, `reports`, `api`, `ui`.
- FastAPI exposes `GET /health` and `POST /run`; Streamlit provides the human-facing UI. Both call the same typed `InvestigationService`; do not duplicate investigation logic in entry points.
- Agent roles are **Case Planner**, **Evidence Investigator**, **Evidence Critic**, and **Community Action Planner**. Their tool operations, handoffs, feedback, and decisions must be observable and reflect actual execution.
- Keep the two-retry limit in shared orchestration so API and UI enforce the same bound.
- Separate provider interfaces from UI and domain logic; use explicit typed I/O.
- `SAMPLE_MODE=true` must work without sponsor credentials using bundled source records and real, input-dependent offline investigation logic. Compute retrieval, critiques, revisions, findings, and actions from the supplied inputs and evidence. Never replay prerecorded final outputs or critiques based on example IDs, exact example wording, or scenario labels.
- Clearly label offline adapters and synthetic sources. Sample mode is **not** proof of sponsor integration. `SAMPLE_MODE=false` must either use real sponsor services or fail clearly; never silently fall back to offline adapters.
- Existing prerecorded fixtures may remain as explicitly labeled regression/demo fixtures while the input-dependent workflow is implemented; they do not satisfy the final sample-mode requirement.
- Keep credentials in local `.env`, never version them. Commit a `.env.example` containing placeholders only. Never put NVIDIA provider credentials in code; configure them inside Nightshift.

## Runtime tracing
- Emit genuine JSONL events to stdout and `logs/`, with a unique run ID, agent name, status, actual tool operations, source IDs, handoffs, Critic decisions, gate results, World Model transitions, and retry counts.
- Trace actual execution only. Do not invent tool calls, state transitions, model identities, integration outcomes, or successful statuses. Offline traces must identify offline execution.
- In live mode, record safe Zetaris query/execution metadata and Nightshift request/response details. Verify NVIDIA Nemotron identity from authoritative returned metadata or runtime traces; mark identity unverified when unavailable.
- Redact credentials, tokens, sensitive case content, and stakeholder information before writing to stdout or files. Keep local logs out of version control; publish only reviewed, sanitized traces.

## Reproducibility and entry points
- Provide and document `run.py`, including exact commands for API, UI, and sample execution through shared services.
- Add `Dockerfile` and `.dockerignore`; exclude secrets, local environments, uploads, and generated data from build context.
- Support dependency installation and sample execution from a clean clone without local GPUs, manually installed models, undocumented setup, or source edits.
- Keep `.env.example` limited to safe defaults and placeholders; document actual configuration loading and fail clearly for missing live dependencies.

## Source quality and safety
- Show exact source document, page/section when available, chunk ID, and whether it is project-supplied, government, research, or synthetic.
- Never fabricate project facts, legal provisions, citations, study results, monitoring data, model identity, test traces, or domain expertise.
- Distinguish *evidence not found in reviewed materials* from *evidence does not exist*.
- Distinguish missing data from proven harm or non-compliance. Every publishable finding requires verified citations and an applicable, cited assessment basis.
- Keep unresolved findings explicitly unresolved. Only gate-approved affirmative findings may appear as conclusions in the Consultation Brief; present unresolved items separately as questions/gaps, never as affirmative harm or non-compliance conclusions.
- Interpret regulatory applicability cautiously; flag uncertain or dated provisions for expert review.
- Use plain language, communicate limitations, and present recommended questions/actions as assistance, not legal or regulatory determinations.
- Do not expose private stakeholder data, case content, secret keys, or provider tokens in public GitHub traces.

## Tests and definition of done
Write Pytest tests for:
1. Citation IDs resolving to retrieved source records.
2. Evidence gate blocking missing/invalid sources, unsupported definitive claims, rejected Critic decisions, and stale approvals.
3. World Model persistence and provenance.
4. Critic rejection changing state, Planner retrieval intent, and the *next* Zetaris query.
5. Retry cap and unresolved-case behavior.
6. Template population preserving user-provided values and section structure.
7. Sample mode without credentials; live mode fails transparently without integrations.
8. Relevant official World Model conformance checks, executed against the official Engine implementation/specification as applicable.
9. Evidence-schema validation, API health/run behavior, and shared-service execution.
10. Observable agent handoffs, actual JSONL tracing, redaction, and error handling.
11. Input-dependent offline investigations: three distinct sample inputs with matching outputs captured from actual runs, not replayed by example ID. Test that changed evidence/input changes relevant retrieval or decisions.

A feature is done only after relevant commands/tests have been run and their *actual* results reported. Do not claim all sponsor requirements are met from mocks alone.

## Codex working procedure
For every requested change:
1. Inspect repository files, `AGENTS.md`, existing tests, and current Git status. Preserve working code.
2. State the smallest implementation plan and files affected.
3. Implement one complete vertical slice; avoid speculative refactors and unrelated features.
4. Run relevant tests and show the command and pass/fail result.
5. Report modified files, actual observed behavior, blockers, and recommended next step.
6. Update README and `.env.example` when setup or behavior changes.
7. Do not delete existing data, change secrets, commit, push to GitHub, or publish without user approval.
8. Prioritize a working, judge-runnable MVP over optional features. Keep documentation explicit about implemented, planned, unverified, and blocked work.

## Submission checklist — Open Agent Hackathon 2026
- Public GitHub repository, published only with user approval.
- Accurate README covering setup, usage, architecture, sponsor integration status, examples, and limitations.
- Three different sample inputs and matching genuine outputs computed from those inputs.
- Sanitized execution traces from actual runs; live sponsor evidence must come from real calls and relevant tests.
- A 1–4 minute demo video and a slide deck.
- Honest disclosure of pre-existing work as required by the official rules, including existing fixture code where applicable.
- Submission deadline: **27 October 2026 at 23:45 UTC**. Check official rules for authoritative requirements; do not mark this checklist complete without evidence.

## Demo priority
Demonstrate the synthetic water-availability claim: preliminary overclaim -> Nemotron rejection -> World Model update -> targeted new Zetaris retrieval -> properly qualified evidence-gap finding -> community consultation question -> DOCX brief. Also include at least basic tests for Land, Air, and People.
