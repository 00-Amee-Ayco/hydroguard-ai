"""Fictional records, not real project disclosures or legal provisions."""
from hydroguard.evidence.models import AssessmentBasis, EvidenceSource, ProjectClaim

GAP_FINDING = (
    "The disclosed evidence does not sufficiently establish that existing water users "
    "will remain unaffected during dry-season conditions."
)
HARM_FINDING = "The project will cause community water shortages."


def source_registry() -> dict[str, EvidenceSource]:
    records = (
        EvidenceSource(source_id="sample-project-1", document_id="synthetic-disclosure",
                       document_title="Fictional Philippine Development Disclosure (Synthetic)",
                       page=3, chunk_id="disclosure-p3-c1", provenance="synthetic",
                       text="The fictional project claims its water demand will not significantly "
                            "affect existing water users. Only annual demand and wet-season "
                            "observations are disclosed in this synthetic excerpt."),
        EvidenceSource(source_id="sample-basis-1", document_id="synthetic-review-note",
                       document_title="Synthetic Water Review Note (not a regulation)",
                       page=1, chunk_id="review-p1-c1", provenance="synthetic",
                       text="For this fictional exercise, examine dry-season supply, project demand "
                            "and existing domestic and agricultural uses before accepting the assurance."),
    )
    return {record.source_id: record for record in records}


def project_claim() -> ProjectClaim:
    return ProjectClaim(claim_id="water-1", project_name="Fictional Philippine Development",
                        domain="Water", text="Project water demand will not significantly affect existing water users.",
                        citation_ids=("sample-project-1",))


def assessment_bases() -> dict[str, AssessmentBasis]:
    basis = AssessmentBasis(basis_id="dry-season-review", citation_ids=("sample-basis-1",),
                            text="Assess dry-season supply against project and existing users' demand.",
                            limitation="Synthetic assessment criterion, not a legal applicability determination.")
    return {basis.basis_id: basis}
