# Meterless Runtime provider

Implements the supplied Runtime 1.4/provider-v4 client contract. Provider ID:
`meterless`; display name: `Meterless Runtime`; stable app ID: `hydroguard`.
This is a chat provider next to the existing offline Critic, not a replacement
for the evidence pipeline, a Nemotron Critic integration, or a World Model.
No such sponsor-completion claim is made.

## Use the UI

```bash
.venv/bin/python -m streamlit run app.py
```

The connection panel supports a pasted address or secret connect link, a masked
Runtime-token field, importing `<stateDir>/proxy-token`, Connect, and Auto Detect.
The token field is shown for unauthorized responses; it is never rendered in
plain text or echoed in an error. Connect links use a masked input too.

Private settings are in the ignored `data/providers/meterless.json`, with mode
0600 and an atomic save. The exact secret key is `meterless_runtime_token`;
`meterless_runtime_base_url` stores only the normalized URL, never a secret
connect fragment. `rt-local` is rejected rather than persisted as a valid token.
No Runtime token is put in `.env.example`, source code or reports.

URLs with/without a scheme, `/v1`, `/v1/models`, `/v1/chat/completions` and
`/healthz` normalize to the origin plus one `/v1`; repeated `/v1` is collapsed.
Connect links use origin plus `/v1` and obtain the token from fragment `k`.
Fragments are stripped before requests or storage. Redirects are not followed.
HTTPX proxy-environment inheritance is disabled for local Runtime requests.

Every call has a Bearer authorization header and `meterless-app: hydroguard`.
With no token, discovery sends the incomplete `Bearer` scheme and lets the real
server reject it; no placeholder token or fabricated local success is used.
Chat requires a real non-placeholder token and adds `meterless-scope: user`.

Discovery always uses `/v1/models`: 401/403 is `unauthorized`; HTTP 200 containing
one or more `meterless/*` IDs is `online`; all other results are `offline`.
`/healthz` is a process-health helper only, never the online criterion. Unknown
Meterless class/disposition IDs are retained; direct-model IDs are not offered
as Meterless routing modes. Discovery does not prove any specific NVIDIA model ran.

Auto Detect tries ports 8088, 8090, 8787 and 11434, in that order, on 127.0.0.1,
localhost and IPv6 loopback. It saves the first online or unauthorized hit.
Discovery probes have a short timeout; chat uses 180 seconds. Plain text is sent
unchanged as a string in `messages[0].content`, with `stream=false`; the client
returns only a string `choices[0].message.content`. HTTP/auth/timeout/protocol
failures produce sanitized errors, not synthetic content. The smoke check adds
an OpenAI-compatible 16-token output limit; normal UI calls do not impose it.

## Verification commands

```bash
.venv/bin/python -m scripts.verify_meterless --auto-detect --wrong-token-check
.venv/bin/python -m scripts.verify_meterless --auto-detect --wrong-token-check --chat
.venv/bin/python -m scripts.verify_meterless --state-dir '/your/verified/stateDir' --auto-detect
```

A connect link can be imported with `--connect-stdin`; interactive input is
hidden. Never put a token-bearing connect link in command-line arguments/history.

## Actual installation inspection

The actual process listening on loopback port 8088 is the native macOS executable:

`/Applications/Nightshift M1-M4.app/Contents/MacOS/nightshift-m1m4`

Its Info.plist reports bundle ID `ai.meterless.nightshift.m1m4`, version `0.92.7`.
The verified corresponding application-data folder is:

`/Users/ameekristinayco/Library/Application Support/ai.meterless.nightshift.m1m4`

It contains `runtime-token` and `secret.key`. The binary references `runtime-token`
and not `proxy-token`. No token or secret-key contents were printed, and
`secret.key` was not read. No explicit stateDir argument was present. This is a
native application process, not a Docker listener; no Docker volume change was
made. A Runtime 1.4-specific `proxy-token` stateDir was not found and is not guessed.

`METERLESS_RUNTIME_TOKEN` was absent from saved `.env`, `.env.local` and process
environment when checked. With the user's authorization, the installation's
existing `runtime-token` was used privately and saved under the required lower-case
settings key. This legacy filename is not silently substituted by the generic
`--state-dir` importer, which correctly requires `proxy-token` per contract.

Actual authenticated GET `/v1/models` returned HTTP 200: 14 IDs total, six
Meterless routing IDs (`auto`, `fast`, `deep`, `cheap`, `local`, `fusion`). The new
provider CLI's Auto Detect returned `online`; a deliberate wrong-token request
returned `unauthorized`, not offline. These are real Runtime/Nightshift discovery
results, not simulated tests. App version and contract behavior are reported
separately; no claim is made that the installed app's version string is 1.4.

The first real `meterless/auto` plain-text request timed out without content.
The subsequent 16-token retry returned a nonempty string. The actual final CLI
command below exited 0 with `state=online`, `wrong_token_state=unauthorized`,
`chat_returns_string=true` and `chat_nonempty=true`:

```bash
.venv/bin/python -m scripts.verify_meterless --auto-detect --wrong-token-check --chat
```

Thus all three acceptance checks passed against the installed service. The cause
of the first timeout was not established; discovery success alone was not counted
as inference success. Generated text and tokens were not printed.

## Implementation and tests

- `hydroguard/ai/meterless.py`: normalization, private settings, authenticated
  health/discovery/chat, Auto Detect and sanitized failures.
- `hydroguard/ai/providers.py`: general chat-provider registry.
- `hydroguard/ui/provider_settings.py` and root `app.py`: setup and chat check UI.
- `scripts/verify_meterless.py`: real verification CLI.
- `tests/test_meterless.py`: contract transport and UI regression checks.

Transport simulations verify all URL variants, unknown mode preservation,
401/403 classification, probe order, private token storage, connect-link handling,
string request/response, chat headers and timeout, and masked unauthorized UI.
They are not counted as proof of real inference.

Full regression result: `.venv/bin/python -m pytest -v` completed with
**169 passed, 0 failed, 8 dependency deprecation warnings**. This includes 36
Meterless contract/UI tests. Existing evidence, Zetaris, gate and API checks pass.
No evidence workflow was switched to Runtime and no commit/push was performed.
