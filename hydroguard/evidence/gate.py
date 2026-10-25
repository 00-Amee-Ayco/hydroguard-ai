"""Independent fail-closed rules for the supported sample finding only."""
from collections.abc import Mapping

from hydroguard.data.sample import GAP_FINDING
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
    if critic is None:
        reasons.append("Missing Critic decision.")
    else:
        if (critic.finding_id != finding.finding_id or critic.revision != finding.revision
                or critic.finding_fingerprint != finding.fingerprint()):
            reasons.append("Stale or mismatched Critic approval.")
        if critic.decision != "approve":
            reasons.append("Critic has not approved this finding.")
    # A strength label or LLM approval cannot establish harm or illegality.
    if finding.claim_type != "evidence_gap":
        reasons.append("Definitive harm and illegality findings are unsupported in this slice.")
    elif finding.text != GAP_FINDING or claim.domain != "Water":
        reasons.append("Evidence-gap wording/domain is outside this slice's reviewed scope.")
    if not finding.gaps or not finding.limitations:
        reasons.append("Explicit evidence gaps and review limitations are required.")
    return GateResult(finding_id=finding.finding_id, revision=finding.revision,
                      passed=not reasons, reasons=tuple(reasons))
