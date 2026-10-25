"""Run: python -m hydroguard.services.audit (offline synthetic fixture only)."""
import os

from hydroguard.ai.sample import sample_critic
from hydroguard.data.sample import GAP_FINDING, HARM_FINDING, assessment_bases, project_claim, source_registry
from hydroguard.evidence.gate import evaluate_finding
from hydroguard.evidence.models import AuditResult, EvidenceFinding, EvidenceStrength, RevisionRecord


def run_sample_audit() -> AuditResult:
    if os.environ.get("SAMPLE_MODE", "true").lower() != "true":
        raise RuntimeError("Live mode is not implemented. This command only supports SAMPLE_MODE=true.")
    sources, bases, claim = source_registry(), assessment_bases(), project_claim()
    initial = EvidenceFinding(
        finding_id="water-finding-1", claim_id=claim.claim_id, revision=1,
        text=HARM_FINDING, claim_type="definitive_harm", strength=EvidenceStrength.WEAK,
        citation_ids=claim.citation_ids, assessment_basis_ids=tuple(bases),
        gaps=("No sufficient dry-season water balance identified in reviewed synthetic materials.",),
        limitations=("Only the listed synthetic excerpts were reviewed; other evidence may exist.",),
    )
    history = []
    critic = sample_critic(initial)
    gate = evaluate_finding(initial, critic, sources, bases, claim)
    history.append(RevisionRecord(finding=initial, critic=critic, gate=gate))
    if not gate.passed:
        # Explicit fixture revision, not autonomous replanning or World Model behavior.
        revised = initial.model_copy(update={"revision": 2, "text": GAP_FINDING, "claim_type": "evidence_gap"})
        critic = sample_critic(revised)
        gate = evaluate_finding(revised, critic, sources, bases, claim)
        history.append(RevisionRecord(finding=revised, critic=critic, gate=gate))
    question = None
    if history[-1].gate.passed:
        question = ("Can the proponent provide a dry-season water balance covering project demand, "
                    "available supply, and existing domestic and agricultural users, and explain "
                    "how those users would be protected during dry periods?")
    return AuditResult(claim=claim, sources=tuple(sources.values()), assessment_bases=tuple(bases.values()),
                       history=tuple(history), consultation_question=question)


if __name__ == "__main__":
    print(run_sample_audit().model_dump_json(indent=2))
