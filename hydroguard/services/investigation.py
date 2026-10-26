"""Typed shared API-facing orchestration over the existing evidence audit."""
from typing import Literal
from pydantic import Field, model_validator

from hydroguard.data.sample import source_registry
from hydroguard.evidence.models import (Record, ProjectClaim, EvidenceFinding, EvidenceSource,
                                       CriticDecision, GateResult, AuditResult)
from hydroguard.services.audit import run_sample_audit
from hydroguard.services.trace import RunTrace


class ClaimInput(Record):
    claim_id: str = Field(min_length=1, max_length=200)
    project_name: str = Field(min_length=1, max_length=500)
    text: str = Field(min_length=1, max_length=10000)

    @model_validator(mode="after")
    def nonblank(self):
        if not all(value.strip() for value in (self.claim_id, self.project_name, self.text)):
            raise ValueError("Claim fields cannot be blank")
        return self


class CaseContext(Record):
    stage: Literal["scoping", "consultation", "review"] = "consultation"
    community_notes: str = Field(default="", max_length=10000)


class RunRequest(Record):
    project_claim: ClaimInput
    domain: Literal["Water", "Land", "Air"]
    case_context: CaseContext
    evidence_references: tuple[str, ...] = Field(max_length=100)


class RunResponse(Record):
    run_id: str
    status: Literal["completed", "unresolved"]
    finding: EvidenceFinding
    citations: tuple[EvidenceSource, ...]
    critic: CriticDecision
    gate: GateResult
    community_question: str | None
    audit: AuditResult


class InvalidEvidenceReference(ValueError):
    pass


class InvestigationService:
    def run(self, request: RunRequest) -> RunResponse:
        trace = RunTrace()
        trace.emit("InvestigationService", "run_started", "started")
        try:
            registry = source_registry()
            if any(ref not in registry or registry[ref].domain != request.domain
                   or registry[ref].kind == "basis" for ref in request.evidence_references):
                raise InvalidEvidenceReference("Unknown, inapplicable, or non-project evidence reference")
            if request.evidence_references:
                selected = set(request.evidence_references)
                registry = {key: value for key, value in registry.items()
                            if key in selected or value.kind == "basis"}
            claim = ProjectClaim(**request.project_claim.model_dump(), domain=request.domain,
                                 citation_ids=request.evidence_references)
            result = run_sample_audit(claim, registry=registry, trace=trace)
            final = result.history[-1]
            question = result.consultation_question
            if question:
                question = f"During {request.case_context.stage}: {question}"
            response = RunResponse(run_id=trace.run_id,
                                   status="completed" if final.gate.passed else "unresolved",
                                   finding=final.finding, citations=result.sources,
                                   critic=final.critic, gate=final.gate,
                                   community_question=question, audit=result)
            trace.emit("InvestigationService", "run_finished", response.status)
            return response
        except Exception:
            trace.emit("InvestigationService", "run_failed", "failed")
            raise
