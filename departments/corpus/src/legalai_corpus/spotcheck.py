"""Spot check (REQ-PMO-0002 AC3): stored article text vs the raw official file, by an independent path.

Offline: reads the stored raw object (hash-verified) recorded in the version's provenance. Independent:
HTML is re-parsed with lxml (not the stdlib parser used for ingestion) and paragraphs are rebuilt by a
separate implementation of normalization.md N1-N3; a unit matches only if its text equals a run of whole
independent paragraphs ("\\n"-delimited), character for character. PDF is re-read with pypdf (not
pdfminer) and compared ignoring whitespace only, because PDF line layout carries no paragraph semantics.
"""

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from legalai_corpus.fetch import RawStore
from legalai_corpus.store import FileSourceStore

_WS = re.compile(r"[ \t\n\r\f]+")
_BLOCK = frozenset(
    [
        "p",
        "div",
        "br",
        "li",
        "ul",
        "ol",
        "tr",
        "td",
        "th",
        "table",
        "tbody",
        "thead",
        "tfoot",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "section",
        "article",
        "center",
        "blockquote",
        "pre",
        "dd",
        "dt",
        "dl",
        "hr",
        "header",
        "footer",
        "caption",
    ]
)
_SKIP = frozenset(["script", "style", "noscript", "template"])


def _lxml_paragraphs(raw: bytes, encoding: str, attr: str, value: str) -> list[str]:
    import lxml.html  # type: ignore[import-untyped]

    root: Any = lxml.html.document_fromstring(raw.decode(encoding))
    if attr == "class":
        hits = root.xpath(f"//*[contains(concat(' ', normalize-space(@class), ' '), ' {value} ')]")
    else:
        hits = root.xpath(f"//*[@{attr}=$v]", v=value)
    if not hits:
        raise ValueError(f"independent parser: container {attr}={value} not found")
    paragraphs: list[str] = []
    buf: list[str] = []

    def flush() -> None:
        paragraphs.append(_WS.sub(" ", "".join(buf)).strip())
        buf.clear()

    def walk(el: Any) -> None:
        tag = el.tag if isinstance(el.tag, str) else ""
        if tag in _SKIP:
            return
        if tag in _BLOCK:
            flush()
        if el.text and tag not in ("",):
            buf.append(el.text)
        for child in el:
            walk(child)
            if child.tail:
                buf.append(child.tail)
        if tag in _BLOCK:
            flush()

    walk(hits[0])
    flush()
    return [p for p in paragraphs if p]


def _pypdf_text(raw: bytes) -> str:
    import io

    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(raw))
    return "".join(page.extract_text() or "" for page in reader.pages)


def check_unit(
    store: FileSourceStore, raw_store: RawStore, doc_id: str, version_id: str, pinpoint: str
) -> dict[str, object]:
    """Compare one stored unit with the official raw file. Returns a result row (never raises on mismatch)."""
    units = [u for u in store.get_units(doc_id, version_id) if u.pinpoint == pinpoint]
    if len(units) != 1:
        return {
            "doc_id": doc_id,
            "version_id": version_id,
            "pinpoint": pinpoint,
            "match": False,
            "detail": f"{len(units)} units with this pinpoint",
        }
    unit = units[0]
    stored = store.get_text(doc_id, version_id, unit.start, unit.end)
    prov = store.get_provenance(doc_id, version_id)
    raw_info: dict[str, Any] = prov["raw"]  # type: ignore[assignment]
    rule: dict[str, Any] = prov["extraction_rule"]  # type: ignore[assignment]
    raw = raw_store.read_object(str(raw_info["sha256"]))
    numbering_ok = unit.kind != "article" or stored.startswith(unit.label)
    if rule["format"] == "html":
        html = rule["html"]
        paragraphs = _lxml_paragraphs(raw, html["encoding"], *html["container_attr"])
        haystack = "\n" + "\n".join(paragraphs) + "\n"
        content_ok = ("\n" + stored + "\n") in haystack
        method = "lxml re-parse of raw HTML, independent paragraph rebuild, exact match on whole paragraphs"
    else:
        content_ok = _WS.sub("", stored) in _WS.sub("", _pypdf_text(raw))
        method = "pypdf re-read of raw PDF, whitespace-insensitive substring"
    return {
        "doc_id": doc_id,
        "version_id": version_id,
        "pinpoint": pinpoint,
        "chars": len(stored),
        "unit_sha256": hashlib.sha256(stored.encode("utf-8")).hexdigest(),
        "official_url": raw_info["final_url"],
        "raw_sha256": raw_info["sha256"],
        "method": method,
        "numbering_ok": numbering_ok,
        "content_ok": content_ok,
        "match": numbering_ok and content_ok,
    }


def run_spotcheck(data_dir: Path, checks_path: Path) -> list[dict[str, object]]:
    """Run every check in a JSON file `{"checks": [{"doc_id", "version_id", "pinpoint"}, ...]}`."""
    checks = json.loads(checks_path.read_text(encoding="utf-8"))["checks"]
    store = FileSourceStore(data_dir)
    raw_store = RawStore(Path(data_dir) / "corpus")
    return [check_unit(store, raw_store, c["doc_id"], c["version_id"], c["pinpoint"]) for c in checks]
