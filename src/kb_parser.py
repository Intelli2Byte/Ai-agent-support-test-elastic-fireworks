import re
from pathlib import Path

import yaml

FRONT_MATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
SECTION_SPLIT_RE = re.compile(r"\n(?=## )", re.MULTILINE)

DOC_TYPE_BY_FILENAME = {
    "11-product-care.md": "care_guide",
    "12-breeze-tumbler-product-card.md": "product",
    "13-support-escalation.md": "internal_ops",
    "14-internal-content-migration-notes.md": "internal_notes",
}


def parse_front_matter(raw: str) -> tuple[dict, str]:
    match = FRONT_MATTER_RE.match(raw)
    if not match:
        return {}, raw.strip()
    meta = yaml.safe_load(match.group(1)) or {}
    body = raw[match.end():].strip()
    return meta, body


def derive_doc_type(filename: str, meta: dict) -> str:
    if filename in DOC_TYPE_BY_FILENAME:
        return DOC_TYPE_BY_FILENAME[filename]
    if meta.get("policy_authority") == "official":
        return "policy"
    return "other"


def chunk_document(path: Path) -> list[dict]:
    raw = path.read_text(encoding="utf-8")
    meta, body = parse_front_matter(raw)
    title = meta.get("title", path.stem)
    doc_type = derive_doc_type(path.name, meta)

    base_meta = {
        "filename": path.name,
        "document_id": str(meta.get("document_id", "")),
        "status": str(meta.get("status", "unknown")),
        "doc_type": doc_type,
        "audience": str(meta.get("audience", "")),
        "policy_authority": str(meta.get("policy_authority", "")),
        "title": str(title),
    }

    chunks = []
    sections = SECTION_SPLIT_RE.split("\n" + body)
    for section in sections:
        text = section.strip()
        if not text:
            continue
        first_line = text.splitlines()[0].strip()
        if first_line.startswith("## "):
            heading = first_line[3:].strip()
        elif first_line.startswith("# "):
            heading = first_line[2:].strip()
        else:
            heading = title
        chunks.append({**base_meta, "heading": heading, "text": text})
    return chunks


def load_all_chunks(kb_dir: Path) -> dict[str, list[dict]]:
    by_file = {}
    for path in sorted(kb_dir.glob("*.md")):
        by_file[path.name] = chunk_document(path)
    return by_file
