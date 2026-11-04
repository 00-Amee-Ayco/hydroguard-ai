"""HydroGuard Streamlit workspace: document review and verified API responses.

Uploaded PDFs are inspected locally. They are NOT sent to Zetaris or attached to
/run, and are not counted as project evidence by the backend.
"""
from __future__ import annotations

import json
import re

import streamlit as st
from pydantic import ValidationError

from hydroguard.services.investigation import RunRequest
from hydroguard.ui.client import AuditClient, BackendError
from hydroguard.ui.project_upload import render_project_upload

DEFAULT = {
    "project_claim": {
        "claim_id": "water-claim",
        "project_name": "Fictional Philippine Development",
        "text": "Project water demand will not significantly affect existing water users.",
    },
    "domain": "Water",
    "case_context": {"stage": "scoping", "community_notes": "Synthetic community context."},
    "evidence_references": [],
}
PAGES = ["Case workspace", "Investigation results", "Evidence explorer", "Consultation brief"]
DOMAINS = ["Water", "Land", "Air", "People"]
STAGES = ["scoping", "consultation", "review"]


CSS = """
<style>
.stApp { background-color:#F5F8F7; color:#173447; }
.stMainBlockContainer { max-width:1450px; padding-top:1rem; padding-bottom:3rem; }
h1,h2,h3 { color:#173447 !important; font-weight:700 !important; }
[data-testid="stSidebar"] { background:#EAF1ED; border-right:1px solid #D2E0D9; }
[data-testid="stSidebar"] p, [data-testid="stSidebar"] label { color:#173447 !important; }
[data-testid="stWidgetLabel"] p, [data-testid="stMetricLabel"] p,
[data-testid="stForm"] label p { color:#173447 !important; opacity:1 !important; }
.stTextInput input,.stTextArea textarea {
    background-color:#FFFFFF !important; color:#173447 !important;
    border:1px solid #BFCFC8; border-radius:6px;
}
.stButton button[kind="primary"],.stFormSubmitButton button[kind="primary"] {
    background:#116149 !important; color:#FFFFFF !important;
    border:1px solid #116149 !important; border-radius:6px;
}
.stButton button[kind="primary"]:hover,.stFormSubmitButton button[kind="primary"]:hover {
    background:#0B4936 !important; color:#FFFFFF !important;
}
[data-testid="stMetric"] {
    background:#FFFFFF; padding:16px; border:1px solid #D7E3DC; border-radius:8px;
}
[data-testid="stMetricValue"],[data-testid="stMetricValue"] * { color:#173447 !important; }
[data-testid="stExpander"] { background:#FFFFFF; border:1px solid #D7E3DC; border-radius:8px; }
[data-testid="stDataFrame"] { border:1px solid #D7E3DC; border-radius:8px; }
/* Consistent forest-green controls with readable white text */
[data-testid="stSelectbox"] [data-baseweb="select"] > div,
[data-testid="stMultiSelect"] [data-baseweb="select"] > div {
    background-color:#103F32 !important;
    border:1px solid #27765D !important;
    border-radius:7px !important;
    color:#FFFFFF !important;
}
[data-testid="stSelectbox"] [data-baseweb="select"] *,
[data-testid="stMultiSelect"] [data-baseweb="select"] * {
    color:#FFFFFF !important;
    fill:#FFFFFF !important;
}
[data-testid="stSelectbox"] [data-baseweb="select"] svg,
[data-testid="stMultiSelect"] [data-baseweb="select"] svg {
    fill:#FFFFFF !important;
    stroke:#FFFFFF !important;
}
/* Uploaded PDF panel */
[data-testid="stFileUploaderDropzone"] {
    background-color:#103F32 !important;
    border:1px dashed #71B99D !important;
    border-radius:9px !important;
}
[data-testid="stFileUploaderDropzone"] *,
[data-testid="stFileUploaderDropzone"] small,
[data-testid="stFileUploaderDropzone"] span,
[data-testid="stFileUploaderDropzone"] p {
    color:#FFFFFF !important;
}
[data-testid="stFileUploaderDropzone"] button {
    background-color:#176149 !important;
    border:1px solid #B9E5D1 !important;
    color:#FFFFFF !important;
    border-radius:6px !important;
}
[data-testid="stFileUploaderDropzone"] button:hover {
    background-color:#247B5B !important;
    color:#FFFFFF !important;
}
/* File name and status after upload */
[data-testid="stFileUploaderFile"] {
    background-color:#E7F2EC !important;
    border:1px solid #BDDCCE !important;
    border-radius:7px;
}
/* All text entry controls: white panels with dark text for easier long-form reading */
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea {
    background-color:#FFFFFF !important;
    color:#173447 !important;
    -webkit-text-fill-color:#173447 !important;
}
/* Readable metrics and descriptive labels */
[data-testid="stMetricValue"],
[data-testid="stMetricValue"] *,
[data-testid="stMetricLabel"] p,
[data-testid="stWidgetLabel"] p {
    color:#173447 !important;
    opacity:1 !important;
}
/* Hide Streamlit's default top toolbar */
[data-testid="stHeader"] {
    display: none !important;
}

/* Hide the Deploy button and Streamlit menu */
[data-testid="stToolbar"],
[data-testid="stDecoration"] {
    display: none !important;
}

/* Remove empty spacing above HydroGuard */
[data-testid="stMainBlockContainer"] {
    padding-top: 1rem !important;
}


/* Accessibility: readable text in EVERY Streamlit alert (warning, info, success, error).
   The active Streamlit theme was rendering light text on pale yellow warnings. */
.stApp [data-testid="stAlert"],
.stApp [data-testid="stAlert"] [data-testid="stMarkdownContainer"],
.stApp [data-testid="stAlert"] p,
.stApp [data-testid="stAlert"] span,
.stApp [data-testid="stAlert"] strong,
.stApp [data-testid="stAlert"] em,
.stApp [data-testid="stAlert"] li,
.stApp [data-testid="stAlert"] a {
    color: #173447 !important;
    -webkit-text-fill-color: #173447 !important;
    opacity: 1 !important;
}
/* Keep warning icons and warning status visible, without forcing text white. */
.stApp [data-testid="stAlert"] svg {
    color: #173447 !important;
    stroke: #173447 !important;
}

</style>
"""

