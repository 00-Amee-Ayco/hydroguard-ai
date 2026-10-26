"""Input-dependent offline audit: python -m hydroguard.services.audit --help."""
import argparse
import os
from collections.abc import Mapping
from hydroguard.services.trace import RunTrace
from hydroguard.ai.sample import sample_critic
from hydroguard.data.sample import assessment_bases, project_claim, retrieve, source_registry
from hydroguard.evidence.assessment import derive_finding, display_text
from hydroguard.evidence.gate import evaluate_finding
from hydroguard.evidence.models import AuditResult, RevisionRecord, ProjectClaim, EvidenceSource, AssessmentBasis, EvidenceFinding


class LiveModeUnavailable(RuntimeError):
    """Live integrations are not implemented; no offline fallback is permitted."""


def run_sample_audit(
    claim: ProjectClaim | None = None, *,
    registry: Mapping[str, EvidenceSource] | None = None,
    bases: Mapping[str, AssessmentBasis] | None = None,
    preliminary: EvidenceFinding | None = None,
    trace: RunTrace | None = None,
) -> AuditResult:
    if os.environ.get("SAMPLE_MODE", "true").lower() != "true":
        raise LiveModeUnavailable("Live mode is not implemented. This command only supports SAMPLE_MODE=true.")
    claim = project_claim() if claim is None else claim
    registry = source_registry() if registry is None else registry
    available_bases = assessment_bases() if bases is None else bases
    selected_bases = {key: basis for key, basis in available_bases.items() if basis.domain == claim.domain}
    if trace:
        trace.emit("Case Planner", "plan_domain_retrieval", handoff="Evidence Investigator")
    retrieved = retrieve(claim, registry)
    if trace:
        trace.emit("Evidence Investigator", "lexical_retrieval", source_ids=tuple(retrieved), handoff="Evidence Critic")
    # An input citation is validated rather than silently replaced.
    if not claim.citation_ids:
        claim = claim.model_copy(update={"citation_ids": tuple(s.source_id for s in retrieved.values() if s.kind == "project")})
    sources = dict(retrieved)
    for basis in selected_bases.values():
        for citation in basis.citation_ids:
            if citation in registry:
                sources[citation] = registry[citation]
    finding = preliminary if preliminary is not None else derive_finding(claim, sources, selected_bases)
    history = []
    for attempt in range(2):
        critic = sample_critic(finding, sources, selected_bases, claim)
        if trace:
            trace.emit("Evidence Critic", "offline_policy_critique", decision=critic.decision,
                       source_ids=tuple(sources), retry=attempt, handoff="Deterministic Evidence Gate")
        gate = evaluate_finding(finding, critic, sources, selected_bases, claim)
        if trace:
            trace.emit("Deterministic Evidence Gate", "validate_finding", passed=gate.passed,
                       source_ids=tuple(sources), retry=attempt)
        history.append(RevisionRecord(finding=finding, critic=critic, gate=gate))
        if gate.passed or preliminary is None or attempt == 1:
            if trace:
                trace.emit("Case Planner", "branch_decision", decision="publish" if gate.passed else "unresolved",
                           retry=attempt, handoff="Community Action Planner" if gate.passed else None)
            break
        if trace:
            trace.emit("Case Planner", "revise_from_reviewed_evidence", decision="retry", retry=attempt + 1,
                       handoff="Evidence Critic")
        finding = derive_finding(claim, sources, selected_bases, finding.revision + 1)
    final = history[-1]
    question = None
    if final.gate.passed:
        claim_text = display_text(claim.text)
        if final.finding.gaps:
            question = (f"For the claim {claim_text!r}, can the proponent provide "
                        f"{', '.join(final.finding.gaps)} and explain the implications for affected users?")
        else:
            question = (f"For the claim {claim_text!r}, how will the documented "
                        f"{', '.join(item for b in selected_bases.values() for item in b.required_items)} "
                        "be verified and monitored with the community?")
    if question:
        question = display_text(question)
    if trace:
        trace.emit("Community Action Planner", "consultation_question", "completed" if question else "withheld")
    return AuditResult(claim=claim, sources=tuple(sources.values()), assessment_bases=tuple(selected_bases.values()),
                       history=tuple(history), consultation_question=question)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Synthetic offline evidence audit; no live AI inference.")
    parser.add_argument("--domain", choices=("Water", "Land", "Air"), default="Water")
    parser.add_argument("--claim", help="Claim text used for lexical evidence retrieval")
    args = parser.parse_args()
    print(run_sample_audit(project_claim(args.domain, args.claim)).model_dump_json(indent=2))
