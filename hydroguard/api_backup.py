"""Judge-runnable offline FastAPI interface."""
import os
from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from hydroguard.services.audit import LiveModeUnavailable
from hydroguard.data.zetaris import (
    ZetarisRetrievalError,
    ZetarisConfigurationError,
    ZetarisEvidenceRetriever,
    TERMS,
)
from hydroguard.services.investigation import (InvestigationService, InvalidEvidenceReference,
                                               RunRequest, RunResponse)
import re
from hydroguard.evidence.models import ProjectClaim

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


@app.get("/evidence/search")
def search_regulatory_evidence(
    query: str = Query(min_length=2, max_length=120),
    domain: str = Query(default="Water"),
):
    """Search genuine regulatory passages through live Zetaris."""

    if os.environ.get("SAMPLE_MODE", "true").lower() == "true":
        raise HTTPException(
            status_code=409,
            detail="Live search requires SAMPLE_MODE=false",
        )

    if domain not in TERMS:
        raise HTTPException(
            status_code=422,
            detail="Unsupported environmental domain",
        )

    if not re.fullmatch(r"[a-zA-Z\s-]+", query):
        raise HTTPException(
            status_code=422,
            detail="Use letters, spaces and hyphens only",
        )

    words = set(re.findall(r"[a-z]+", query.lower()))
    recognized = sorted(words.intersection(TERMS[domain]))

    if not recognized:
        raise HTTPException(
            status_code=422,
            detail="No supported search topics were found",
        )

    claim = ProjectClaim(
        claim_id="knowledge-explorer",
        project_name="Knowledge Explorer",
        text=" ".join(recognized),
        domain=domain,
        citation_ids=(),
    )

    try:
        retriever = ZetarisEvidenceRetriever.from_environment()
        sources = retriever.retrieve(claim)

    except ZetarisConfigurationError:
        raise HTTPException(
            status_code=503,
            detail="Live Zetaris configuration unavailable",
        ) from None

    except ZetarisRetrievalError:
        raise HTTPException(
            status_code=502,
            detail="Live Zetaris search failed",
        ) from None

    results = [
        source.model_dump(mode="json")
        for source in sources.values()
        if source.source_type == "regulatory"
    ]

    return {
        "origin": "live_zetaris",
        "domain": domain,
        "supported_terms_used": recognized,
        "result_count": len(results),
        "results": results,
    }