HEADER = """
<div style="background:linear-gradient(110deg,#102B3F,#174B48);color:#FFF;
            padding:24px 28px;border-radius:9px;margin-bottom:24px;">
  <div style="color:#B5E5CE;font-size:12px;font-weight:700;letter-spacing:2px;">
    ENVIRONMENTAL EVIDENCE INTELLIGENCE
  </div>
  <div style="font-size:36px;font-weight:800;color:white;margin-top:7px;">HydroGuard</div>
  <div style="color:#D8EAE6;font-size:15px;margin-top:10px;">
    See the claim. Trace the evidence. Challenge the gap. Know what to ask next.
  </div>
</div>
"""


def display(value) -> str:
    """Redact common credential and local-path formats in displayed API text."""
    text = str(value if value is not None else "")
    text = re.sub(r"(?:nvapi-|sk-proj-|ghp_)[A-Za-z0-9_-]+", "[credential omitted]", text)
    text = re.sub(r"(?i)bearer\s+\S+", "[credential omitted]", text)
    text = re.sub(r"(?:/Users/|/home/|/private/|[A-Za-z]:\\)[^\s,;]+", "[local path omitted]", text)
    return text


def source_details(result) -> None:
    if not result.citations:
        st.info("No source records were returned. This does not prove evidence does not exist.")
    for source in result.citations:
        with st.expander(display(source.document_title)):
            st.caption("Page: " + display(source.page or source.locator or "not supplied"))
            st.caption("Type: " + display(source.source_type or source.kind))
            st.caption("Source ID: " + display(source.source_id))
            st.caption("Document ID: " + display(source.document_id))
            st.caption("Chunk ID: " + display(source.chunk_id))
            if source.provenance == "synthetic" or source.is_synthetic:
                st.text(display(source.text))
            else:
                st.info("Private source text is withheld here. Review the original using an authorized evidence process.")
    for basis in result.audit.assessment_bases:
        with st.expander("Assessment basis · " + display(basis.basis_id)):
            st.text(display(basis.model_dump_json(indent=2)))


