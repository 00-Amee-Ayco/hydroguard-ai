import json
import httpx
import pytest
from hydroguard.ai.meterless import Connection
from hydroguard.ai.nightshift_smoke import verify, SYNTHETIC_PROMPT

TOKEN = 'private-test-token'
ROUTE = 'meterless/nemotron'
CONNECTION = Connection('http://127.0.0.1:8088/v1', TOKEN)


def transport(status=200, body=None, route=ROUTE, model='nvidia/nemotron-test', content='Reject unsupported harm.', chat_status=200):
    calls = []
    def handle(request):
        calls.append(request)
        assert request.headers['authorization'] == 'Bearer ' + TOKEN
        assert request.headers['meterless-app'] == 'hydroguard'
        if request.method == 'GET':
            return httpx.Response(status, json=body if body is not None else {'data': [{'id': ROUTE}]})
        assert request.headers['meterless-scope'] == 'user'
        payload = json.loads(request.content)
        assert isinstance(payload['messages'][0]['content'], str)
        assert payload['messages'][0]['content'] == SYNTHETIC_PROMPT
        assert payload['model'] == route
        assert request.extensions['timeout']['read'] == 180
        return httpx.Response(chat_status, headers={'x-request-id': 'req-test-1'}, json={
            'model': model, 'choices': [{'message': {'content': content}}]})
    return httpx.MockTransport(handle), calls


def test_success_is_one_request_with_actual_identity():
    mock, calls = transport()
    result = verify(CONNECTION, transport=mock)
    assert result['nemotron_invocation'] == 'PASS'
    assert result['request_id'] == 'req-test-1'
    assert result['response_model'] == 'nvidia/nemotron-test'
    assert len(calls) == 2
    assert TOKEN not in json.dumps(result)
    assert 'Reject unsupported harm.' not in json.dumps(result)


@pytest.mark.parametrize('status,blocker', [(401,'unauthorized'), (403,'unauthorized'),
    (429,'rate_limited_no_automatic_retry'), (404,'unsupported_endpoint_or_route'),
    (500,'http_error_response_omitted')])
def test_discovery_errors(status, blocker):
    mock, calls = transport(status=status)
    result = verify(CONNECTION, transport=mock)
    assert result['connection'] == 'BLOCKED'
    assert result['blocker'] == blocker
    assert len(calls) == 1


@pytest.mark.parametrize('ids', [['meterless/auto'], ['nvidia/nemotron-embed-1b'], []])
def test_no_fallback_or_direct_vendor_call(ids):
    mock, calls = transport(body={'data': [{'id': x} for x in ids]})
    result = verify(CONNECTION, transport=mock)
    assert result['inference_attempts'] == 0
    assert result['nemotron_invocation'] == 'BLOCKED'
    assert len(calls) == 1


@pytest.mark.parametrize('model', ['meterless/nemotron','nvidia/other','nemotron', TOKEN])
def test_alias_or_wrong_model_does_not_verify_identity(model):
    mock, _ = transport(model=model)
    result = verify(CONNECTION, transport=mock)
    assert not result['identity_verified']
    assert result['nemotron_invocation'] == 'BLOCKED'
    assert TOKEN not in json.dumps(result)


def test_configured_route_must_be_discovered():
    mock, calls = transport()
    assert verify(CONNECTION, model='meterless/absent-nemotron', transport=mock)['inference_attempts'] == 0
    assert len(calls) == 1


@pytest.mark.parametrize('status', [401,403,429,404,500])
def test_chat_errors_never_retry(status):
    mock, calls = transport(chat_status=status)
    result = verify(CONNECTION, transport=mock)
    assert result['nemotron_invocation'] == 'BLOCKED'
    assert result['inference_http_status'] == status
    assert len(calls) == 2


@pytest.mark.parametrize('error,blocker', [(httpx.ConnectError('secret'), 'network_error_details_omitted'),
    (httpx.ReadTimeout('secret'), 'timeout_no_automatic_retry')])
def test_network_errors_redacted(error,blocker):
    def fail(request): raise error
    result = verify(CONNECTION, transport=httpx.MockTransport(fail))
    assert result['blocker'] == blocker
    assert 'secret' not in json.dumps(result)


