"""Isolated, fail-closed Nightshift probe. Never used by InvestigationService."""
import re
import httpx
from hydroguard.ai.meterless import Connection, MeterlessProvider, CHAT_TIMEOUT

SYNTHETIC_PROMPT = (
    'An EIA project disclosure says water demand will not affect existing users, '
    'but lacks dry-season water balance data. Is a definite water-shortage '
    'conclusion supported? Explain briefly.'
)



def safe_id(value, token):
    """Metadata only; never echo arbitrary bodies, links or a credential substring."""
    if (isinstance(value, str) and 0 < len(value) <= 200
            and re.fullmatch(r'[A-Za-z0-9_./:\-]+', value)
            and not (token and token in value)):
        return value
    return None


def sanitized_error(response):
    """Classify private error data into fixed labels; never return body fragments."""
    try:
        body = response.json()
    except ValueError:
        return {'provider_error_category': 'unclassified_non_json_error'}
    error = body.get('error', body) if isinstance(body, dict) else body
    # The text is inspected privately, not emitted. Some builds nest upstream
    # details in a JSON string rather than a structured error.code field.
    import json
    text = json.dumps(error).lower()
    result = {'provider_error_category': 'unclassified_provider_error'}
    match = re.search(r'nvidia[_ :/-]+(401|403|404|429|500|502|503|504)\b', text)
    if not match:
        match = re.search(r'\\?"status\\?"\s*:\s*(401|403|404|429|500|502|503|504)\b', text)
    if match:
        result['upstream_http_status'] = int(match.group(1))
    if 'provider_auth_failed' in text or 'authorization failed' in text:
        result.update(provider_error_category='provider_authentication_or_access_failed',
                      runtime_error_code='provider_auth_failed')
    elif 'rate_limit' in text or result.get('upstream_http_status') == 429:
        result['provider_error_category'] = 'provider_rate_limited'
    elif 'not found' in text or 'unknown model' in text:
        result['provider_error_category'] = 'provider_route_or_model_unavailable'
    elif 'timeout' in text or 'timed out' in text:
        result['provider_error_category'] = 'provider_timeout'
    return result


def verify(connection: Connection, model=None, transport=None):
    result = dict(connection='BLOCKED', nemotron_invocation='BLOCKED',
                  discovery_http_status=None, inference_http_status=None,
                  request_id=None, response_model=None, identity_verified=False,
                  nonempty_output=False, inference_attempts=0,
                  contract='OpenAI-compatible GET /v1/models; POST /v1/chat/completions')
    token = connection.token
    if not token or token == 'rt-local':
        return result | {'blocker': 'missing_credentials'}
    provider = MeterlessProvider(connection, transport)
    try:
        with httpx.Client(transport=transport, timeout=CHAT_TIMEOUT, trust_env=False,
                          follow_redirects=False) as client:
            response = client.get(provider.connection.base_url + '/models',
                                  headers=provider._headers(), timeout=15)
            result['discovery_http_status'] = response.status_code
            if response.status_code != 200:
                return result | {'blocker': http_blocker(response.status_code)}
            payload = response.json()
            rows = payload.get('data') if isinstance(payload, dict) else None
            if not isinstance(rows, list):
                return result | {'blocker': 'invalid_discovery_response'}
            ids = [row.get('id') for row in rows if isinstance(row, dict)
                   and safe_id(row.get('id'), token)]
            routes = [route for route in ids if route.startswith('meterless/')]
            result.update(connection='PASS', discovered_route_count=len(ids),
                          meterless_routes=routes)
            # These are IDs advertised by Nightshift, not direct provider URLs.
            # Exclude embedding models and never substitute a generic routing mode.
            candidates = [route for route in ids if 'nemotron' in route.lower()
                          and 'embed' not in route.lower()
                          and route.startswith(('meterless/', 'nvidia/'))]
            if model is not None:
                candidates = [route for route in candidates if route == model]
            if not candidates:
                return result | {'blocker': 'no_discovered_nemotron_inference_route'}
            route = sorted(candidates, key=lambda x: ('lightning' not in x, x))[0]
            result.update(selected_route=route, inference_attempts=1)
            response = client.post(provider.connection.base_url + '/chat/completions',
                headers=provider._headers(chat=True), json={
                    'model': route, 'messages': [{'role': 'user', 'content': SYNTHETIC_PROMPT}],
                    'stream': False, 'max_tokens': 256})
            result.update(inference_http_status=response.status_code,
                          request_id=safe_id(response.headers.get('x-request-id'), token))
            if response.status_code != 200:
                result.update(sanitized_error(response))
                if result.get('runtime_error_code') == 'provider_auth_failed':
                    return result | {'blocker': 'upstream_provider_authentication_or_model_access_failed'}
                return result | {'blocker': http_blocker(response.status_code)}
            body = response.json()
            result['response_model'] = safe_id(body.get('model'), token)
            result['route_mismatch'] = result['response_model'] != route
            if result['request_id'] is None:
                result['request_id'] = safe_id(body.get('id'), token)
            content = body['choices'][0]['message']['content']
            result['nonempty_output'] = isinstance(content, str) and bool(content.strip())
            result['response_summary'] = ('Response received; content omitted. Unsupported-conclusion rejection language detected.'
                if isinstance(content, str) and any(x in content.lower() for x in ('not supported', 'unsupported', 'no,', 'not justified', 'cannot'))
                else 'Response received; content omitted; semantic outcome not automatically established.')
            identity = result['response_model'] or ''
            # A reflected routing alias is not evidence of the actual winning model.
            result['identity_verified'] = (not identity.startswith('meterless/')
                and bool(re.match(r'^nvidia[/:].*nemotron', identity, re.I)))
            if not result['nonempty_output']:
                return result | {'blocker': 'empty_or_nontext_output'}
            if result['route_mismatch'] and not route.startswith('meterless/'):
                return result | {'blocker': 'resolved_model_mismatch'}
            if not result['identity_verified']:
                return result | {'blocker': 'actual_nvidia_nemotron_identity_unverified'}
            return result | {'nemotron_invocation': 'PASS', 'blocker': None}
    except httpx.TimeoutException:
        return result | {'blocker': 'timeout_no_automatic_retry'}
    except httpx.HTTPError:
        return result | {'blocker': 'network_error_details_omitted'}
    except (ValueError, KeyError, IndexError, TypeError, AttributeError):
        return result | {'blocker': 'invalid_api_response_details_omitted'}


def http_blocker(status):
    if status in (401, 403):
        return 'unauthorized'
    if status == 429:
        return 'rate_limited_no_automatic_retry'
    if status in (404, 405):
        return 'unsupported_endpoint_or_route'
    return 'http_error_response_omitted'