def brief(result) -> str:
    approved = result.gate.passed
    lines = [
        "HYDROGUARD CONSULTATION BRIEF",
        display(result.audit.claim.project_name),
        "Mode: " + display(result.audit.mode),
        "Run: " + result.run_id,
        "Project claim: " + display(result.audit.claim.text),
        "Validated finding:" if approved else "UNRESOLVED — not an established conclusion:",
        display(result.finding.text),
        "Evidence strength: " + result.finding.strength.value,
        "Gate: " + ("passed for this finding only" if approved else "blocked"),
        "Limitations:",
        *[display(item) for item in result.finding.limitations],
        "Gaps:",
        *[display(item) for item in result.finding.gaps],
        "Question: " + (
            display(result.community_question) if approved else "No gate-approved question available."
        ),
        "Sources:",
    ]
    lines.extend(
        display(f"{src.source_id} | {src.document_title} | page {src.page or 'not supplied'} | {src.chunk_id} | {src.provenance}")
        for src in result.citations
    )
    lines.append("Missing evidence is not proof of harm or illegality. Gate approval is not project safety approval.")
    return "\n\n".join(lines)


def initialize_case_state() -> None:
    st.session_state.setdefault("case", json.loads(json.dumps(DEFAULT)))


def case_workspace(client: AuditClient, sample: bool) -> None:
    st.subheader("Your case workspace")
    st.write("Upload the project EIS, choose one or more environmental domains, then request the available evidence review.")
    uploaded_project = render_project_upload()

    st.markdown("### 2 · Choose environmental domains")
    st.caption("You may select several domains or all four. Domain selection controls the document excerpts displayed below.")
    # Initialize selections
    for domain in DOMAINS:
        st.session_state.setdefault(f"domain_{domain}", False)

    st.session_state.setdefault("select_all_domains", False)


    def toggle_all_domains():
        """Select or deselect every domain."""
        all_checked = st.session_state["select_all_domains"]

        for domain in DOMAINS:
            st.session_state[f"domain_{domain}"] = all_checked


    def update_select_all():
        """Keep Select All synchronized with individual checkboxes."""
        st.session_state["select_all_domains"] = all(
            st.session_state[f"domain_{domain}"]
            for domain in DOMAINS
        )


    st.checkbox(
        "Select all domains",
        key="select_all_domains",
        on_change=toggle_all_domains,
    )

    cols = st.columns(4)

    for col, domain in zip(cols, DOMAINS):
        with col:
            st.checkbox(
                domain,
                key=f"domain_{domain}",
                on_change=update_select_all,
            )

    # Pass this variable to the existing document preview and audit logic.
    selected_domains = [
        domain
        for domain in DOMAINS
        if st.session_state[f"domain_{domain}"]
    ]

    if uploaded_project is None:
        st.info("Upload a PDF to view domain-specific source excerpts and enable the review.")
        return
    if not selected_domains:
        st.warning("Choose at least one environmental domain.")
        return

    st.markdown("### 3 · Document evidence overview")
    st.caption("These are PDF excerpts, not verified findings. Pages refer to physical PDF page numbers.")
    for domain in selected_domains:
        snippets = uploaded_project["domain_passages"].get(domain, [])
        with st.expander(f"{domain} · {len(snippets)} example matching pages", expanded=(domain == "Water")):
            if not snippets:
                st.info("No matching pages were found using the demo's keyword scan. This does not prove the topic is absent.")
            for snippet in snippets:
                st.markdown(f"**PDF page {snippet['pdf_page']}** · Matched topic: {snippet['term']}")
                st.write(display(snippet["excerpt"]))

    st.markdown("### 4 · Run available evidence review")
    st.info(
        "Live Zetaris currently supports a bounded Water investigation only. "
        "Uploaded PDF excerpts are NOT registered as project citations. "
        "Land, Air and People selections receive document previews only; they are not audited."
    )
    if "Water" not in selected_domains:
        st.warning("No backend audit is available for the selected domains. Add Water to run the current audit.")
        return

    water_pages = uploaded_project["domain_passages"].get("Water", [])
    if not water_pages:
        st.warning("No Water passage found in the PDF. The audit was not run.")
        return

    # The existing /run API requires one claim string. We pick one original PDF
    # excerpt automatically; this is not full-document ingestion or verification.
    chosen = water_pages[0]
    st.caption(
        f"Current backend will evaluate one automatically selected Water excerpt "
        f"(PDF page {chosen['pdf_page']}); it will not audit the entire document."
    )
    if st.button("Run Water evidence audit", type="primary", key="hg_run_document_audit"):
        payload = {
            "project_claim": {
                "claim_id": "water-document-review",
                "project_name": uploaded_project["project_name"][:500],
                "text": chosen["excerpt"][:10000],
            },
            "domain": "Water",
            "case_context": {
                "stage": "consultation",
                "community_notes": "",
            },
            "evidence_references": [],
        }
        st.session_state["case"] = payload
        st.session_state.pop("result", None)
        try:
            request = RunRequest.model_validate(payload)
            with st.spinner("Retrieving regulatory evidence from the HydroGuard backend…"):
                st.session_state["result"] = client.run(request)
            st.session_state["hg_audit_pdf_metadata"] = {
                "filename": uploaded_project["filename"],
                "pdf_page": chosen["pdf_page"],
                "hash_prefix": uploaded_project["file_sha256"][:12],
                "selected_domains": list(selected_domains),
            }
            st.success("Water API audit returned. See Investigation results for the finding, evidence gate and limitations.")
            if len(selected_domains) > 1:
                st.info("Other selected domains were previewed only—not audited.")
        except ValidationError:
            st.error("The automatically selected text did not meet the API's claim format.")
        except BackendError as error:
            st.error(display(error))


