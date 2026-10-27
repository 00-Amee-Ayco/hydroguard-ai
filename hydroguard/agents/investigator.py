"""Evidence Investigator consumes records via a provider-neutral retrieval contract."""
from hydroguard.data.retrieval import EvidenceRetriever
from hydroguard.evidence.models import ProjectClaim, EvidenceSource


class EvidenceInvestigator:
    def __init__(self, retriever: EvidenceRetriever):
        self.retriever = retriever

    def investigate(self, claim: ProjectClaim) -> dict[str, EvidenceSource]:
        sources = self.retriever.retrieve(claim)
        if any(key != source.source_id for key, source in sources.items()):
            raise ValueError("Retrieved citation IDs do not resolve to their source records")
        return sources
