"""HydroGuard Streamlit workspace: document review and verified API responses.

Uploaded PDFs are inspected locally. They are NOT sent to Zetaris or attached to
/run, and are not counted as project evidence by the backend.
"""
from __future__ import annotations

import base64
import json
import re
from pathlib import Path

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
PAGES = ["Case workspace", "Investigation results", "Evidence explorer"]
DOMAINS = ["Water", "Land", "Air", "People"]
STAGES = ["scoping", "consultation", "review"]
LOGO_PATH = Path(__file__).resolve().parent / "assets" / "HydroGuard_Logo.png"



CSS = """
<style>
/* Licensed Neue Haas font is used when installed in the browser's OS.
   Arial/Helvetica are graceful fallbacks until a licensed webfont is configured. */
@font-face {
    font-family: "HydroGuard Neue Haas";
    src: local("Neue Haas Grotesk Text Pro 55 Roman"),
         local("Neue Haas Grotesk Text Pro Regular"),
         local("Neue Haas Grotesk Text Pro");
    font-style: normal;
    font-weight: 400;
    font-display: swap;
}
@font-face {
    font-family: "HydroGuard Neue Haas";
    src: local("Neue Haas Grotesk Text Pro Bold"),
         local("Neue Haas Grotesk Text Pro 75 Bold");
    font-style: normal;
    font-weight: 700;
    font-display: swap;
}
/* HydroGuard's official logo palette: deep navy, ocean blue, ice blue. */
:root {
    --hg-navy: #052B5B;
    --hg-blue: #0A4C91;
    --hg-blue-hover: #07376C;
    --hg-secondary: #5B8F83;
    --hg-secondary-hover: #47796F;
    --hg-text: #102F53;
    --hg-muted: #52796F;
    --hg-border: #CDDBEA;
    --hg-bg: #F5F8FD;
}
.stApp { background-color: var(--hg-bg); color: var(--hg-text); }
/* Apply Neue Haas only to text-bearing elements.
   DO NOT set font-family on .stApp * or all spans: Streamlit uses icon fonts. */
.stApp, .stApp p, .stApp li, .stApp label,
.stApp button, .stApp input, .stApp textarea,
.stApp h1, .stApp h2, .stApp h3, .stApp h4,
[data-testid="stSidebar"] {
    font-family: "HydroGuard Neue Haas", "Neue Haas Grotesk Text Pro", "Helvetica Neue", Arial, sans-serif !important;
}
.stApp p, .stApp li, .stApp input, .stApp textarea,
.stApp [data-testid="stMarkdownContainer"] p {
    font-weight: 400 !important;
}
.stApp strong, .stApp b {
    font-weight: 700 !important;
}
[data-testid="stWidgetLabel"] p,
[data-testid="stRadio"] label p,
[data-testid="stCheckbox"] label p,
[data-testid="stSidebar"] label p {
    font-weight: 600 !important;
}
.stApp button { font-weight: 600 !important; }
/* CRITICAL: Restore icon font used for uploader and sidebar controls.
   'upload' and 'keyboard_double_arrow...' are icon ligatures, not labels. */
.stApp .material-symbols-rounded,
.stApp .material-symbols-outlined,
.stApp [data-testid="stIconMaterial"],
.stApp [data-testid="stIconMaterial"] span,
[data-testid="stSidebar"] .material-symbols-rounded,
[data-testid="stSidebar"] [data-testid="stIconMaterial"] {
    font-family: "Material Symbols Rounded" !important;
    font-weight: normal !important;
    font-style: normal !important;
    font-size: 24px;
    line-height: 1 !important;
    letter-spacing: normal !important;
    text-transform: none !important;
    white-space: nowrap !important;
    word-wrap: normal !important;
    direction: ltr;
    -webkit-font-feature-settings: "liga" !important;
    font-feature-settings: "liga" !important;
    -webkit-font-smoothing: antialiased;
}
/* Preserve regular weight within research snippets. */
.stApp [data-testid="stExpanderDetails"] p,
.stApp [data-testid="stExpanderDetails"] li { font-weight: 400 !important; }

.stMainBlockContainer { max-width:1450px; padding-top:1rem; padding-bottom:3rem; }
h1,h2,h3,h4 { color:var(--hg-navy) !important; font-weight:700 !important; }
.stApp p, .stApp li { color:var(--hg-text); }
.stApp [data-testid="stCaptionContainer"] p { color:var(--hg-muted) !important; }
[data-testid="stSidebar"] { background:#EAF1FA; border-right:1px solid var(--hg-border); }
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] label { color:var(--hg-text) !important; }
[data-testid="stWidgetLabel"] p,
[data-testid="stMetricLabel"] p,
[data-testid="stForm"] label p { color:var(--hg-text) !important; opacity:1 !important; }
[data-testid="stRadio"] label p,
[data-testid="stCheckbox"] label p { color:var(--hg-text) !important; }
[data-testid="stRadio"] [role="radiogroup"] [aria-checked="true"],
[data-testid="stCheckbox"] input { accent-color:var(--hg-blue) !important; }
/* Navy primary actions; ocean-sage secondary controls. */
.stButton button[kind="primary"],
.stFormSubmitButton button[kind="primary"],
.stDownloadButton button {
    background:var(--hg-blue) !important;
    color:#FFFFFF !important;
    border:1px solid var(--hg-blue) !important;
    border-radius:8px !important;
}
.stButton button[kind="primary"] *,
.stFormSubmitButton button[kind="primary"] *,
.stDownloadButton button * { color:#FFFFFF !important; }
.stButton button[kind="primary"]:hover,
.stFormSubmitButton button[kind="primary"]:hover,
.stDownloadButton button:hover {
    background:var(--hg-blue-hover) !important;
    border-color:var(--hg-blue-hover) !important;
}
.stButton button[kind="secondary"],
.stFormSubmitButton button[kind="secondary"] {
    border-color:var(--hg-secondary) !important;
    color:#FFFFFF !important;
    background:var(--hg-secondary) !important;
}
.stButton button[kind="secondary"] *,
.stFormSubmitButton button[kind="secondary"] * { color:#FFFFFF !important; }
.stButton button[kind="secondary"]:hover,
.stFormSubmitButton button[kind="secondary"]:hover {
    background:var(--hg-secondary-hover) !important;
    border-color:var(--hg-secondary-hover) !important;
}
/* Mint accents for focus rings, selected controls and the brand border. */
.stApp :is(input, textarea, button, [role="combobox"]):focus-visible {
    outline:2px solid var(--hg-secondary) !important;
    outline-offset:2px;
}
.stApp [data-testid="stCheckbox"] input { accent-color:var(--hg-secondary) !important; }
/* White, readable input panels */
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea {
    background-color:#FFFFFF !important;
    color:var(--hg-text) !important;
    -webkit-text-fill-color:var(--hg-text) !important;
    border:1px solid var(--hg-border) !important;
    border-radius:8px !important;
}
[data-testid="stSelectbox"] [data-baseweb="select"] > div,
[data-testid="stMultiSelect"] [data-baseweb="select"] > div {
    background-color:var(--hg-navy) !important;
    border:1px solid #3674B2 !important;
    border-radius:8px !important;
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
[data-testid="stFileUploaderDropzone"] {
    background-color:#EAF2FB !important;
    border:1px dashed #6D9BC6 !important;
    border-radius:10px !important;
}
[data-testid="stFileUploaderDropzoneInstructions"],
[data-testid="stFileUploaderDropzoneInstructions"] p,
[data-testid="stFileUploaderDropzoneInstructions"] small {
    color: var(--hg-text) !important;
    font-weight: 400 !important;
}
[data-testid="stFileUploaderDropzone"] button {
    background-color:var(--hg-blue) !important;
    border:1px solid var(--hg-blue) !important;
    color:#FFFFFF !important;
    border-radius:7px !important;
}
[data-testid="stFileUploaderDropzone"] button,
[data-testid="stFileUploaderDropzone"] button span {
    color: #FFFFFF !important;
    white-space: nowrap !important;
}
[data-testid="stFileUploaderFile"] {
    background:#E8F2FD !important;
    border:1px solid #BED4EA !important;
    border-radius:8px !important;
}
[data-testid="stMetric"] {
    background:#FFFFFF;
    padding:16px;
    border:1px solid var(--hg-border);
    border-radius:10px;
}
[data-testid="stMetricValue"],
[data-testid="stMetricValue"] * { color:var(--hg-navy) !important; font-weight:700 !important; }
[data-testid="stExpander"] { background:#FFFFFF; border:1px solid var(--hg-border); border-radius:9px; }
[data-testid="stDataFrame"] { border:1px solid var(--hg-border); border-radius:9px; }
/* Accessible alert messages, including warnings: retain distinct alert backgrounds. */
.stApp [data-testid="stAlert"],
.stApp [data-testid="stAlert"] [data-testid="stMarkdownContainer"],
.stApp [data-testid="stAlert"] p,
.stApp [data-testid="stAlert"] span,
.stApp [data-testid="stAlert"] strong,
.stApp [data-testid="stAlert"] em,
.stApp [data-testid="stAlert"] li,
.stApp [data-testid="stAlert"] a {
    color:#183655 !important;
    -webkit-text-fill-color:#183655 !important;
    opacity:1 !important;
}
.stApp [data-testid="stAlert"] svg {
    color:#183655 !important;
    stroke:#183655 !important;
}
/* Hide default Streamlit toolbar, while retaining application navigation. */
[data-testid="stHeader"],
[data-testid="stToolbar"],
[data-testid="stDecoration"] { display:none !important; }
/* Shared branded header displayed on EVERY page. */
.hg-brand-header {
    background:linear-gradient(125deg,#FFFFFF 0%,#EFF6FE 100%);
    border:1px solid #CFDFF0;
    border-left:5px solid var(--hg-secondary);
    padding:18px 28px 20px;
    border-radius:12px;
    margin-bottom:25px;
    box-shadow:0 5px 20px rgba(5,43,91,.05);
}
.hg-brand-header img { width:180px; max-width:100%; height:auto; display:block; }
.hg-brand-tagline { color:#416F66 !important; font-size:15px; margin-top:6px; line-height:1.45; font-weight:400 !important; }

/* ==========================================================
   TEAL ACCENTS — UPLOAD TEXT AND DOMAIN CHECKBOXES
   Keep Material Symbols icon font untouched.
   ========================================================== */
/* Upload field title, file instructions, and file-size/type text */
.stApp [data-testid="stFileUploader"] [data-testid="stWidgetLabel"] p,
.stApp [data-testid="stFileUploader"] label p,
.stApp [data-testid="stFileUploaderDropzoneInstructions"] p,
.stApp [data-testid="stFileUploaderDropzoneInstructions"] small,
.stApp [data-testid="stFileUploaderDropzoneInstructions"] span:not([data-testid="stIconMaterial"]):not(.material-symbols-rounded):not(.material-symbols-outlined) {
    color: #5B8F83 !important;
    -webkit-text-fill-color: #5B8F83 !important;
}
/* Keep Upload button readable: white text on navy, teal border */
.stApp [data-testid="stFileUploaderDropzone"] button {
    border-color: #5B8F83 !important;
}
.stApp [data-testid="stFileUploaderDropzone"] button,
.stApp [data-testid="stFileUploaderDropzone"] button span:not(.material-symbols-rounded):not(.material-symbols-outlined) {
    color: #FFFFFF !important;
    -webkit-text-fill-color: #FFFFFF !important;
}
/* Domain checkbox labels (Water, Land, Air, People, Select all) */
.stApp [data-testid="stCheckbox"] label p {
    color: #5B8F83 !important;
    -webkit-text-fill-color: #5B8F83 !important;
    font-weight: 600 !important;
}
/* Native checkbox and modern Streamlit/BaseWeb checked state */
.stApp [data-testid="stCheckbox"] input[type="checkbox"] {
    accent-color: #5B8F83 !important;
}
.stApp [data-testid="stCheckbox"] [data-baseweb="checkbox"] [aria-checked="true"] {
    background-color: #5B8F83 !important;
    border-color: #5B8F83 !important;
}


/* ==========================================================
   BRAND-CONSISTENT INTERACTIVE CONTROLS
   Streamlit/BaseWeb may use div-based controls instead of
   native checkbox inputs and may style form buttons separately.
   ========================================================== */

/* Checkboxes: teal square in both unchecked and checked states. */
.stApp [data-testid="stCheckbox"] [data-baseweb="checkbox"] > div:first-child,
.stApp [data-testid="stCheckbox"] [data-baseweb="checkbox"] [role="checkbox"],
.stApp [data-testid="stCheckbox"] label > div:first-child [role="checkbox"],
.stApp [data-testid="stCheckbox"] [data-baseweb="checkbox"] input + div {
    background-color: #E7F2EF !important;
    border-color: #5B8F83 !important;
    box-shadow: inset 0 0 0 1px #5B8F83 !important;
}
.stApp [data-testid="stCheckbox"] [data-baseweb="checkbox"]:has(input:checked) > div:first-child,
.stApp [data-testid="stCheckbox"] [data-baseweb="checkbox"] [aria-checked="true"],
.stApp [data-testid="stCheckbox"] [role="checkbox"][aria-checked="true"],
.stApp [data-testid="stCheckbox"] [data-baseweb="checkbox"] input:checked + div {
    background-color: #5B8F83 !important;
    border-color: #5B8F83 !important;
    box-shadow: none !important;
}
.stApp [data-testid="stCheckbox"] [data-baseweb="checkbox"] svg,
.stApp [data-testid="stCheckbox"] [role="checkbox"] svg {
    color: #FFFFFF !important;
    fill: #FFFFFF !important;
    stroke: #FFFFFF !important;
}
.stApp [data-testid="stCheckbox"] input[type="checkbox"] { accent-color: #5B8F83 !important; }

/* Radio selection controls (sidebar): teal instead of default red. */
.stApp [data-testid="stRadio"] [role="radio"][aria-checked="true"],
.stApp [data-testid="stRadio"] [data-baseweb="radio"]:has(input:checked) > div:first-child {
    border-color: #5B8F83 !important;
    accent-color: #5B8F83 !important;
}
.stApp [data-testid="stRadio"] input[type="radio"] { accent-color: #5B8F83 !important; }

/* Dropdowns: lighter ocean-blue surfaces and white readable selection. */
.stApp [data-testid="stSelectbox"] [data-baseweb="select"] > div,
.stApp [data-testid="stMultiSelect"] [data-baseweb="select"] > div,
.stApp [data-testid="stSelectbox"] [role="combobox"],
.stApp [data-testid="stMultiSelect"] [role="combobox"] {
    background: #0A4C91 !important;
    border: 1px solid #5B8F83 !important;
    border-radius: 8px !important;
    color: #FFFFFF !important;
}
.stApp [data-testid="stSelectbox"] [data-baseweb="select"] *,
.stApp [data-testid="stMultiSelect"] [data-baseweb="select"] * {
    color: #FFFFFF !important;
}
/* Dropdown options can render in an overlay outside .stApp. */
[data-baseweb="popover"] [role="option"][aria-selected="true"],
[data-baseweb="menu"] [role="option"][aria-selected="true"] {
    background: #DCEEE9 !important;
    color: #052B5B !important;
}

/* All app action buttons, including Streamlit FORM submit buttons.
   Use teal background + white text for high contrast. */
.stApp [data-testid="stFormSubmitButton"] button,
.stApp [data-testid="stBaseButton-primaryFormSubmit"] ,
.stApp [data-testid="stBaseButton-secondaryFormSubmit"],
.stApp [data-testid="stBaseButton-primary"],
.stApp [data-testid="stBaseButton-secondary"],
.stApp [data-testid="stButton"] > button,
.stApp .stButton > button,
.stApp .stFormSubmitButton > button {
    background-color: #0A4C91 !important;
    border: 1px solid #0A4C91 !important;
    color: #FFFFFF !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
}
.stApp [data-testid="stFormSubmitButton"] button *,
.stApp [data-testid="stBaseButton-primaryFormSubmit"] *,
.stApp [data-testid="stBaseButton-secondaryFormSubmit"] *,
.stApp [data-testid="stBaseButton-primary"] *,
.stApp [data-testid="stBaseButton-secondary"] *,
.stApp [data-testid="stButton"] button * {
    color: #FFFFFF !important;
    -webkit-text-fill-color: #FFFFFF !important;
}
.stApp [data-testid="stFormSubmitButton"] button:hover,
.stApp [data-testid="stButton"] button:hover,
.stApp [data-testid="stBaseButton-primary"]:hover,
.stApp [data-testid="stBaseButton-secondary"]:hover {
    background-color: #07376C !important;
    border-color: #5B8F83 !important;
}
/* Protect native uploader and its Material Symbols icon styling. */
.stApp [data-testid="stFileUploaderDropzone"] button {
    background: #0A4C91 !important;
    border-color: #5B8F83 !important;
}



/* ==============================================
   HYDROGUARD — EXPANDER HOVER FIX
   Navy: #052B5B
   Teal: #5B8F83
   ============================================== */

/* Expander container */
.stApp [data-testid="stExpander"] {
    background: #FFFFFF !important;
    border: 1px solid #CDDBEA !important;
    border-radius: 10px !important;
    overflow: hidden !important;
}

/* Normal header */
.stApp [data-testid="stExpander"] details > summary {
    background: #EAF1FA !important;
    background-image: none !important;
    color: #052B5B !important;
}

/* Hover, focus and keyboard navigation */
.stApp [data-testid="stExpander"] details > summary:hover,
.stApp [data-testid="stExpander"] details > summary:focus,
.stApp [data-testid="stExpander"] details > summary:focus-visible,
.stApp [data-testid="stExpander"] details:hover > summary {
    background: #E7F2EF !important;
    background-image: none !important;
    color: #052B5B !important;
}

/* Prevent inner Streamlit containers from
   displaying a dark hover background */
.stApp [data-testid="stExpander"] summary > div,
.stApp [data-testid="stExpander"] summary:hover > div,
.stApp [data-testid="stExpander"] summary:hover
[data-testid="stMarkdownContainer"] {
    background: transparent !important;
    background-color: transparent !important;
}

/* Expanded state */
.stApp [data-testid="stExpander"] details[open] > summary,
.stApp [data-testid="stExpander"] details[open] > summary:hover {
    background: #E7F2EF !important;
    background-image: none !important;
    border-bottom: 2px solid #5B8F83 !important;
}

/* Header text — always navy */
.stApp [data-testid="stExpander"] summary,
.stApp [data-testid="stExpander"] summary p,
.stApp [data-testid="stExpander"] summary span,
.stApp [data-testid="stExpander"] summary strong {
    color: #052B5B !important;
    -webkit-text-fill-color: #052B5B !important;
    opacity: 1 !important;
}

/* Keep header text navy on hover */
.stApp [data-testid="stExpander"] summary:hover,
.stApp [data-testid="stExpander"] summary:hover * {
    color: #052B5B !important;
    -webkit-text-fill-color: #052B5B !important;
}

/* Expander arrow — teal */
.stApp [data-testid="stExpander"] summary svg {
    color: #5B8F83 !important;
    stroke: #5B8F83 !important;
}

/* Evidence content */
.stApp [data-testid="stExpanderDetails"] {
    background: #FFFFFF !important;
    color: #102F53 !important;
}

.stApp [data-testid="stExpanderDetails"] p,
.stApp [data-testid="stExpanderDetails"] li {
    color: #102F53 !important;
    font-weight: 400 !important;
    line-height: 1.65 !important;
}

.stApp [data-testid="stExpanderDetails"] strong {
    color: #052B5B !important;
    font-weight: 700 !important;
}

</style>
"""


def render_brand_header() -> None:
    """Show the official HydroGuard logo across all workspace pages."""
    if not LOGO_PATH.is_file():
        st.error("HydroGuard logo file is missing: hydroguard/ui/assets/HydroGuard_Logo.png")
        return
    encoded_logo = base64.b64encode(LOGO_PATH.read_bytes()).decode("ascii")
    st.markdown(
        '<div class="hg-brand-header">'
        f'<img src="data:image/png;base64,{encoded_logo}" alt="HydroGuard logo" />'
        '<div class="hg-brand-tagline">'
        'See the claim. Trace the evidence. Challenge the gap. Know what to ask next.'
        '</div></div>',
        unsafe_allow_html=True,
    )


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
    st.set_page_config(page_title="HydroGuard · Evidence workspace", page_icon="🌊", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)
    render_brand_header()
    initialize_case_state()
    if LOGO_PATH.is_file():
        st.sidebar.image(str(LOGO_PATH), width=140)
    st.sidebar.markdown(
        "**Environmental Evidence Intelligence Workspace**\n\n"
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
