"""Meterless Runtime 1.4 / provider contract v4. No evidence-Critic wiring."""
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import parse_qs, urlsplit, urlunsplit
import httpx

PROVIDER_ID = "meterless"
PROVIDER_NAME = "Meterless Runtime"
DEFAULT_BASE_URL = "http://127.0.0.1:8088/v1"
APP_ID = "hydroguard"
TOKEN_KEY = "meterless_runtime_token"
BASE_KEY = "meterless_runtime_base_url"
CHAT_TIMEOUT = 180.0


class MeterlessError(RuntimeError):
    """Constant sanitized messages only; never raw HTTP exceptions or response bodies."""


@dataclass(frozen=True)
class Connection:
    base_url: str
    token: str = field(default="", repr=False)


@dataclass(frozen=True)
class ProviderStatus:
    state: str  # online | unauthorized | offline
    models: tuple[str, ...] = ()

    @property
    def requires_token(self):
        return self.state == "unauthorized"


def parse_connection(value: str, token: str = "") -> Connection:
    """Consume a pasted address/connect link without retaining its secret fragment."""
    value = value.strip() or DEFAULT_BASE_URL
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", value):
        value = "http://" + value
    try:
        url = urlsplit(value)
        if url.scheme not in ("http", "https") or not url.hostname or url.username or url.password:
            raise ValueError
        port = url.port
        host = url.hostname
        if any(char.isspace() for char in host):
            raise ValueError
        authority = f"[{host}]" if ":" in host else host
        if port is not None:
            authority += f":{port}"
        path = url.path.rstrip("/")
        if path == "/connect":
            keys = parse_qs(url.fragment).get("k", [])
            if len(keys) != 1 or not keys[0]:
                raise ValueError
            token = keys[0]
        elif not re.fullmatch(r"(?:/v1)*(?:/(?:chat/completions|models|healthz))?", path):
            raise ValueError
        elif url.fragment:
            raise ValueError
        base = urlunsplit((url.scheme, authority, "/v1", "", ""))
    except (ValueError, TypeError):
        raise MeterlessError("Invalid Runtime address/connect link; value omitted") from None
    if not isinstance(token,str) or any(char.isspace() for char in token):
        raise MeterlessError("Invalid Runtime token format; value omitted")
    return Connection(base, token)


class RuntimeSettings:
    """Private local store with the contract's exact token key; no secret repr."""
    def __init__(self, path: Path = Path("data/providers/meterless.json")):
        self.path = path

    def load(self) -> Connection:
        if not self.path.exists():
            return Connection(DEFAULT_BASE_URL)
        try:
            values = json.loads(self.path.read_text())
            return parse_connection(values.get(BASE_KEY, DEFAULT_BASE_URL), values.get(TOKEN_KEY, ""))
        except (OSError, ValueError, TypeError, AttributeError):
            raise MeterlessError("Cannot load private Runtime settings") from None

    def save(self, connection: Connection):
        connection = parse_connection(connection.base_url, connection.token)
        if connection.token == "rt-local":
            raise MeterlessError("rt-local is a rejected placeholder; paste the real Runtime token")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(dir=self.path.parent, prefix=".meterless-")
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump({BASE_KEY:connection.base_url, TOKEN_KEY:connection.token}, stream)
                stream.write("\n")
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def from_state_dir(self, state_dir: Path, address: str = DEFAULT_BASE_URL) -> Connection:
        try:
            token = (state_dir.expanduser() / "proxy-token").read_text().strip()
        except (OSError, UnicodeError):
            raise MeterlessError("Cannot read proxy-token from the supplied Runtime stateDir") from None
        if not token or token == "rt-local":
            raise MeterlessError("proxy-token is empty or contains the rejected placeholder")
        connection = parse_connection(address, token)
        self.save(connection)
        return connection


