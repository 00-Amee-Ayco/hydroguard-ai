"""Transport simulations test the probe contract; they do not prove live integration."""
import io
import json
import socket
from urllib.error import HTTPError, URLError
from uuid import UUID

import pytest
from scripts.zetaris_smoke import Config, NoRedirect, SmokeError, main, smoke


ENV = {"ZETARIS_REST_URL": "https://instance.test/api/v1.0", "ZETARIS_API_KEY": "SECRET",
       "ZETARIS_ORG_ID": "1"}


def config(tmp_path, values=None, timeout=10):
    return Config.load(tmp_path / "absent", environ=ENV if values is None else values, timeout=timeout)


class Response(io.BytesIO):
    status = 200


def test_documented_protocol_and_success(tmp_path):
    calls = []
    def opener(req, timeout):
        calls.append(req)
        assert timeout == 10
        assert req.get_header("Authorization") == "Bearer SECRET"
        assert req.get_header("X-org-id") == "1"
        UUID(req.get_header("X-request-id"))
        if req.method == "GET":
            assert req.full_url.endswith("/datasource/datasources")
            return Response(b"[]")
        body = json.loads(req.data)
        assert req.full_url.endswith("/sql-editor/sqls/run")
        assert body["sql"] == "SELECT 1" and body["limit"] == 1 and body["source"] == "SqlEditor"
        UUID(body["queryId"])
        return Response(b'{"data":[["1"]]}')
    result = smoke(config(tmp_path), opener)
    assert result["connected"] and result["rows"] == [["1"]]
    assert result["authentication"] == "verified_by_query"
    assert len(calls) == 2
    assert calls[0].get_header("X-request-id") != calls[1].get_header("X-request-id")
    assert "SECRET" not in json.dumps(result)


@pytest.mark.parametrize("missing", ENV)
def test_missing_credentials_explicit(tmp_path, missing):
    values = {k: v for k, v in ENV.items() if k != missing}
    with pytest.raises(SmokeError, match=missing):
        config(tmp_path, values)


@pytest.mark.parametrize("code,auth", [(401,"rejected"), (403,"access_denied"), (500,"unverified")])
def test_http_errors_redacted(tmp_path, code, auth):
    def opener(req, timeout):
        raise HTTPError(req.full_url, code, "SECRET", {}, io.BytesIO(b"SECRET"))
    result = smoke(config(tmp_path), opener)
    assert not result["connected"]
    assert result["authentication"] == auth
    assert f"HTTP {code}" in result["error"]
    assert "SECRET" not in json.dumps(result)


@pytest.mark.parametrize("error", [socket.timeout("SECRET"), URLError(socket.timeout()), URLError("SECRET"), OSError("SECRET")])
def test_network_failures_redacted(tmp_path, error):
    def opener(*args, **kwargs):
        raise error
    result = smoke(config(tmp_path), opener)
    assert not result["connected"]
    assert "SECRET" not in json.dumps(result)


def test_unexpected_sql_result_is_not_success(tmp_path):
    responses = iter([b"[]", b'{"data":[]}'])
    result = smoke(config(tmp_path), lambda *a, **k: Response(next(responses)))
    assert not result["connected"]
    assert result["query_status"] == "failed"


def test_no_redirect_credential_forwarding():
    assert NoRedirect().redirect_request(None, None, 302, "", {}, "https://other.test") is None


@pytest.mark.parametrize("url", ["https://user:SECRET@test/api/v1.0", "http://localhost:8889/api/v1.0", "https://test/api/v1.0?token=SECRET"])
def test_unsafe_url_refused(tmp_path, url):
    with pytest.raises(SmokeError) as exc:
        config(tmp_path, {**ENV, "ZETARIS_REST_URL": url})
    assert "SECRET" not in str(exc.value)


def test_env_loading_no_secret_prints(tmp_path, monkeypatch, capsys):
    for key in ENV:
        monkeypatch.delenv(key, raising=False)
    path = tmp_path / ".env.local"
    path.write_text('export ZETARIS_API_KEY="SECRET"\n')
    assert main(["--env-file", str(path)]) == 1
    assert "SECRET" not in capsys.readouterr().out
    assert "SECRET" not in repr(config(tmp_path))


@pytest.mark.parametrize("value", [0, -1, 61, float("nan")])
def test_invalid_timeout(tmp_path, value):
    with pytest.raises(SmokeError, match="Timeout"):
        config(tmp_path, timeout=value)
