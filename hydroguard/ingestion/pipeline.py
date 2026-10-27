"""Private, deterministic extraction and citation indexing. No OCR or legal inference."""
import csv
from hashlib import sha256
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Metadata(BaseModel):
    model_config = ConfigDict(extra="forbid")
    is_synthetic: bool = False
    case_id: str | None = None
    title: str | None = None
    title_reference: str | None = None
    source_type: Literal["regulatory", "scientific", "project", "community", "unknown"] = "unknown"
    issuing_body_or_author: str | None = None
    author_reference: str | None = None
    publication_or_effective_date: str | None = None
    date_reference: str | None = None
    original_source_url: str | None = None
    url_reference: str | None = None
    licence: str = "unverified; do not redistribute"
    licence_reference: str | None = None

    @model_validator(mode="after")
    def require_verification_references(self):
        for value, reference in ((self.title, self.title_reference),
                                  (self.issuing_body_or_author, self.author_reference),
                                  (self.publication_or_effective_date, self.date_reference),
                                  (self.original_source_url, self.url_reference)):
            if value and not reference:
                raise ValueError("Curated metadata requires a verification reference")
        return self


def digest(value: bytes) -> str:
    return sha256(value).hexdigest()


def extract(path: Path) -> tuple[list[dict], list[dict]]:
    units, flags = [], []
    if path.suffix.lower() == ".pdf":
        import pymupdf
        with pymupdf.open(path) as pdf:
            if pdf.needs_pass:
                return [], [{"reason": "encrypted_pdf_requires_password"}]
            for number, page in enumerate(pdf, 1):
                text = page.get_text("text", sort=True)
                images = page.get_image_info()
                image_area = sum(pymupdf.Rect(image["bbox"]).get_area() for image in images)
                # A sparse text layer over a large image is not trustworthy OCR.
                suspect = not text.strip() or image_area > page.rect.get_area() * .5
                if suspect:
                    flags.append({"page": number, "reason": "possible_scan_or_textless_page_needs_ocr_or_manual_review"})
                    continue
                units.append({"page": number, "section": None, "paragraph": None,
                              "locator": f"pdf-page:{number}", "text": text})
    elif path.suffix.lower() == ".docx":
        from docx import Document
        from docx.table import Table
        doc = Document(path)
        paragraph_number, table_number = 0, 0
        headings = {}
        for block in doc.iter_inner_content():
            if isinstance(block, Table):
                table_number += 1
                seen = set()
                for row_number, row in enumerate(block.rows, 1):
                    for cell_number, cell in enumerate(row.cells, 1):
                        if cell._tc in seen:
                            continue
                        seen.add(cell._tc)
                        for index, paragraph in enumerate(cell.paragraphs, 1):
                            if paragraph.text.strip():
                                units.append({"page": None, "section": " / ".join(headings.values()) or None,
                                              "paragraph": None,
                                              "locator": f"docx-table:{table_number}:row:{row_number}:cell:{cell_number}:paragraph:{index}",
                                              "text": paragraph.text})
            else:
                paragraph_number += 1
                style = block.style.name if block.style else ""
                if style.startswith("Heading ") and style[8:].isdigit():
                    level = int(style[8:])
                    headings = {k: v for k, v in headings.items() if k < level}
                    headings[level] = block.text
                if block.text.strip():
                    units.append({"page": None, "section": " / ".join(headings.values()) or None,
                                  "paragraph": paragraph_number,
                                  "locator": f"docx-paragraph:{paragraph_number}", "text": block.text})
        flags.append({"reason": "docx_pages_unavailable; headings_and_body_or_table_paragraph_locators_used; headers_footers_textboxes_not_extracted"})
    else:
        flags.append({"reason": "unsupported_format"})
    return units, flags


