"""Typed shared API-facing orchestration over the existing evidence audit."""
import os
from typing import Literal
from pydantic import Field, model_validator

from hydroguard.data.sample import source_registry
from hydroguard.evidence.models import (Record, ProjectClaim, EvidenceFinding, EvidenceSource,
                                       CriticDecision, GateResult, AuditResult)
from hydroguard.services.audit import run_sample_audit, LiveModeUnavailable
from hydroguard.agents.investigator import EvidenceInvestigator
from hydroguard.data.zetaris import ZetarisEvidenceRetriever, ZetarisConfigurationError
from hydroguard.evidence.gate import evaluate_finding
from hydroguard.evidence.models import EvidenceStrength, RevisionRecord
from hydroguard.services.trace import RunTrace
from hydroguard.cases.water_case import unresolved_water_finding


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
    critic: CriticDecision | None
    gate: GateResult
    community_question: str | None
    audit: AuditResult


class InvalidEvidenceReference(ValueError):
    pass


class InvestigationService:
    def __init__(self, live_retriever_factory=None):
        self.live_retriever_factory = live_retriever_factory or ZetarisEvidenceRetriever.from_environment

    def _run_live(self, request: RunRequest, trace: RunTrace) -> RunResponse:
        try:
            retriever = self.live_retriever_factory(trace)
        except ZetarisConfigurationError:
            trace.mode = "live_unavailable"
            raise LiveModeUnavailable("Live Zetaris configuration unavailable; no sample fallback") from None
        trace.mode = "live_zetaris"
        claim = ProjectClaim(**request.project_claim.model_dump(), domain=request.domain, citation_ids=())
        trace.emit("Case Planner", "plan_regulatory_retrieval", handoff="Evidence Investigator")
        sources = EvidenceInvestigator(retriever).investigate(claim)
        if any(reference not in sources for reference in request.evidence_references):
            raise InvalidEvidenceReference("Requested reference not found in live retrieval")
        regulatory_ids = tuple(source.source_id for source in sources.values() if source.source_type == "regulatory")
        trace.emit("Evidence Investigator", "consumed_regulatory_records" if regulatory_ids else "regulatory_retrieval_empty",
                   source_ids=regulatory_ids, row_count=len(regulatory_ids), handoff="Deterministic Evidence Gate")
        project_ids = tuple(source.source_id for source in sources.values() if source.kind == "project")
        claim = claim.model_copy(update={"citation_ids": project_ids})
        finding = unresolved_water_finding(claim, sources)
        if project_ids:
            trace.emit("Evidence Investigator", "consumed_project_disclosure", source_ids=project_ids,
                       row_count=len(project_ids))
        trace.emit("Evidence Investigator", "regulatory_applicability_unresolved", decision="expert_review_required")
        gate = evaluate_finding(finding, None, sources, {}, claim)
        trace.emit("Deterministic Evidence Gate", "validate_finding", source_ids=tuple(sources), passed=gate.passed)
        trace.emit("Case Planner", "branch_decision", decision="unresolved")
        audit = AuditResult(mode="Live Zetaris / unresolved",
            execution="live Zetaris retrieval only; no live Critic or World Model", claim=claim,
            sources=tuple(sources.values()), assessment_bases=(),
            history=(RevisionRecord(finding=finding, critic=None, gate=gate),), consultation_question=None)
        response = RunResponse(run_id=trace.run_id, status="unresolved", finding=finding,
            citations=tuple(sources.values()), critic=None, gate=gate, community_question=None, audit=audit)
        trace.emit("InvestigationService", "run_finished", "unresolved")
        return response

    def run(self, request: RunRequest) -> RunResponse:
        trace = RunTrace()
        trace.emit("InvestigationService", "run_started", "started")
        try:
            if os.environ.get("SAMPLE_MODE", "true").lower() != "true":
                return self._run_live(request, trace)
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
