"""Independent fail-closed validation over retrieved offline evidence."""
from collections.abc import Mapping

from hydroguard.evidence.assessment import context_fingerprint, derive_finding
from hydroguard.evidence.models import (
    AssessmentBasis, CriticDecision, EvidenceFinding, EvidenceSource, GateResult, ProjectClaim,
)


def evaluate_finding(
    finding: EvidenceFinding,
    critic: CriticDecision | None,
    sources: Mapping[str, EvidenceSource],
    bases: Mapping[str, AssessmentBasis],
    claim: ProjectClaim,
) -> GateResult:
    reasons: list[str] = []
    if finding.claim_id != claim.claim_id:
        reasons.append("Finding does not reference the current project claim.")

    def check_citations(ids: tuple[str, ...], label: str) -> None:
        if not ids:
            reasons.append(f"Missing {label} source citation.")
        for citation in ids:
            if citation not in sources or sources[citation].source_id != citation:
                reasons.append(f"Invalid {label} citation ID: {citation}")

    check_citations(finding.citation_ids, "finding")
    check_citations(claim.citation_ids, "project claim")
    if not set(claim.citation_ids).issubset(finding.citation_ids):
        reasons.append("Finding must cite the reviewed project claim.")
    if not finding.assessment_basis_ids:
        reasons.append("Missing assessment basis.")
    for basis_id in finding.assessment_basis_ids:
        basis = bases.get(basis_id)
        if basis is None or basis.basis_id != basis_id:
            reasons.append(f"Invalid assessment basis: {basis_id}")
        else:
            check_citations(basis.citation_ids, "assessment basis")
            if basis.domain != claim.domain or not basis.required_items:
                reasons.append("Assessment basis is not applicable to this claim.")
            if any(sources[c].kind != "basis" or sources[c].domain != claim.domain
                   for c in basis.citation_ids if c in sources):
                reasons.append("Assessment basis cites an unsuitable source.")
    if critic is None:
        reasons.append("Missing Critic decision.")
    else:
        if (critic.finding_id != finding.finding_id or critic.revision != finding.revision
                or critic.finding_fingerprint != finding.fingerprint()):
            reasons.append("Stale or mismatched Critic approval.")
        if critic.evidence_fingerprint != context_fingerprint(sources, bases, claim):
            reasons.append("Stale evidence context in Critic approval.")
        if critic.decision != "approve":
            reasons.append("Critic has not approved this finding.")
    if finding.claim_type not in ("evidence_gap", "evidence_summary"):
        reasons.append("Definitive harm and illegality findings are unsupported in offline mode.")
    expected = derive_finding(claim, sources, bases, finding.revision)
    # Recompute the safe finding from the actual records, independent of approval.
    for field in ("text", "claim_type", "strength", "citation_ids", "assessment_basis_ids", "gaps"):
        if getattr(finding, field) != getattr(expected, field):
            reasons.append(f"Finding {field} does not match the reviewed evidence.")
    if not finding.limitations or (finding.claim_type == "evidence_gap" and not finding.gaps):
        reasons.append("Explicit evidence gaps and review limitations are required.")
    return GateResult(finding_id=finding.finding_id, revision=finding.revision,
                      passed=not reasons, reasons=tuple(reasons))
