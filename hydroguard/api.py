"""Judge-runnable offline FastAPI interface."""
import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from hydroguard.services.audit import LiveModeUnavailable
from hydroguard.data.zetaris import ZetarisRetrievalError
from hydroguard.services.investigation import (InvestigationService, InvalidEvidenceReference,
                                               RunRequest, RunResponse)

app = FastAPI(title="HydroGuard", description="Sample audit or live Zetaris regulatory retrieval; no live AI inference.")
service = InvestigationService()


@app.exception_handler(RequestValidationError)
async def invalid_request(request: Request, exc: RequestValidationError):
    # FastAPI's default errors may echo private request values. Omit inputs/messages.
    return JSONResponse(status_code=422, content={"detail": "Invalid request", "errors": [
        {"type": error["type"]} for error in exc.errors()]})


@app.get("/health")
def health():
    offline = os.environ.get("SAMPLE_MODE", "true").lower() == "true"
    return {"status": "ok", "mode": "sample" if offline else "live_retrieval_only",
            "execution_available": offline, "sponsor_integrations_verified": False}


@app.post("/run", response_model=RunResponse)
def run(request: RunRequest):
    try:
        return service.run(request)
    except InvalidEvidenceReference:
        raise HTTPException(status_code=422, detail="Unknown or inapplicable evidence reference") from None
    except LiveModeUnavailable:
        raise HTTPException(status_code=503, detail="Live Zetaris configuration is unavailable; check local configuration") from None
    except ZetarisRetrievalError:
        raise HTTPException(status_code=502, detail="Live Zetaris retrieval failed; no sample fallback") from None
    except Exception:
        raise HTTPException(status_code=500, detail="Investigation failed; consult the sanitized run trace") from None
