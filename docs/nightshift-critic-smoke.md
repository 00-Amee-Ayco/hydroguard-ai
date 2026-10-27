# Isolated Nightshift / Nemotron smoke test

```bash
.venv/bin/python -m scripts.verify_nightshift_critic
```

The command explicitly loads `.env` and `.env.local` (interpolation disabled),
then overlays process environment variables, which take precedence per key.
It consumes `NIGHTSHIFT_BASE_URL`, `NIGHTSHIFT_API_KEY`,
`METERLESS_RUNTIME_TOKEN` and `NIGHTSHIFT_MODEL`. Blank values use existing
private settings in `data/providers/meterless.json`; API key selection prefers
NIGHTSHIFT_API_KEY, then METERLESS_RUNTIME_TOKEN, then the stored Runtime token.
No configuration is written. These names are HydroGuard conventions.

The [official Meterless contract](https://www.meterless.ai/engines.html) and
[CLI documentation](https://meterless.ai/cli.html) describe the authenticated
OpenAI-compatible API. Discovery is GET `/v1/models`; chat is POST
`/v1/chat/completions`. Requests send Bearer authentication and
`meterless-app: hydroguard`, plus `meterless-scope: user` for chat. Plain text
remains a string. Discovery timeout is 15 seconds, chat timeout 180 seconds.
Redirects and proxy environment inheritance are disabled. No retry or fallback.
The participant-specific HackOS guide has not been located in the repository.

The isolated probe accepts Nemotron inference IDs actually advertised by
Nightshift, including `nvidia/*` IDs. This does not call NVIDIA directly: every
request goes to the configured Nightshift origin. Embedding IDs are excluded.
An explicitly configured model must be present in discovery; otherwise the
probe blocks. Without a configured model, it chooses a discovered Nemotron
inference ID, preferring a lightning ID. The earlier restriction requiring a
`meterless/` prefix was too narrow and is corrected only in this isolated probe.
The general provider, InvestigationService, offline Critic and gate are unchanged.

The prompt is the user's synthetic water-disclosure question. At most one
inference is made. Output includes statuses, safe identifiers, a model-mismatch
flag and an optional heuristic summary; no generated response text, full payload,
authorization values or raw exceptions are printed. A successful result requires
nonempty text and response-reported NVIDIA Nemotron identity. A reflected
`meterless/*` mode is insufficient. A different model than a requested specific
NVIDIA ID blocks success. Response-reported identity is not independent attestation.

## Actual latest execution

Authenticated discovery at `http://127.0.0.1:8088/v1/models` returned HTTP 200
and 19 IDs, including five NVIDIA Nemotron IDs. The current saved `.env.local`
had Zetaris keys only; no populated Nightshift variables were found in `.env`
or `.env.local`. Existing private Runtime settings supplied authentication.
No provider settings or environment files were overwritten.

The one inference requested `nvidia/nemotron-3.5-lightning-30b-a3b` through
Nightshift POST `/v1/chat/completions`. It returned **HTTP 502**. No request ID,
actual resolved model, or output was available. Connection PASS; Nemotron
inference BLOCKED. A route being advertised does not prove it can execute.
No second inference, fallback, or direct NVIDIA request was made.

Next action: inspect Nightshift's local runtime/lane diagnostics for this HTTP
502 and confirm the advertised NVIDIA route can execute. The 502 alone does
not establish whether credentials, upstream availability or model mapping is
the cause. Re-run the same command after resolving that runtime error.

## HTTP 502 diagnosis

The diagnostic retry matched the requested ID exactly to authenticated discovery:

- `nvidia/nemotron-3.5-lightning-30b-a3b`
- `nvidia/nemotron-3-ultra-550b-a55b`
- `nvidia/nemotron-3.5-bolt-e4b`
- `nvidia/nemotron-3-embed-1b` (embedding, not chat)
- `nvidia/nemotron-3.5-embed-1b` (embedding, not chat)

Each discovery row reports `owned_by: nvidia`, `meterless.kind: cloud`, and
`meterless.availability: unverified`. These are cloud provider IDs, not resident
local lanes or generic `meterless/auto` aliases. The failed ID matched exactly.

Documented GET `/healthz` returned 200, `engine_ready: true`, cloud native true,
and reported an NVIDIA provider key present. GET `/v1/meterless/classes` returned
200 and listed the three chat IDs under the text/judge cloud routes. Its text
ready state also includes a local Llama lane; that does not establish NVIDIA
readiness. No `ns` executable was available on PATH, so no CLI command was guessed.
Health/class diagnostics are documented on the Meterless CLI/engines pages linked
above. No undocumented lane/provider endpoint was called.

One exact Lightning retry through Nightshift returned HTTP 502 with:

- error type `api_error`
- error code `provider_auth_failed`
- upstream detail: NVIDIA HTTP 403, title `Forbidden`, detail `Authorization failed`
- no request/correlation ID returned in the inspected headers
- no response model or nonempty output

The runtime message distinguishes its saved **provider key** in Setup → Providers
from the Runtime API key. Runtime authentication works. The observed cause of
502 is upstream provider authentication/access rejection; whether the saved key
is invalid/revoked or the account lacks model access is not established. A
configured credential exists, but is not proven usable. The installed provider
implementation also maps upstream 401/403 to `provider_auth_failed`.
There is no evidence of a request-format or embedding/chat mismatch for Lightning.

Stop and check the NVIDIA entry in Nightshift Setup → Providers: use a current
credential and verify that its account can invoke the exact advertised chat model.
Do not change HydroGuard's working Runtime key as a remedy for this upstream 403.
No alternate inference was attempted after this provider-auth failure. No
participant guide was available to verify additional hackathon route restrictions.
The repeatable smoke test now classifies this known error code without printing
raw provider error bodies. No provider setting, model download or evidence
pipeline change was made.

## Direct NVIDIA comparison diagnostic

Official model-specific Build example:
https://build.nvidia.com/nvidia/nemotron-3.5-lightning-30b-a3b/build
confirms base URL `https://integrate.api.nvidia.com/v1`, chat completions, and
model `nvidia/nemotron-3.5-lightning-30b-a3b`. The matching ID is documented,
not inferred by stripping a Nightshift prefix.

No NVIDIA credential was available in parsed `.env`, `.env.local` or process
configuration for a direct diagnostic. Nightshift's encrypted provider store
was not decrypted and an exposed chat credential was not reused. Direct
inference: NOT TESTED. This is not a direct-provider application adapter.

One subsequent Nightshift comparison request returned HTTP 502 with
`provider_error_category: unclassified_provider_error`; discovery returned 200
and 19 routes. No request ID, actual model or text output was returned. The
current error could not be classified from recognized private error fields;
the earlier upstream 403 is historical evidence, not proof of the latest cause.
The classifier now recognizes nested/stringified status fields, NVIDIA status
markers, auth/access, rate limit, missing model and timeout categories, returning
only fixed labels and numeric statuses. Unrecognized errors stay explicitly
unclassified; arbitrary response details are never printed.

Next action: ask Meterless support to inspect the active native runtime's
forwarding error for this exact route/502. Direct-vs-forwarding attribution is
unresolved without a safely configured direct credential and successful comparison.