def evidence_explorer(client: AuditClient, sample: bool) -> None:
    st.subheader("Live Zetaris Knowledge Explorer")
    st.caption("Browse two separate reference collections. Neither search verifies a project's claims.")
    if sample:
        st.warning("Live search requires SAMPLE_MODE=false in the FastAPI backend.")
        return

    with st.form("live_zetaris_search"):
        source_type = st.selectbox("Knowledge source", ["Regulatory documents", "Scientific research abstracts"])
        domains = ["Water", "Land", "Air"] if source_type == "Regulatory documents" else ["Water", "Land", "Air", "People"]
        search_domain = st.selectbox("Environmental domain", domains)
        suggested = "water users" if source_type == "Regulatory documents" else "water"
        query = st.text_input("Search terms", value=suggested,
                              help="Regulatory Water: water, groundwater, baseline, season, demand, users. "
                                   "Scientific Water: water, groundwater, river, drinking, wastewater, flood, hydrology, mercury.")
        submitted = st.form_submit_button("Search Zetaris", type="primary")
    if submitted:
        st.session_state.pop("zetaris_search", None)
        try:
            with st.spinner("Searching live Zetaris evidence…"):
                if source_type == "Regulatory documents":
                    data = client.search(query, search_domain)
                else:
                    data = client.search_scientific(query, search_domain)
                st.session_state["zetaris_search"] = data
        except BackendError as error:
            st.error(display(error))
    searched = st.session_state.get("zetaris_search")
    if not searched:
        return
    scientific = searched.get("source_type") == "scientific_abstract"
    st.success("Live Zetaris query completed. This does not verify a project claim.")
    st.metric("Retrieved source records", searched.get("result_count", 0))
    st.caption("Matched topics: " + ", ".join(searched.get("supported_terms_used", [])))
    if scientific:
        st.info("These are research abstracts and citation metadata, not full papers, legal standards or project-specific evidence. The Water audit remains regulatory-only.")
    if not searched.get("results"):
        st.info("No matching reference passages were returned.")
    for index, source in enumerate(searched.get("results", []), 1):
        if scientific:
            title = display(source.get("title", "Untitled research"))
            with st.expander(f"{index}. {title}"):
                st.caption("Entry: " + display(source.get("entry_number")))
                st.caption("Section: " + display(source.get("section")))
                st.write(display(source.get("abstract", "")))
                st.markdown("**APA citation**")
                st.write(display(source.get("apa_citation", "")))
                if source.get("doi_url"):
                    st.caption("DOI: " + display(source.get("doi_url")))
        else:
            title = display(source.get("document_title", "Untitled source"))
            page = source.get("page") or "Not supplied"
            with st.expander(f"{index}. {title} — Page {page}"):
                st.caption("Origin: Live Zetaris · Source type: " + display(source.get("source_type", "regulatory")))
                st.caption("Source ID: " + display(source.get("source_id")))
                st.caption("Document ID: " + display(source.get("document_id")))
                st.write(display(source.get("text", "")))


