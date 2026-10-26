"""Small, deterministic evidence policy over curated offline source facts."""
import json
from hashlib import sha256
from collections.abc import Mapping
from hydroguard.evidence.models import AssessmentBasis, EvidenceFinding, EvidenceSource, EvidenceStrength, ProjectClaim

LIMITATION = "Only retrieved synthetic records were reviewed; missing evidence may exist elsewhere. No harm or legal determination is made."


def display_text(text: str) -> str:
    """Normalize presentation whitespace without changing the underlying record."""
    return " ".join(text.split())


def context_fingerprint(sources: Mapping[str, EvidenceSource],
                        bases: Mapping[str, AssessmentBasis], claim: ProjectClaim) -> str:
    payload = {"sources": {k: v.model_dump(mode="json") for k, v in sorted(sources.items())},
               "bases": {k: v.model_dump(mode="json") for k, v in sorted(bases.items())},
               "claim": claim.model_dump(mode="json")}
    return sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def derive_finding(claim: ProjectClaim, sources: Mapping[str, EvidenceSource],
                   bases: Mapping[str, AssessmentBasis], revision: int = 1) -> EvidenceFinding:
    applicable = [basis for basis in bases.values() if basis.domain == claim.domain]
    requirements = tuple(dict.fromkeys(item for basis in applicable for item in basis.required_items))
    evidence = [source for source in sources.values() if source.domain == claim.domain and source.kind != "basis"]
    present = {item for source in evidence for item in source.evidence_items}
    missing = tuple(item for item in requirements if item not in present)
    if not requirements:
        missing = ("applicable assessment criteria",)
    strength = (EvidenceStrength.INSUFFICIENT if not present else EvidenceStrength.WEAK) if missing else EvidenceStrength.MODERATE
    claim_text = display_text(claim.text)
    if missing:
        text = (f"The reviewed {claim.domain} evidence does not sufficiently substantiate the claim "
                f"{claim_text!r}; evidence not identified: {', '.join(missing)}.")
    else:
        text = (f"The reviewed {claim.domain} records document {', '.join(requirements)} for the claim "
                f"{claim_text!r}; this is an evidence inventory, not assurance of no impact.")
    return EvidenceFinding(finding_id=f"{claim.claim_id}-finding", claim_id=claim.claim_id,
                           revision=revision, text=display_text(text), claim_type="evidence_gap" if missing else "evidence_summary",
                           strength=strength, citation_ids=tuple(source.source_id for source in evidence),
                           assessment_basis_ids=tuple(basis.basis_id for basis in applicable),
                           gaps=missing, limitations=(LIMITATION,))
