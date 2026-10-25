from hydroguard.data.sample import source_registry
from hydroguard.services.audit import run_sample_audit


def test_all_citations_resolve_with_provenance(monkeypatch):
    monkeypatch.setenv("SAMPLE_MODE", "true")
    result = run_sample_audit()
    registry = source_registry()
    ids = list(result.claim.citation_ids)
    for basis in result.assessment_bases:
        ids.extend(basis.citation_ids)
    for record in result.history:
        ids.extend(record.finding.citation_ids)
    for citation in ids:
        source = registry[citation]
        assert source.source_id == citation
        assert source.document_id and source.document_title and source.chunk_id
        assert source.page >= 1
        assert source.provenance == "synthetic"
    assert registry["sample-project-1"].page == 3
    assert registry["sample-project-1"].chunk_id == "disclosure-p3-c1"