def investigation_results(result) -> None:
    st.subheader("What does the evidence establish?")
    columns = st.columns(3)
    columns[0].metric("Evidence strength", result.finding.strength.value)
    columns[1].metric("Finding gate", "Passed" if result.gate.passed else "Blocked")
    columns[2].metric("Sources reviewed", len(result.citations))
    if not result.gate.passed:
        st.warning("Unresolved review item — do not present this as an established conclusion.")
    st.write(display(result.finding.text))
    st.info("Insufficient evidence does not demonstrate harm. Gate approval does not establish project safety or compliance.")
    st.subheader("Evidence gaps")
    for gap in result.finding.gaps:
        st.write("• " + display(gap))
    for limitation in result.finding.limitations:
        st.caption(display(limitation))
    st.subheader("Review controls")
    if result.critic:
        st.write(display(f"Critic: {result.critic.response_origin} · Decision: {result.critic.decision}"))
        st.caption(display(result.critic.model_identity))
    else:
        st.warning("No Critic approval was returned. Live Nemotron execution is unverified.")
    for reason in result.gate.reasons:
        st.write(display(reason))
    st.subheader("Consultation question")
    st.write(
        display(result.community_question)
        if result.gate.passed and result.community_question
        else "No validated consultation question is available."
    )
    source_details(result)


def consultation_brief(result) -> None:
    st.subheader("Prepare for consultation")
    text = brief(result)
    st.text(text)
    st.download_button("Download text brief", text, "hydroguard-brief.txt", "text/plain")
    summary = {
        "run_id": result.run_id,
        "status": result.status,
        "gate_passed": result.gate.passed,
        "brief": text,
    }
    st.download_button(
        "Download JSON brief", json.dumps(summary, indent=2),
        "hydroguard-brief.json", "application/json",
    )
    st.caption("Editable text and JSON only. DOCX report generation is not implemented.")


def render() -> None:
    st.set_page_config(page_title="HydroGuard · Evidence workspace", page_icon="🌿", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(HEADER, unsafe_allow_html=True)
    initialize_case_state()
    st.sidebar.markdown(
        "### HYDROGUARD\n\n**Environmental Evidence Workspace**\n\n"
        "Philippine EIA Evidence Intelligence\n\n---"
    )
    page = st.sidebar.radio("Workspace", PAGES)
    st.sidebar.caption("1. Upload → 2. Select domains → 3. Review → 4. Explore")
    try:
        client = AuditClient()
        health = client.health()
    except BackendError as error:
        st.error(display(error))
        st.info("Start the FastAPI backend (for example: SAMPLE_MODE=false python run.py).")
        return
    sample = health.get("mode") == "sample"
    st.sidebar.info("SAMPLE · synthetic evidence / offline rules" if sample else "LIVE · Zetaris retrieval only")
    st.sidebar.caption("Nemotron inference blocked/unverified. World Model not integrated.")
    result = st.session_state.get("result")
    if result and (result.audit.mode.startswith("Sample") != sample):
        st.warning("Saved result belongs to a different mode. Run a new audit for this backend.")
        result = None

    if page == PAGES[0]:
        case_workspace(client, sample)
    elif page == PAGES[2]:
        evidence_explorer(client, sample)
    elif result is None:
        st.info("Run an evidence audit in Case workspace first.")
    elif page == PAGES[1]:
        meta = st.session_state.get("hg_audit_pdf_metadata")
        if meta:
            st.caption("PDF excerpt used as claim text: " + display(meta["filename"]) + " · physical page " + str(meta["pdf_page"]))
            st.info("The uploaded document was not supplied as case-specific cited evidence to the API. Other domain previews are not audit results.")
        investigation_results(result)
    else:
        consultation_brief(result)
