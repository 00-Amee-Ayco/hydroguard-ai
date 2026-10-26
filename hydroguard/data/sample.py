"""Bundled synthetic records; evidence_items are curated facts, not NLP extraction."""
import re
from collections.abc import Mapping

from hydroguard.evidence.models import AssessmentBasis, EvidenceSource, ProjectClaim

HARM_FINDING = "The project will cause community water shortages."
# Retained as a legacy example string, never used to select decisions.
GAP_FINDING = "The disclosed evidence does not sufficiently establish that existing water users will remain unaffected during dry-season conditions."

CRITERIA = {
    "Water": ("dry-season water balance", "existing water users"),
    "Land": ("erosion baseline", "slope stability assessment"),
    "Air": ("particulate baseline", "dispersion assessment", "receptor inventory"),
}
CLAIMS = {
    "Water": "Project water demand will not significantly affect existing water users.",
    "Land": "Earthworks will not increase erosion or slope instability.",
    "Air": "Project dust emissions will not affect nearby air quality receptors.",
}


def source_registry() -> dict[str, EvidenceSource]:
    records = []
    disclosures = {
        "Water": "Water demand is described using annual totals and wet-season observations.",
        "Land": "Earthworks erosion baseline is surveyed; a slope assessment is not disclosed.",
        "Air": "Dust emissions particulate baseline and dispersion assessment are included; receptor mapping is absent.",
    }
    present = {"Water": (), "Land": ("erosion baseline",),
               "Air": ("particulate baseline", "dispersion assessment")}
    for domain in CRITERIA:
        project_id = "sample-project-1" if domain == "Water" else f"sample-{domain.lower()}-project"
        basis_id = "sample-basis-1" if domain == "Water" else f"sample-{domain.lower()}-basis"
        records.append(EvidenceSource(
            source_id=project_id, document_id=f"synthetic-{domain.lower()}-disclosure",
            document_title=f"Fictional {domain} Disclosure (Synthetic)", page=3,
            chunk_id="disclosure-p3-c1" if domain == "Water" else f"{domain.lower()}-p3-c1",
            provenance="synthetic", domain=domain, kind="project",
            text=CLAIMS[domain] + " " + disclosures[domain], evidence_items=present[domain]))
        records.append(EvidenceSource(
            source_id=basis_id, document_id=f"synthetic-{domain.lower()}-review",
            document_title=f"Synthetic {domain} Review Criterion (not a regulation)", page=1,
            chunk_id=f"{domain.lower()}-review-p1-c1", provenance="synthetic", domain=domain,
            kind="basis", text="Review " + ", ".join(CRITERIA[domain]) + "."))
    return {source.source_id: source for source in records}


def assessment_bases() -> dict[str, AssessmentBasis]:
    return {("dry-season-review" if domain == "Water" else f"{domain.lower()}-review"):
            AssessmentBasis(basis_id="dry-season-review" if domain == "Water" else f"{domain.lower()}-review",
                            text="Review " + ", ".join(items), domain=domain, required_items=items,
                            citation_ids=("sample-basis-1" if domain == "Water" else f"sample-{domain.lower()}-basis",),
                            limitation="Synthetic review criterion, not a legal applicability determination.")
            for domain, items in CRITERIA.items()}


def project_claim(domain: str = "Water", text: str | None = None) -> ProjectClaim:
    return ProjectClaim(claim_id=f"{domain.lower()}-claim", project_name="Fictional Philippine Development",
                        domain=domain, text=text or CLAIMS[domain], citation_ids=())


def retrieve(claim: ProjectClaim, registry: Mapping[str, EvidenceSource]) -> dict[str, EvidenceSource]:
    """Actual lexical selection, scoped by domain; no fixture-ID dispatch."""
    words = set(re.findall(r"[a-z]+", claim.text.lower())) - {"the", "a", "will", "not", "project", "or", "and"}
    return {key: source for key, source in registry.items()
            if source.domain == claim.domain and source.kind != "basis"
            and words.intersection(re.findall(r"[a-z]+", source.text.lower()))}
