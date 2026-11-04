"""Streamlit upload and page-grounded passage picker for HydroGuard.

This helper does NOT ingest the document into Zetaris or attach it to /run.
It is a local document-review UI only.
"""
from __future__ import annotations

import hashlib
import io
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


def render_project_upload() -> dict | None:
    """Return a user-selected, page-grounded passage, or None."""
    st.markdown("### 1 · Upload a project EIS / EIA document")
    st.caption("PDF only · up to 25 MB and 250 pages · processed in this local Streamlit session")
    uploaded = st.file_uploader(
        "Project document (PDF)", type=["pdf"], key="hg_project_pdf"
    )
    if uploaded is None:
        st.info("Upload a project PDF to inspect its contents and choose a passage to investigate.")
        return None

    pdf_bytes = uploaded.getvalue()
    try:
        pages = extract_pdf_pages(pdf_bytes)
    except ValueError as exc:
        st.error(str(exc))
        return None

    digest = hashlib.sha256(pdf_bytes).hexdigest()
    if st.session_state.get("hg_doc_sha256") != digest:
        st.session_state["hg_doc_sha256"] = digest
        st.session_state.pop("hg_passage_choice", None)

    a, b, c = st.columns(3)
    a.metric("PDF pages", len(pages))
    b.metric("Pages with text", sum(bool(p.strip()) for p in pages))
    c.metric("File size", f"{len(pdf_bytes)/1024/1024:.1f} MB")
    st.caption(f"Filename: {uploaded.name} · SHA-256: {digest[:16]}…")
    st.info("Upload analyzed locally. This document is NOT yet registered in Zetaris or linked as evidence to the backend audit.")

    term = st.text_input(
        "Find a statement in the project PDF",
        value="water quality",
        key="hg_project_term",
    ).strip()
    if not term:
        st.info("Enter search terms to find relevant PDF pages.")
        return None

    words = re.findall(r"[\w-]+", term.lower())[:8]
    matches = []
    for page_no, page_text in enumerate(pages, start=1):
        if not page_text:
            continue
        lower = page_text.lower()
        if all(word in lower for word in words):
            # Show a bounded excerpt around the first search term, rather than the whole page.
            pos = lower.find(words[0])
            start = max(0, pos - 200)
            end = min(len(page_text), pos + 700)
            excerpt = page_text[start:end].strip()
            matches.append({"page": page_no, "text": page_text, "excerpt": excerpt})
            if len(matches) >= 30:
                break

    st.caption(f"Matching PDF pages shown: {len(matches)} (maximum 30)")
    if not matches:
        st.warning("No page contains all of those words. Try a simpler query.")
        return None

    choice = st.selectbox(
        "Select a source page",
        options=list(range(len(matches))),
        format_func=lambda i: f"PDF page {matches[i]['page']}",
        key="hg_passage_choice",
    )
    selected = matches[choice]
    st.text_area(
        "Source excerpt (read-only preview)",
        value=selected["excerpt"],
        height=200,
        disabled=True,
    )
    st.caption("PDF page numbering is physical page order, which may differ from printed EISS section numbering.")

    st.markdown("### 2 · Select a claim for the existing audit")
    suggested = selected["excerpt"].replace("\n", " ")[:400]
    claim_text = st.text_area(
        "Claim to investigate (review and edit)",
        value=suggested,
        height=110,
        key=f"hg_claim_{digest[:10]}_{selected['page']}",
    ).strip()
    st.warning(
        "The audit currently receives the edited claim as text only. "
        "It will not count this PDF as project-specific evidence until the backend "
        "supports secure document ingestion, case IDs and source citations."
    )
    if not claim_text:
        return None
    return {
        "project_name": uploaded.name.removesuffix(".pdf"),
        "claim_text": claim_text,
        "pdf_page": selected["page"],
        "file_sha256": digest,
        "filename": uploaded.name,
    }
