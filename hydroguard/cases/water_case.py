"""Describe disclosure gaps without inventing a regulatory obligation or approval."""
from hydroguard.evidence.assessment import display_text
from hydroguard.evidence.models import EvidenceFinding, EvidenceStrength

OMISSIONS = (
    ("a complete dry-season water balance is not provided", "Complete dry-season water balance is explicitly not provided in the retrieved disclosure."),
    ("quantified existing-user abstraction evidence is not provided", "Quantified existing-user abstraction evidence is explicitly not provided in the retrieved disclosure."),
)


def unresolved_water_finding(claim, sources):
    project = [source for source in sources.values() if source.kind == "project"]
    regulatory = [source for source in sources.values() if source.source_type == "regulatory"]
    disclosed = display_text(" ".join(source.text for source in project)).lower()
    omissions = tuple(description for phrase, description in OMISSIONS if phrase in disclosed)
    if not project:
        gaps = ("No project-specific disclosure was retrieved; regulatory references cannot substantiate the project claim.",)
        text = "The project claim remains unresolved. Project-specific evidence and reviewed assessment criteria are missing."
    elif len(omissions) == 2:
        text = ("The disclosed project evidence does not sufficiently establish that existing water users "
                "will remain unaffected during dry-season conditions.")
        gaps = omissions
    else:
        text = "The project assurance remains unresolved; sufficient evidence and applicable assessment criteria have not been established."
        gaps = omissions or ("Retrieved project passages do not establish sufficient support for the assurance.",)
    if not regulatory:
        gaps = ("No relevant regulatory passages returned by Zetaris.",) + gaps
    gaps += ("Regulatory applicability and an assessment basis require review; no dry-season legal requirement is inferred from the references.",
             "Live Evidence Critic approval is unavailable; no Critic was invoked.")
    return EvidenceFinding(finding_id=f"{claim.claim_id}-finding", claim_id=claim.claim_id, revision=1,
        text=text, claim_type="evidence_gap", strength=EvidenceStrength.INSUFFICIENT,
        citation_ids=tuple(sources), assessment_basis_ids=(), gaps=gaps,
        limitations=("Disclosure gaps concern only retrieved materials, not proof that studies do not exist elsewhere.",
                     "Synthetic project disclosure and authentic regulatory references; no finding of harm, safety or compliance.",
                     "Regulatory reference relevance is not legal applicability. No reviewed assessment requirement or live Critic approval is available."))
