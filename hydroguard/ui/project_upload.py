"""Streamlit upload and page-grounded passage picker for HydroGuard.

This helper does NOT ingest the document into Zetaris or attach it to /run.
It is a local document-review UI only.
"""
from __future__ import annotations

import hashlib
import re

import pymupdf as fitz
import streamlit as st

MAX_BYTES = 25 * 1024 * 1024
MAX_PAGES = 250


@st.cache_data(show_spinner=False, max_entries=4)
def extract_pdf_pages(pdf_bytes: bytes) -> tuple[str, ...]:
    """Extract searchable page text with PDF page numbers preserved by index."""
    if len(pdf_bytes) > MAX_BYTES:
        raise ValueError("PDF exceeds the 25 MB demo upload limit.")
    if not pdf_bytes.startswith(b"%PDF-"):
        raise ValueError("This file does not appear to be a PDF.")
    doc = None
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        if doc.needs_pass:
            raise ValueError("Password-protected PDFs are not supported.")
        if len(doc) > MAX_PAGES:
            raise ValueError("PDF exceeds the 250-page demo limit.")
        return tuple(page.get_text("text", sort=True).strip() for page in doc)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("Could not safely read this PDF.") from exc
    finally:
        if doc is not None:
            doc.close()


DOMAIN_TERMS = {
    "Water": ("andoon river", "water quality", "water supply", "hydrology", "water balance", "water source"),
    "Land": ("land use", "soil erosion", "geology", "landslide", "land area", "soil contamination"),
    "Air": ("air quality", "noise", "emission", "particulate", "ambient air", "generator set"),
    "People": ("public participation", "residents", "community", "livelihood", "stakeholder", "health and safety"),
}


def domain_passages(pages: tuple[str, ...], domain: str, limit: int = 4) -> list[dict]:
    """Return source-grounded excerpts, NOT verified claims or audit findings."""
    terms = DOMAIN_TERMS[domain]
    candidates = []
    for page_idx, text in enumerate(pages, 1):
        if not text.strip():
            continue
        normalized = " ".join(text.split())
        low = normalized.lower()
        # Avoid pages that only match an EISS running header.
        matches = [(low.find(term), term) for term in terms if low.find(term) >= 0]
        if not matches:
            continue
        # Prefer substantive narrative over cover pages / contents pages.
        position, term = min(matches, key=lambda x: x[0])
        start = max(0, position - 110)
        end = min(len(normalized), position + 390)
        excerpt = normalized[start:end].strip()
        candidates.append({"pdf_page": page_idx, "excerpt": excerpt, "term": term})
    # Skip likely front matter when substantive pages are available.
    substantive = [c for c in candidates if c["pdf_page"] > 25]
    return (substantive or candidates)[:limit]


def render_project_upload() -> dict | None:
    """Load a PDF locally and return page-grounded, domain-indexed excerpts.

    This does not ingest the file into Zetaris or provide citations to /run.
    """
    st.markdown("### 1 · Upload a project EIS / EIA document")
    st.caption("PDF · up to 25 MB / 250 pages · local review only")
    uploaded = st.file_uploader("Project document (PDF)", type=["pdf"], key="hg_project_pdf")
    if uploaded is None:
        st.info("Upload your EIS to explore the Water, Land, Air and People sections.")
        return None
    content = uploaded.getvalue()
    try:
        pages = extract_pdf_pages(content)
    except ValueError as error:
        st.error(str(error))
        return None
    digest = hashlib.sha256(content).hexdigest()
    metrics = st.columns(3)
    metrics[0].metric("PDF pages", len(pages))
    metrics[1].metric("Searchable pages", sum(bool(page) for page in pages))
    metrics[2].metric("PDF size", f"{len(content) / 1048576:.1f} MB")
    st.caption(f"Document: {uploaded.name} · SHA-256: {digest[:12]}…")
    st.caption("PDF text is processed in this Streamlit session, not uploaded to Zetaris.")
    return {
        "filename": uploaded.name,
        "project_name": uploaded.name.rsplit(".", 1)[0],
        "file_sha256": digest,
        "pages": len(pages),
        "domain_passages": {domain: domain_passages(pages, domain) for domain in DOMAIN_TERMS},
    }
