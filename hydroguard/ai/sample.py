"""Input-dependent offline rule evaluator; no NVIDIA/Nightshift inference."""
from hydroguard.evidence.assessment import context_fingerprint
from hydroguard.evidence.gate import evaluate_finding
from collections.abc import Mapping
from hydroguard.evidence.models import CriticDecision, EvidenceFinding, EvidenceSource, AssessmentBasis, ProjectClaim


def sample_critic(finding: EvidenceFinding, sources: Mapping[str, EvidenceSource],
                  bases: Mapping[str, AssessmentBasis], claim: ProjectClaim) -> CriticDecision:
    # Provisional approval lets the policy check evidence without circular inference.
    provisional = CriticDecision(finding_id=finding.finding_id, revision=finding.revision,
                                 finding_fingerprint=finding.fingerprint(),
                                 evidence_fingerprint=context_fingerprint(sources, bases, claim),
                                 decision="approve", reason="Offline policy evaluation in progress.")
    result = evaluate_finding(finding, provisional, sources, bases, claim)
    return provisional.model_copy(update={
        "decision": "approve" if result.passed else "reject",
        "reason": "Offline evidence policy satisfied." if result.passed else "; ".join(result.reasons),
    })
