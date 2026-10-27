"""Contract v4 transport simulations; real-runtime proof is a separate CLI check."""
import json
import stat
from pathlib import Path
import httpx
import pytest
from hydroguard.ai.meterless import (parse_connection, MeterlessProvider, RuntimeSettings,
    auto_detect, MeterlessError, TOKEN_KEY, BASE_KEY, APP_ID, CHAT_TIMEOUT)
from hydroguard.ai.providers import CHAT_PROVIDERS


@pytest.mark.parametrize("address", ["127.0.0.1:8088", "http://127.0.0.1:8088", "http://127.0.0.1:8088/v1",
    "127.0.0.1:8088/v1/chat/completions", "127.0.0.1:8088/v1/models", "127.0.0.1:8088/healthz",
    "127.0.0.1:8088/v1/v1", "127.0.0.1:8088/v1/v1/models/", "127.0.0.1:8088/v1/healthz"])
def test_address_normalization(address):
    assert parse_connection(address).base_url == "http://127.0.0.1:8088/v1"


def test_ipv6_https_and_connect_fragment():
    connection=parse_connection("https://[::1]:8787/connect#k=SECRET%2Bvalue")
    assert connection.base_url == "https://[::1]:8787/v1"
    assert connection.token == "SECRET+value"
    assert "SECRET" not in repr(connection)
    assert parse_connection("localhost:8090/v1").base_url == "http://localhost:8090/v1"


@pytest.mark.parametrize("address", ["ftp://host", "http://user:SECRET@host", "http://host/connect", "http://host/connect#k=x&k=y", "http://host/arbitrary", "http://host:invalid"])
def test_invalid_addresses_never_echo_input(address):
    with pytest.raises(MeterlessError) as exc:parse_connection(address)
    assert "SECRET" not in str(exc.value)


def transport(status=200, payload=None):
    def handle(req):
        assert req.headers["authorization"] == "Bearer SECRET"
        assert req.headers["meterless-app"] == APP_ID == "hydroguard"
        return httpx.Response(status,json=payload if payload is not None else {})
    return httpx.MockTransport(handle)


@pytest.mark.parametrize("status", [401,403])
def test_wrong_token_is_unauthorized_not_offline(status):
    provider=MeterlessProvider(parse_connection("localhost:8088","SECRET"),transport(status))
    result=provider.probe()
    assert result.state == "unauthorized" and result.requires_token


def test_models_keep_unknown_class_and_disposition_ids():
    ids=["meterless/auto","meterless/fast","meterless/deep","meterless/cheap","meterless/local","meterless/fusion",
         "meterless/coding", "meterless/coding.deep", "meterless/new-class.new-mode"]
    provider=MeterlessProvider(parse_connection("localhost:8088","SECRET"),transport(payload={"data":[{"id":i} for i in ids]+[{"id":"not-meterless"}]}))
    result=provider.probe()
    assert result.state == "online" and result.models == tuple(ids)


@pytest.mark.parametrize("payload", [{"data":[]},{"data":[{"id":"other-model"}]},{"data":"bad"},{}])
def test_non_runtime_models_are_offline(payload):
    assert MeterlessProvider(parse_connection("localhost:8088","SECRET"),transport(payload=payload)).probe().state == "offline"


def test_health_does_not_imply_online():
    provider=MeterlessProvider(parse_connection("localhost:8088","SECRET"),transport(payload={"status":"ok"}))
    assert provider.health() is True and provider.probe().state == "offline"


def test_chat_plain_text_and_180_second_timeout():
    text="  exact text\n"
    def handle(req):
        assert req.url.path == "/v1/chat/completions"
        assert req.headers["authorization"] == "Bearer SECRET"
        assert req.headers["meterless-app"] == "hydroguard"
        assert req.headers["meterless-scope"] == "user"
        assert req.extensions["timeout"]["read"] == CHAT_TIMEOUT == 180.0
        body=json.loads(req.content)
        assert body["model"] == "meterless/auto"
        assert body["messages"][0]["content"] == text
        assert isinstance(body["messages"][0]["content"],str)
        return httpx.Response(200,json={"choices":[{"message":{"content":"READY"}}]})
    assert MeterlessProvider(parse_connection("localhost:8088/v1","SECRET"),httpx.MockTransport(handle)).chat(text) == "READY"


@pytest.mark.parametrize("status", [401,403,500])
def test_chat_errors_do_not_leak_response_or_credentials(status):
    provider=MeterlessProvider(parse_connection("localhost:8088","SECRET"),transport(status,payload={"error":"SECRET"}))
    with pytest.raises(MeterlessError) as exc:provider.chat("private prompt")
    assert "SECRET" not in str(exc.value)
    if status in (401,403):assert "unauthorized" in str(exc.value)


