#!/usr/bin/env python3
"""Standalone, read-only direct REST probe. No audit/API integration or sample fallback.

Protocol: https://github.com/zetaris/getting-started/blob/main/scripts/zetaris_sql.py
Configuration: docs/connections/client-setup.md in that official repository.
"""
import argparse
from dataclasses import dataclass, field
import json
import math
import os
from pathlib import Path
import shlex
import socket
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen, build_opener, HTTPRedirectHandler
from uuid import uuid4


class SmokeError(RuntimeError):
    """Only constant, sanitized messages may be included in this exception."""


@dataclass(frozen=True)
class Config:
    base_url: str = field(repr=False)
    api_key: str = field(repr=False)
    org_id: str = field(repr=False)
    timeout: float = 10.0

    @classmethod
    def load(cls, env_file: Path, environ=None, timeout: float = 10.0):
        values = {}
        if env_file.is_file():
            try:
                for line in env_file.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if line.startswith("export "):
                        line = line[7:]
                    key, separator, value = line.partition("=")
                    if not separator:
                        raise SmokeError("Invalid environment file: expected KEY=value.")
                    parts = shlex.split(value, comments=True)
                    values[key.strip()] = " ".join(parts)
            except (OSError, UnicodeError, ValueError):
                raise SmokeError("Cannot parse the selected environment file; values omitted.") from None
        values.update(os.environ if environ is None else environ)
        required = ("ZETARIS_REST_URL", "ZETARIS_API_KEY", "ZETARIS_ORG_ID")
        missing = [name for name in required if not values.get(name, "").strip()]
        if missing:
            raise SmokeError("Missing required configuration: " + ", ".join(missing))
        base = values["ZETARIS_REST_URL"].rstrip("/")
        try:
            url = urlsplit(base)
            valid = (url.scheme in ("http", "https") and url.hostname and not url.username
                     and not url.password and not url.query and not url.fragment
                     and url.path == "/api/v1.0" and url.port != 8889)
        except ValueError:
            valid = False
        if not valid:
            raise SmokeError("ZETARIS_REST_URL must be an HTTP(S) API base ending /api/v1.0, without credentials/query/fragment; port 8889 is prohibited.")
        org = values["ZETARIS_ORG_ID"]
        if not org.isascii() or not org.isdigit():
            raise SmokeError("ZETARIS_ORG_ID must be a numeric organisation ID.")
        if not math.isfinite(timeout) or not 0 < timeout <= 60:
            raise SmokeError("Timeout must be greater than zero and at most 60 seconds.")
        key = values["ZETARIS_API_KEY"]
        if any(c in key for c in ("\r", "\n")):
            raise SmokeError("Invalid API key format; value omitted.")
        return cls(base, key, org, timeout)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Do not forward bearer credentials to a redirect target.
        return None


def smoke(config: Config, opener=None) -> dict:
    opener = opener or build_opener(NoRedirect()).open
    result = {"connected": False, "authentication": "unverified", "protocol": "direct_rest",
              "metadata": "not_attempted", "query": "SELECT 1", "query_status": "not_attempted"}

    def request(path, body=None):
        headers = {"Authorization": "Bearer " + config.api_key,
                   "X-Org-ID": config.org_id, "X-Request-ID": str(uuid4()),
                   "Content-Type": "application/json"}
        req = Request(config.base_url + path, headers=headers,
                      data=None if body is None else json.dumps(body).encode(),
                      method="GET" if body is None else "POST")
        try:
            with opener(req, timeout=config.timeout) as response:
                if response.status != 200:
                    raise SmokeError("Unexpected HTTP status; response body omitted.")
                raw = response.read(2_000_001)
                if len(raw) > 2_000_000:
                    raise SmokeError("Response exceeds the smoke-test size limit.")
                return json.loads(raw)
        except HTTPError as error:
            if error.code == 401:
                result["authentication"] = "rejected"
            elif error.code == 403:
                result["authentication"] = "access_denied"
            raise SmokeError(f"HTTP {error.code}; response body omitted. Check key, organisation ID, permissions and API route.") from None
        except (TimeoutError, socket.timeout):
            raise SmokeError("Request timed out; connectivity is unverified.") from None
        except URLError as error:
            if isinstance(error.reason, (TimeoutError, socket.timeout)):
                raise SmokeError("Request timed out; connectivity is unverified.") from None
            raise SmokeError("Connection failed (DNS, refused connection, TLS or network restriction); endpoint and credentials omitted.") from None
        except OSError:
            raise SmokeError("Connection failed; endpoint and credentials omitted.") from None
        except (ValueError, UnicodeError):
            raise SmokeError("Response was not valid JSON; response body omitted.") from None

    try:
        metadata = request("/datasource/datasources")
        if not isinstance(metadata, list) and not (isinstance(metadata, dict) and isinstance(metadata.get("data"), list)):
            raise SmokeError("Unexpected datasource response shape; no connectivity success claimed.")
        result["metadata"] = "HTTP 200"
        result["authentication"] = "metadata_request_accepted"
        result["query_status"] = "attempted"
        response = request("/sql-editor/sqls/run", {"queryId": str(uuid4()), "sql": "SELECT 1",
                           "source": "SqlEditor", "limit": 1})
        rows = response.get("data") if isinstance(response, dict) else None
        if rows != [[1]] and rows != [["1"]]:
            raise SmokeError("SELECT 1 did not return the documented one-row result; response omitted.")
        result.update(connected=True, authentication="verified_by_query", query_status="passed", rows=rows)
    except SmokeError as error:
        if result["query_status"] == "attempted":
            result["query_status"] = "failed"
        result["error"] = str(error)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=Path(__file__).resolve().parents[1] / ".env.local")
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args(argv)
    try:
        result = smoke(Config.load(args.env_file, timeout=args.timeout))
    except SmokeError as error:
        result = {"connected": False, "authentication": "not_attempted", "error": str(error)}
    print(json.dumps(result, indent=2))
    return 0 if result["connected"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
