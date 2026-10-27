"""Clearly fictional project fixture, never a regulatory source or real community."""
from pathlib import Path
import json
from hashlib import sha256
from hydroguard.ingestion.pipeline import ingest, load_passages

CASE_ID = "riverside-water"
PROJECT_NAME = "Riverside Industrial Development (fictional)"
CLAIM = "The proposed water demand will not adversely affect existing water users."
PAGES = (
    """SYNTHETIC PROJECT DISCLOSURE - NOT A REAL PROJECT
Riverside Industrial Development
Fictional Water Evidence Case | Page 1 of 2

No actual company, community, watercourse or monitoring site is represented.
All quantities and observations below are invented demonstration inputs.

1. Proposed water demand
The fictional development proposes water demand of 120 cubic metres per day.
This is a planning estimate for this synthetic case, not a measured abstraction.

2. Wet-season baseline observations
A fictional three-visit wet-season survey records visible surface-water flow
and continued domestic and agricultural use at unnamed demonstration points.
The illustrative flow observation is 0.8 cubic metres per second on one visit.
No observation or figure represents a real field survey or scientific result.

3. Proponent assurance (fictional)
The proposed water demand will not adversely affect existing water users.
This is a claim to be audited, not HydroGuard's conclusion.
""",
    """SYNTHETIC PROJECT DISCLOSURE - NOT A REAL PROJECT
Riverside Industrial Development
Fictional Water Evidence Case | Page 2 of 2

4. Disclosed limitations
A complete dry-season water balance is not provided in this disclosure.
Quantified existing-user abstraction evidence is not provided in this disclosure.
The wet-season visits do not establish dry-season available supply or the
combined demand of the project and existing users during dry periods.
No dry-season gauging series, existing-user abstraction inventory, or cumulative
water-demand calculation is attached to this two-page synthetic disclosure.

5. Scope of the exercise
Missing information in this disclosure is not proof that studies do not exist
elsewhere. It is not proof of water shortage, environmental harm, illegality,
non-compliance, or entitlement to a particular regulatory outcome.
No regulatory requirement is asserted by this fictional project document.

Prepared as an explicitly synthetic HydroGuard demonstration input.
""",
)


def prepare(root: Path = Path("data/cases/riverside")) -> dict:
    import pymupdf
    source = root / "source/project/riverside_disclosure.pdf"
    source.parent.mkdir(parents=True, exist_ok=True)
    if source.exists():
        with pymupdf.open(source) as doc:
            actual = [" ".join(page.get_text().split()) for page in doc]
        if actual != [" ".join(text.split()) for text in PAGES]:
            raise ValueError("Existing Riverside document differs; refusing overwrite")
    else:
        doc = pymupdf.open()
        doc.set_metadata({"title": "Riverside Industrial Development - SYNTHETIC Water Disclosure",
                          "author": "HydroGuard synthetic demonstration fixture"})
        for text in PAGES:
            page = doc.new_page(width=595, height=842)
            remaining = page.insert_textbox(pymupdf.Rect(48, 48, 547, 794), text,
                                            fontsize=11, fontname="helv", lineheight=1.35)
            if remaining < 0:
                raise ValueError("Synthetic PDF overflow")
        doc.save(source, no_new_id=True, deflate=True)
        doc.close()
    catalog = root / "metadata.json"
    catalog.write_text(json.dumps({"project/riverside_disclosure.pdf": {
        "title": "Riverside Industrial Development - SYNTHETIC Water Disclosure",
        "title_reference": "Synthetic source PDF pages 1-2",
        "source_type": "project", "is_synthetic": True, "case_id": CASE_ID,
        "licence": "CC0; generated fictional demonstration text only",
        "licence_reference": "HydroGuard-authored fixture; no external content copied"}}, indent=2)+"\n")
    output = root / "processed"
    result = ingest(root/"source", output, catalog)
    records = load_passages(output/"passages.jsonl")
    payload = (json.dumps(list(records.values()), ensure_ascii=False, indent=2)+"\n").encode()
    snapshot = sha256(payload).hexdigest()[:16]
    filename = f"riverside_project_{snapshot}.json"
    (output/filename).write_bytes(payload)
    manifest = {"case_id":CASE_ID, "project_name":PROJECT_NAME, "claim":CLAIM,
                "filename":filename, "table":f"HYDROGUARD.riverside_project_{snapshot}",
                "path":f"dffs://{filename}", "passages":len(records),
                "source_ids":list(records), "sha256":sha256(payload).hexdigest()}
    (root/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    return manifest
