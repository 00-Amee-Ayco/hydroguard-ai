"""Typed, immutable records for the offline evidence-auditing slice."""
from enum import Enum
from hashlib import sha256
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EvidenceStrength(str, Enum):
    STRONG = "Strong"
    MODERATE = "Moderate"
    WEAK = "Weak"
    INSUFFICIENT = "Insufficient"


class EvidenceSource(Record):
    source_id: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    document_title: str = Field(min_length=1)
    page: int = Field(ge=1)
    chunk_id: str = Field(min_length=1)
    provenance: Literal["project-supplied", "government", "research", "synthetic"]
    text: str = Field(min_length=1)
    domain: Literal["Water", "Land", "Air", "People"] = "Water"
    kind: Literal["project", "evidence", "basis"] = "project"
    evidence_items: tuple[str, ...] = ()
    is_synthetic: bool | None = None
    case_id: str | None = None
    source_type: str | None = None
    original_filename: str | None = None
    locator: str | None = None
    issuing_body_or_author: str | None = None
    publication_or_effective_date: str | None = None
    original_source_url: str | None = None


class ProjectClaim(Record):
    claim_id: str
    project_name: str
    domain: Literal["Water", "Land", "Air", "People"]
    text: str
    citation_ids: tuple[str, ...]


class AssessmentBasis(Record):
    basis_id: str
    text: str
    citation_ids: tuple[str, ...]
    limitation: str
    domain: Literal["Water", "Land", "Air", "People"] = "Water"
    required_items: tuple[str, ...] = ()


class EvidenceFinding(Record):
    finding_id: str
    claim_id: str
    revision: int = Field(ge=1)
    text: str
    claim_type: Literal["evidence_gap", "evidence_summary", "definitive_harm", "illegality"]
    strength: EvidenceStrength
    citation_ids: tuple[str, ...] = ()
    assessment_basis_ids: tuple[str, ...] = ()
    gaps: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()

    def fingerprint(self) -> str:
        return sha256(self.model_dump_json().encode()).hexdigest()


class CriticDecision(Record):
    finding_id: str
    revision: int = Field(ge=1)
    finding_fingerprint: str
    decision: Literal["approve", "narrow", "reject", "reinvestigate"]
    reason: str
    evidence_fingerprint: str = ""
    response_origin: Literal["offline_rule_based"] = "offline_rule_based"
    live_inference: Literal[False] = False
    model_identity: Literal["unverified; no model invoked"] = "unverified; no model invoked"


class GateResult(Record):
    finding_id: str
    revision: int
    passed: bool
    reasons: tuple[str, ...]


class RevisionRecord(Record):
    finding: EvidenceFinding
    critic: CriticDecision | None
    gate: GateResult


class AuditResult(Record):
    mode: Literal["Sample / Synthetic", "Live Zetaris / unresolved"] = "Sample / Synthetic"
    execution: Literal["input-dependent offline rules; no live AI or sponsor services", "live Zetaris retrieval only; no live Critic or World Model"] = (
        "input-dependent offline rules; no live AI or sponsor services"
    )
    claim: ProjectClaim
    sources: tuple[EvidenceSource, ...]
    assessment_bases: tuple[AssessmentBasis, ...]
    history: tuple[RevisionRecord, ...]
    consultation_question: str | None
