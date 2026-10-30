"""Word (.docx, transitional OOXML) text extraction with the standard library.

Stored text, in this order: main body, headers, footers, footnotes, endnotes (each part in
relationship-target order). Within a part: every paragraph ends with "\\n"; `w:tab`/`w:ptab` -> "\\t";
`w:br`/`w:cr` -> "\\n"; `w:noBreakHyphen` -> U+2011; `w:softHyphen` -> U+00AD; table cells are read
row by row; text boxes are read where they are anchored; field results are kept and field codes
dropped; for markup-compatibility blocks only the first `mc:Choice` is read (the fallback duplicates it).

Refused (fail closed): tracked changes (the text is ambiguous until accepted), symbol-font characters
(`w:sym`), embedded OLE objects and alt-chunks (text not extractable), DTDs, encrypted packages,
strict OOXML. Images and comments are not text: they are reported as warnings.
"""

import io
import re
import zipfile
from xml.etree import ElementTree as ET

from legalai_casefile._common import Extraction, single_page
from legalai_casefile.errors import (
    CorruptDocumentError,
    EncryptedDocumentError,
    FormatMismatchError,
    TooLargeError,
    UnsupportedContentError,
    UnsupportedFormatError,
)

MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
MAX_UNCOMPRESSED = 256 * 1024 * 1024
MAX_MEMBERS = 10_000

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_W_STRICT = "http://purl.oclc.org/ooxml/wordprocessingml/main"
_MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"
_M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
_R = "http://schemas.openxmlformats.org/package/2006/relationships"
_REL_BASE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/"
_OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


def _w(tag: str) -> str:
    return f"{{{_W}}}{tag}"


_SKIP = frozenset(
    _w(t)
    for t in (
        "pPr", "rPr", "sectPr", "tblPr", "trPr", "tcPr", "tblGrid", "tblPrEx", "sdtPr", "sdtEndPr",
        "instrText", "delInstrText", "bookmarkStart", "bookmarkEnd", "proofErr", "commentRangeStart",
        "commentRangeEnd", "commentReference", "annotationRef", "footnoteRef", "endnoteRef",
        "footnoteReference", "endnoteReference", "separator", "continuationSeparator",
        "lastRenderedPageBreak", "fldChar", "permStart", "permEnd",
    )
)  # fmt: skip
_TRACKED = frozenset(_w(t) for t in ("ins", "del", "moveFrom", "moveTo"))
_REFUSED = {
    _w("sym"): "symbol-font characters (w:sym)",
    _w("object"): "embedded objects",
    _w("altChunk"): "alt-chunks",
}
_CHARS = {
    _w("tab"): "\t",
    _w("ptab"): "\t",
    _w("br"): "\n",
    _w("cr"): "\n",
    _w("noBreakHyphen"): chr(0x2011),
    _w("softHyphen"): chr(0x00AD),
}
_TEXT = frozenset({_w("t"), f"{{{_M}}}t"})
_TXBX = _w("txbxContent")
_IMAGE_TAGS = frozenset(
    {
        "{http://schemas.openxmlformats.org/drawingml/2006/main}blip",
        "{urn:schemas-microsoft-com:vml}imagedata",
    }
)
_NOTE_SKIP_TYPES = frozenset({"separator", "continuationSeparator", "continuationNotice"})


class _Walker:
    def __init__(self) -> None:
        self.out: list[str] = []
        self.images = 0

    def walk(self, elem: ET.Element) -> None:
        for child in elem:
            tag = child.tag
            if tag in _SKIP:
                continue
            if tag in _TRACKED:
                raise UnsupportedContentError("tracked changes; accept or reject all changes first")
            if tag in _REFUSED:
                raise UnsupportedContentError(_REFUSED[tag])
            if tag in _TEXT:
                self.out.append(child.text or "")
            elif tag in _CHARS:
                self.out.append(_CHARS[tag])
            elif tag == _w("p"):
                self.walk(child)
                self.out.append("\n")
            elif tag == f"{{{_MC}}}AlternateContent":
                branch = child.find(f"{{{_MC}}}Choice")
                if branch is None:
                    branch = child.find(f"{{{_MC}}}Fallback")
                if branch is not None:
                    self.walk(branch)
            elif tag in (_w("drawing"), _w("pict")):
                self.images += sum(1 for e in child.iter() if e.tag in _IMAGE_TAGS)
                for box in _outer_textboxes(child):
                    self.walk(box)
            else:
                self.walk(child)