def test_autodetect_order_and_save_first_unauthorized(tmp_path):
    calls=[]
    def handle(req):
        calls.append((req.url.host,req.url.port))
        assert req.url.path == "/v1/models"
        assert "authorization" in req.headers
        if req.url.host == "localhost" and req.url.port == 8090:return httpx.Response(403)
        raise httpx.ConnectError("private network detail",request=req)
    settings=RuntimeSettings(tmp_path/"private.json")
    found,status=auto_detect(settings,transport=httpx.MockTransport(handle))
    assert found.base_url == "http://localhost:8090/v1" and status.state == "unauthorized"
    assert calls == [("127.0.0.1",8088),("localhost",8088),("::1",8088),("127.0.0.1",8090),("localhost",8090)]
    assert settings.load().base_url == found.base_url


def test_autodetect_scans_all_contract_addresses(tmp_path):
    calls=[]
    def handle(req):
        calls.append((req.url.host,req.url.port));return httpx.Response(404)
    found,status=auto_detect(RuntimeSettings(tmp_path/"settings"),transport=httpx.MockTransport(handle))
    assert found is None and status.state == "offline"
    assert len(calls) == 12 and ("::1",11434) in calls
    assert not (tmp_path/"settings").exists()


def test_private_token_key_and_state_dir_import(tmp_path):
    state=tmp_path/"runtime";state.mkdir();(state/"proxy-token").write_text("SECRET\n")
    settings=RuntimeSettings(tmp_path/"config.json")
    connection=settings.from_state_dir(state)
    assert connection.token == "SECRET"
    stored=json.loads(settings.path.read_text())
    assert stored[TOKEN_KEY] == "SECRET" and "#k=" not in stored[BASE_KEY]
    assert stat.S_IMODE(settings.path.stat().st_mode) == 0o600
    assert CHAT_PROVIDERS["meterless"].name == "Meterless Runtime"


def test_connect_link_not_stored_or_logged(tmp_path,capsys):
    settings=RuntimeSettings(tmp_path/"config.json")
    settings.save(parse_connection("http://localhost:8088/connect#k=SECRET"))
    stored=json.loads(settings.path.read_text())
    assert stored[BASE_KEY] == "http://localhost:8088/v1"
    assert stored[TOKEN_KEY] == "SECRET"
    assert "SECRET" not in capsys.readouterr().out


def test_placeholder_is_rejected(tmp_path):
    settings=RuntimeSettings(tmp_path/"config.json")
    with pytest.raises(MeterlessError):settings.save(parse_connection("localhost:8088","rt-local"))
    with pytest.raises(MeterlessError,match="unauthorized"):
        MeterlessProvider(parse_connection("localhost:8088","rt-local")).chat("hello")


def test_chat_timeout_sanitized():
    def fail(req):raise httpx.ReadTimeout("SECRET",request=req)
    with pytest.raises(MeterlessError) as exc:
        MeterlessProvider(parse_connection("localhost:8088","SECRET"),httpx.MockTransport(fail)).chat("private")
    assert "SECRET" not in str(exc.value)


def test_ui_unauthorized_shows_masked_token_field(tmp_path,monkeypatch):
    from streamlit.testing.v1 import AppTest
    import hydroguard.ui.provider_settings as ui
    from hydroguard.ai.meterless import ProviderStatus
    monkeypatch.setattr(ui,"RuntimeSettings",lambda:RuntimeSettings(tmp_path/"ui-settings.json"))
    class Provider:
        def __init__(self,connection):pass
        def probe(self):return ProviderStatus("unauthorized")
    monkeypatch.setattr(ui,"MeterlessProvider",Provider)
    at=AppTest.from_file(str(Path(__file__).resolve().parents[1]/"app.py")).run()
    at.text_input[1].set_value("test-token")
    next(button for button in at.button if button.label=="Connect").click()
    at.run()
    assert not at.exception
    assert any("unauthorized" in element.value for element in at.warning)
    assert at.text_input[1].label == "Runtime token"
    assert at.text_input[1].proto.type == at.text_input[1].proto.PASSWORD


def test_bounded_smoke_keeps_content_a_string():
    def handle(req):
        payload=json.loads(req.content)
        assert payload["max_tokens"] == 16
        assert isinstance(payload["messages"][0]["content"],str)
        return httpx.Response(200,json={"choices":[{"message":{"content":"READY"}}]})
    provider=MeterlessProvider(parse_connection("localhost:8088","SECRET"),httpx.MockTransport(handle))
    assert provider.chat("hello",max_tokens=16) == "READY"
