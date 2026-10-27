# Five-slide demo outline

## Slide 1 — See the claim, trace the evidence

Audience: stakeholders preparing for Philippine EIA consultation.
Problem: a confident project assurance may omit evidence needed to assess it.
Show the fictional Water input; explain that this is assistance, not a safety,
compliance or approval decision.

## Slide 2 — Working offline audit

Run `SAMPLE_MODE=true python run.py` and POST `input_examples/water.json`.
Show source/page/chunk citations, Insufficient evidence, dry-season/existing-user
gaps, rule-based Critic, independent gate and consultation question. Label all
bundled evidence synthetic and the Critic offline. Do not imply model inference.

## Slide 3 — Inputs change the result

POST Land and Air examples. Show missing slope stability assessment versus missing
receptor inventory, both Weak evidence. Compare the genuinely generated output
examples. Explain that runtime code computes responses rather than replaying files.
Show the test result: 202 passed, 0 failed.

## Slide 4 — Real data, honest unresolved result

Show the recorded freeze verification of live Zetaris retrieval: one genuine
regulatory passage, page 197, source ID and run ID from submission-summary.md.
Explain provenance and the unresolved gate result: retrieval is not applicability,
project safety or approval. Show only reviewed metadata, not restricted full text,
credentials or unsanitized local logs. A live re-run requires private configuration.

## Slide 5 — Boundaries and next milestone

Verified: offline auditing/gate/API, document ingestion, genuine Zetaris passage
retrieval, authenticated Nightshift discovery. Blocked: Nemotron HTTP 502 and
unverified model execution. Not verified/implemented: official World Model Engine,
Critic-driven replanning, community evidence UI, consultation DOCX generator.
Next milestone is an authorized, verified Critic/Engine loop after the freeze.
Close with the actual consultation question, not an invented harm conclusion.