def test_missing_token_does_not_call_network():
    def fail(request): raise AssertionError('must not send')
    assert verify(Connection(CONNECTION.base_url), transport=httpx.MockTransport(fail))['blocker'] == 'missing_credentials'


@pytest.mark.parametrize('body', [[], {'data': 'invalid'}])
def test_invalid_discovery(body):
    mock, _ = transport(body=body)
    assert verify(CONNECTION, transport=mock)['blocker'] == 'invalid_discovery_response'


def test_empty_output():
    mock, _ = transport(content=' ')
    assert verify(CONNECTION, transport=mock)['blocker'] == 'empty_or_nontext_output'


def test_discovered_vendor_id_still_calls_only_nightshift():
    route = 'nvidia/nemotron-test'
    mock, calls = transport(body={'data': [{'id': route}]}, route=route)
    result = verify(CONNECTION, model=route, transport=mock)
    assert result['nemotron_invocation'] == 'PASS'
    assert result['route_mismatch'] is False
    assert all(request.url.host == '127.0.0.1' for request in calls)


def test_vendor_route_mismatch_blocks():
    mock, _ = transport(body={'data': [{'id': 'nvidia/nemotron-requested'}]},
                        route='nvidia/nemotron-requested')
    assert verify(CONNECTION, transport=mock)['blocker'] == 'resolved_model_mismatch'


def test_configuration_explicit_local_loading_and_process_precedence(tmp_path, monkeypatch):
    from scripts.verify_nightshift_critic import load_configuration
    monkeypatch.chdir(tmp_path)
    for key in ('NIGHTSHIFT_BASE_URL', 'NIGHTSHIFT_API_KEY', 'METERLESS_RUNTIME_TOKEN', 'NIGHTSHIFT_MODEL'):
        monkeypatch.delenv(key, raising=False)
    (tmp_path / '.env').write_text('NIGHTSHIFT_API_KEY=env-token\nNIGHTSHIFT_MODEL=env-model\n')
    (tmp_path / '.env.local').write_text('NIGHTSHIFT_BASE_URL=http://localhost:8090/v1/models\nNIGHTSHIFT_API_KEY=local-token\nNIGHTSHIFT_MODEL=local-model\n')
    connection, model = load_configuration()
    assert connection.base_url == 'http://localhost:8090/v1'
    assert connection.token == 'local-token'
    assert model == 'local-model'
    monkeypatch.setenv('NIGHTSHIFT_API_KEY', 'process-token')
    monkeypatch.setenv('NIGHTSHIFT_MODEL', 'process-model')
    connection, model = load_configuration()
    assert connection.token == 'process-token'
    assert model == 'process-model'


def test_provider_auth_failure_classified_without_raw_details():
    def handle(request):
        if request.method == 'GET':
            return httpx.Response(200, json={'data': [{'id': ROUTE}]})
        return httpx.Response(502, json={'error': {'code': 'provider_auth_failed',
            'message': 'private provider details', 'meterless_detail': TOKEN}})
    result = verify(CONNECTION, transport=httpx.MockTransport(handle))
    assert result['runtime_error_code'] == 'provider_auth_failed'
    assert result['blocker'] == 'upstream_provider_authentication_or_model_access_failed'
    assert 'private provider details' not in json.dumps(result)
    assert TOKEN not in json.dumps(result)

@pytest.mark.parametrize('error,status,category', [
    ({'message':'nvidia_403: Authorization failed'},403,'provider_authentication_or_access_failed'),
    ({'meterless_detail':'{"status":429,"detail":"private-test-token"}'},429,'provider_rate_limited'),
    ({'message':'nvidia_404: model not found'},404,'provider_route_or_model_unavailable'),
    ({'message':'private-test-token timeout'},None,'provider_timeout'),
])
def test_sanitized_nested_provider_errors(error,status,category):
    from hydroguard.ai.nightshift_smoke import sanitized_error
    result = sanitized_error(httpx.Response(502,json={'error':error}))
    assert result['provider_error_category'] == category
    assert result.get('upstream_http_status') == status
    assert TOKEN not in json.dumps(result)
