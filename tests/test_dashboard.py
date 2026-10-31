import json
from pathlib import Path
import httpx
import pytest
from streamlit.testing.v1 import AppTest
from fastapi.testclient import TestClient
from hydroguard.api import app
from hydroguard.ui.client import AuditClient, BackendError
from hydroguard.ui.dashboard import brief, display
from hydroguard.services.investigation import RunRequest,RunResponse

ROOT=Path(__file__).resolve().parents[1]

class ActualBackend:
    def health(self):return {'mode':'sample'}
    def run(self,request):
        with TestClient(app) as c:
            response=c.post('/run',json=request.model_dump(mode='json'))
        assert response.status_code==200
        return RunResponse.model_validate(response.json())


def test_complete_water_ui_flow(monkeypatch):
    monkeypatch.setenv('SAMPLE_MODE','true')
    monkeypatch.setattr('hydroguard.ui.dashboard.AuditClient',ActualBackend)
    at=AppTest.from_file(str(ROOT/'app.py')).run()
    assert not at.exception
    next(b for b in at.button if b.label=='Run Evidence Audit').click().run()
    assert not at.exception
    assert at.session_state['result'].gate.passed
    for page in ('Investigation results','Evidence explorer','Consultation brief'):
        at.sidebar.radio[0].set_value(page).run()
        assert not at.exception
    assert 'dry-season' in brief(at.session_state['result'])


def test_ui_backend_failure(monkeypatch):
    class Failed:
        def health(self):raise BackendError('Backend unavailable')
    monkeypatch.setattr('hydroguard.ui.dashboard.AuditClient',Failed)
    at=AppTest.from_file(str(ROOT/'app.py')).run()
    assert not at.exception
    assert at.error[0].value=='Backend unavailable'


@pytest.mark.parametrize('status',[422,500,502,503])
def test_client_http_errors_do_not_echo_payload(status):
    client=AuditClient(transport=httpx.MockTransport(lambda r:httpx.Response(status,json={'secret':'PRIVATE'})))
    with pytest.raises(BackendError) as error:client.health()
    assert 'PRIVATE' not in str(error.value)


def test_client_empty_and_timeout():
    request=RunRequest.model_validate(json.loads((ROOT/'input_examples/water.json').read_text()))
    client=AuditClient(transport=httpx.MockTransport(lambda r:httpx.Response(200,json={})))
    with pytest.raises(BackendError):client.run(request)
    def fail(r):raise httpx.ReadTimeout('PRIVATE')
    with pytest.raises(BackendError,match='timed out'):AuditClient(transport=httpx.MockTransport(fail)).health()


def test_brief_rejected_and_redaction(monkeypatch):
    monkeypatch.setenv('SAMPLE_MODE','true')
    result=ActualBackend().run(RunRequest.model_validate(json.loads((ROOT/'input_examples/water.json').read_text())))
    result=result.model_copy(update={"gate":result.gate.model_copy(update={"passed":False})})
    text=brief(result)
    assert 'UNRESOLVED' in text
    assert 'No gate-approved question' in text
    assert 'nvapi-secret' not in display('nvapi-secret /Users/private/doc.pdf')
    assert '/Users/' not in display('/Users/private/doc.pdf')