def split_unit(text: str, max_chars: int = 1200):
    if max_chars < 100:
        raise ValueError("max_chars must be at least 100")
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            boundary = max(text.rfind("\n", start + max_chars // 2, end), text.rfind(" ", start + max_chars // 2, end))
            if boundary > start:
                end = boundary + 1
        if text[start:end].strip():
            yield start, end, text[start:end]
        start = end


def ingest(root: Path, output: Path, catalog: Path | None = None, max_chars: int = 1200) -> dict:
    if not root.is_dir():
        raise ValueError("Knowledge directory does not exist")
    if max_chars < 100:
        raise ValueError("max_chars must be at least 100")
    if output.resolve() == root.resolve() or root.resolve() in output.resolve().parents:
        raise ValueError("Output must be outside the source directory")
    curated = json.loads(catalog.read_text()) if catalog else {}
    documents, chunks, inventory = {}, {}, []
    files = sorted(p for p in root.rglob("*") if p.is_file() and not p.is_symlink())
    for path in files:
        if path.suffix.lower() not in (".pdf", ".docx"):
            continue
        relative = path.relative_to(root).as_posix()
        content_hash = digest(path.read_bytes())
        document_id = "doc-" + content_hash
        item = {"original_filename": path.name, "relative_path": relative,
                "bytes": path.stat().st_size, "document_id": document_id}
        if document_id in documents:
            documents[document_id]["aliases"].append(relative)
            inventory.append({**item, "status": "duplicate_content_not_reindexed"})
            continue
        supplied = curated.get(relative, {})
        metadata = Metadata.model_validate(supplied)
        folder_type = path.relative_to(root).parts[0]
        source_type = metadata.source_type
        if source_type == "unknown" and folder_type in ("regulatory", "scientific", "project", "community"):
            source_type = folder_type
        document = {**item, **metadata.model_dump(), "source_type": source_type,
                    "source_type_basis": "curated_catalog" if "source_type" in supplied else "directory_label_unverified",
                    "title": metadata.title or path.stem,
                    "title_status": "curated_with_reference" if metadata.title else "filename_fallback_unverified",
                    "content_sha256": content_hash, "aliases": [relative],
                    "extraction_policy": "pymupdf-sort-text/docx-body-v1", "chunk_policy": f"locator-char-v1-{max_chars}"}
        try:
            units, flags = extract(path)
            status = "extracted" if units else "needs_review"
        except Exception as error:
            # Do not log document contents or parser exception messages.
            units, flags, status = [], [{"reason": "extraction_failed", "error_type": type(error).__name__}], "failed"
        document.update(status=status, review_flags=flags, extracted_units=len(units))
        documents[document_id] = document
        inventory.append({**item, "status": status, "extracted_units": len(units), "review_flags": flags})
        for unit in units:
            for start, end, text in split_unit(unit["text"], max_chars):
                chunk_id = "chunk-" + digest(f"{document_id}:{document['chunk_policy']}:{unit['locator']}:{start}:{end}:{digest(text.encode())}".encode())
                chunks[chunk_id] = {"chunk_id": chunk_id, "document_id": document_id,
                                    "original_filename": path.name, "relative_path": relative,
                                    "title": document["title"], "title_status": document["title_status"],
                                    "source_type": source_type, "source_type_basis": document["source_type_basis"],
                                    **{k: getattr(metadata, k) for k in Metadata.model_fields if k not in ("title", "source_type")},
                                    "page": unit["page"], "section": unit["section"], "paragraph": unit["paragraph"],
                                    "locator": unit["locator"], "char_start": start, "char_end": end,
                                    "text": text, "content_sha256": content_hash}
    output.mkdir(parents=True, exist_ok=True)
    def write(name, text):
        temporary = output / (name + ".tmp")
        temporary.write_text(text, encoding="utf-8")
        temporary.replace(output / name)
    write("documents.json", json.dumps(list(documents.values()), ensure_ascii=False, indent=2) + "\n")
    write("inventory.json", json.dumps(inventory, ensure_ascii=False, indent=2) + "\n")
    write("passages.jsonl", "".join(json.dumps(chunk, ensure_ascii=False) + "\n" for chunk in chunks.values()))
    if chunks:
        temporary = output / "passages.csv.tmp"
        with temporary.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(next(iter(chunks.values()))))
            writer.writeheader()
            writer.writerows(chunks.values())
        temporary.replace(output / "passages.csv")
    else:
        write("passages.csv", "chunk_id,document_id,text\n")
    return {"documents": len(documents), "passages": len(chunks), "inventory": inventory}


def load_passages(path: Path) -> dict[str, dict]:
    records = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record["chunk_id"] in records:
            raise ValueError("Duplicate citation ID")
        records[record["chunk_id"]] = record
    return records


def retrieve_passages(records: dict[str, dict], query: str, limit: int = 5, source_type: str | None = None) -> list[dict]:
    """Explicit LOCAL lexical preview; never a live Zetaris fallback."""
    import re
    terms = set(re.findall(r"\w+", query.lower())) - {"the", "and", "of", "a", "in", "for"}
    scored = []
    for record in records.values():
        if source_type and record["source_type"] != source_type:
            continue
        words = set(re.findall(r"\w+", record["text"].lower()))
        score = len(terms & words)
        if score:
            scored.append((score, record["chunk_id"], record))
    return [r for _, _, r in sorted(scored, key=lambda row: (-row[0], row[1]))[:max(0, limit)]]