class MeterlessProvider:
    id = PROVIDER_ID
    name = PROVIDER_NAME
    default_base_url = DEFAULT_BASE_URL

    def __init__(self, connection: Connection, transport=None):
        self.connection = parse_connection(connection.base_url, connection.token)
        self.transport = transport

    def _headers(self, chat=False):
        # With no token, the Bearer scheme is deliberately incomplete: the actual
        # /models response decides availability; no invented/local token is used.
        headers = {"Authorization":"Bearer" + (" " + self.connection.token if self.connection.token else ""),
                   "meterless-app":APP_ID}
        if chat:
            headers["meterless-scope"] = "user"
        return headers

    def health(self, timeout=1.0) -> bool:
        try:
            with httpx.Client(transport=self.transport, timeout=timeout, follow_redirects=False, trust_env=False) as client:
                response = client.get(self.connection.base_url.removesuffix("/v1") + "/healthz", headers=self._headers())
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    def probe(self, timeout=1.0) -> ProviderStatus:
        try:
            with httpx.Client(transport=self.transport, timeout=timeout, follow_redirects=False, trust_env=False) as client:
                response = client.get(self.connection.base_url + "/models", headers=self._headers())
            if response.status_code in (401,403):
                return ProviderStatus("unauthorized")
            if response.status_code != 200:
                return ProviderStatus("offline")
            payload = response.json()
            data = payload.get("data") if isinstance(payload, dict) else None
            if not isinstance(data, list):
                return ProviderStatus("offline")
            models = tuple(dict.fromkeys(item["id"] for item in data if isinstance(item,dict)
                and isinstance(item.get("id"),str) and item["id"].startswith("meterless/")))
            if self.connection.token == "rt-local":
                return ProviderStatus("unauthorized")
            return ProviderStatus("online", models) if models else ProviderStatus("offline")
        except (httpx.HTTPError, ValueError):
            return ProviderStatus("offline")

    def chat(self, text: str, model: str = "meterless/auto", *, max_tokens: int | None = None) -> str:
        if not isinstance(text,str):
            raise MeterlessError("Plain text input must be a string")
        if not isinstance(model,str) or not model.startswith("meterless/"):
            raise MeterlessError("Select a meterless/* routing mode from Runtime discovery")
        if not self.connection.token or self.connection.token == "rt-local":
            raise MeterlessError("unauthorized: paste the real Runtime token")
        body={"model":model,"messages":[{"role":"user","content":text}],"stream":False}
        if max_tokens is not None:
            if isinstance(max_tokens,bool) or not isinstance(max_tokens,int) or max_tokens < 1:
                raise MeterlessError("max_tokens must be a positive integer")
            body["max_tokens"]=max_tokens
        try:
            with httpx.Client(transport=self.transport, timeout=CHAT_TIMEOUT, follow_redirects=False, trust_env=False) as client:
                response = client.post(self.connection.base_url + "/chat/completions", headers=self._headers(chat=True),
                    json=body)
            if response.status_code in (401,403):
                raise MeterlessError("unauthorized: paste the real Runtime token")
            if response.status_code != 200:
                raise MeterlessError(f"Runtime chat failed: HTTP {response.status_code}; response omitted")
            content = response.json()["choices"][0]["message"]["content"]
            if not isinstance(content,str):
                raise MeterlessError("Runtime response content was not a string")
            return content
        except httpx.TimeoutException:
            raise MeterlessError("Runtime chat timed out after 180 seconds; private details omitted") from None
        except httpx.HTTPError:
            raise MeterlessError("Runtime chat connection failed; private details omitted") from None
        except (ValueError, KeyError, TypeError, IndexError):
            raise MeterlessError("Runtime returned an invalid OpenAI chat response; private details omitted") from None


def auto_detect(settings: RuntimeSettings, token: str = "", transport=None, timeout=1.0):
    """Save the first real /models online OR unauthorized response, not healthz."""
    for port in (8088,8090,8787,11434):
        for host in ("127.0.0.1","localhost","[::1]"):
            connection = parse_connection(f"http://{host}:{port}",token)
            status = MeterlessProvider(connection,transport).probe(timeout)
            if status.state in ("online","unauthorized"):
                # A rejected placeholder is never persisted as a real token.
                saved = Connection(connection.base_url,"" if token=="rt-local" else token)
                settings.save(saved)
                return saved,status
    return None,ProviderStatus("offline")