def _outer_textboxes(elem: ET.Element) -> list[ET.Element]:
    found: list[ET.Element] = []
    for child in elem:
        if child.tag == _TXBX:
            found.append(child)
        else:
            found.extend(_outer_textboxes(child))
    return found


def _parse_xml(zf: zipfile.ZipFile, name: str) -> ET.Element:
    raw = zf.read(name)
    if b"<!DOCTYPE" in raw or b"<!ENTITY" in raw:
        raise UnsupportedContentError("XML document type declarations are not allowed in .docx parts")
    try:
        return ET.fromstring(raw)
    except ET.ParseError as exc:
        raise CorruptDocumentError(f"malformed XML in part {name}") from exc


def _related_parts(zf: zipfile.ZipFile, kind: str) -> list[str]:
    rels_name = "word/_rels/document.xml.rels"
    if rels_name not in zf.namelist():
        return []
    rels = _parse_xml(zf, rels_name)
    targets = sorted(
        rel.get("Target", "")
        for rel in rels.iter(f"{{{_R}}}Relationship")
        if rel.get("Type") == _REL_BASE + kind and rel.get("TargetMode") != "External"
    )
    names = []
    for target in targets:
        name = target.lstrip("/") if target.startswith("/") else "word/" + target
        if name not in zf.namelist():
            raise CorruptDocumentError(f"missing part referenced as {kind}")
        names.append(name)
    return sorted(names, key=lambda n: [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", n)])


def extract_docx(data: bytes) -> Extraction:
    if data.startswith(_OLE_MAGIC):
        if "EncryptedPackage".encode("utf-16-le") in data:
            raise EncryptedDocumentError("password-protected Word document")
        raise UnsupportedFormatError("legacy binary Word (.doc) format; save as .docx")
    if not data.startswith(b"PK\x03\x04"):
        raise FormatMismatchError("not a ZIP-based .docx file")
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise CorruptDocumentError("damaged .docx archive") from exc
    with zf:
        infos = zf.infolist()
        if len(infos) > MAX_MEMBERS or sum(i.file_size for i in infos) > MAX_UNCOMPRESSED:
            raise TooLargeError(".docx archive expands beyond the size limit")
        if any(i.flag_bits & 0x1 for i in infos):
            raise EncryptedDocumentError("encrypted ZIP members")
        if "word/document.xml" not in zf.namelist():
            raise FormatMismatchError("ZIP file has no word/document.xml")
        try:
            return _extract(zf)
        except (zipfile.BadZipFile, KeyError, EOFError) as exc:
            raise CorruptDocumentError("damaged .docx archive") from exc


def _extract(zf: zipfile.ZipFile) -> Extraction:
    root = _parse_xml(zf, "word/document.xml")
    if root.tag.startswith(f"{{{_W_STRICT}}}"):
        raise UnsupportedFormatError("strict OOXML; save as a standard (transitional) .docx")
    body = root.find(_w("body"))
    if body is None:
        raise CorruptDocumentError("document.xml has no body")
    walker = _Walker()
    walker.walk(body)
    for kind in ("header", "footer"):
        for name in _related_parts(zf, kind):
            walker.walk(_parse_xml(zf, name))
    for kind, note in (("footnotes", "footnote"), ("endnotes", "endnote")):
        for name in _related_parts(zf, kind):
            for elem in _parse_xml(zf, name).iter(_w(note)):
                if elem.get(_w("type")) not in _NOTE_SKIP_TYPES:
                    walker.walk(elem)
    warnings = []
    if walker.images:
        warnings.append(f"{walker.images} image(s) not extracted")
    comments = _related_parts(zf, "comments")
    if any("".join(_parse_xml(zf, n).itertext()).strip() for n in comments):
        warnings.append("comments not extracted")
    return single_page("".join(walker.out), MEDIA_TYPE, "docx-ooxml stdlib", warnings)
