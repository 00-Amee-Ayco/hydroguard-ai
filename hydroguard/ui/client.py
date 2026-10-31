"""HTTP presentation adapter only; all investigation logic remains in /run."""
import os
from urllib.parse import urlsplit
import httpx
from pydantic import ValidationError
from hydroguard.services.investigation import RunRequest, RunResponse

class BackendError(RuntimeError):
    pass

class AuditClient:
    def __init__(self, base_url=None, transport=None):
        self.base = (base_url or os.getenv('HYDROGUARD_API_URL', 'http://127.0.0.1:8000')).rstrip('/')
        parsed = urlsplit(self.base)
        if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise BackendError('Invalid backend address. Configure HYDROGUARD_API_URL without credentials.')
        self.transport = transport

    def request(self, method, path, **kwargs):
        try:
            with httpx.Client(timeout=60, transport=self.transport, follow_redirects=False, trust_env=False) as client:
                r = client.request(method, self.base + path, **kwargs)
            if r.status_code != 200:
                messages = {422:'The case input or evidence references were rejected.',
                            502:'Live retrieval failed. No sample evidence was substituted.',
                            503:'Live configuration is unavailable.'}
                raise BackendError(messages.get(r.status_code, 'The backend could not complete this request.'))
            return r.json()
        except httpx.TimeoutException:
            raise BackendError('The backend timed out. Check its status before running again.') from None
        except (httpx.HTTPError, ValueError):
            raise BackendError('Cannot reach a valid backend response. Start the FastAPI server and check configuration.') from None

    def health(self):
        data = self.request('GET','/health')
        if not isinstance(data,dict) or data.get('mode') not in ('sample','live_retrieval_only'):
            raise BackendError('Backend health response is not recognized.')
        return data

    def run(self, request: RunRequest):
        try:
            return RunResponse.model_validate(self.request('POST','/run',json=request.model_dump(mode='json')))
        except ValidationError:
            raise BackendError('The backend returned an incomplete audit. No finding was published.') from None
