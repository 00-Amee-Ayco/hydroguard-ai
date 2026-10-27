"""Shared retrieval contract used by sample and live Evidence Investigators."""
from collections.abc import Mapping
from typing import Protocol
from hydroguard.evidence.models import EvidenceSource, ProjectClaim
from hydroguard.data.sample import retrieve


class EvidenceRetriever(Protocol):
    def retrieve(self, claim: ProjectClaim) -> dict[str, EvidenceSource]: ...


class SampleEvidenceRetriever:
    def __init__(self, registry: Mapping[str, EvidenceSource], retrieve_fn=retrieve):
        self.registry = registry
        self.retrieve_fn = retrieve_fn

    def retrieve(self, claim: ProjectClaim) -> dict[str, EvidenceSource]:
        return self.retrieve_fn(claim, self.registry)
