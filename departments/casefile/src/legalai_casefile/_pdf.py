"""PDF text extraction (pypdf) with fail-closed structural checks.

Library choice and evidence: REQ-PMO-0001 §8 and `tools/compare_pdf_extractors.py`.

Text comes from `pypdf.PageObject.extract_text()` (plain mode, content-stream order), unchanged.
Each page's text is followed by one form feed (`PAGE_TERMINATOR`). No other characters are added,
removed or changed.

pypdf (like every candidate measured) returns garbage or empty strings rather than errors for
unmappable fonts, image-only pages and invisible OCR layers, so this module walks every content
stream itself to detect them and refuses the file instead of returning incomplete text.
"""

import io
from bisect import bisect_right
from collections import Counter
from dataclasses import dataclass, field

import pypdf
from pypdf.generic import ArrayObject, ContentStream, DictionaryObject, IndirectObject

from legalai_casefile._cjk import CJK_MAPPING_VERSION, describe, is_compat_ideograph, map_radicals
from legalai_casefile._common import PAGE_TERMINATOR, Extraction, check_characters
from legalai_casefile.errors import (
    CorruptDocumentError,
    EmptyDocumentError,
    EncryptedDocumentError,
    FormatMismatchError,
    IntakeError,
    PartialExtractionError,
    ScannedDocumentError,
    UnsupportedContentError,
)

MEDIA_TYPE = "application/pdf"
LARGE_IMAGE_SHARE = 0.25
"""An image covering at least this share of the page may hold text we cannot read: refuse."""

_MAX_FORM_DEPTH = 16
_TEXT_SHOW = frozenset({b"Tj", b"TJ", b"'", b'"'})
_PAINT = frozenset({b"f", b"F", b"f*", b"B", b"B*", b"b", b"b*", b"S", b"s", b"sh"})
_INVISIBLE_MODES = frozenset({3, 7})
_STANDARD_LATIN_FONTS = frozenset(
    f"{family}{style}"
    for family, styles in (
        ("Helvetica", ("", "-Bold", "-Oblique", "-BoldOblique")),
        ("Courier", ("", "-Bold", "-Oblique", "-BoldOblique")),
        ("Times", ("-Roman", "-Bold", "-Italic", "-BoldItalic")),
    )
    for style in styles
)
_HARMLESS_ANNOTS = frozenset({"/Link", "/Popup"})
_TEXT_BEARING_ANNOTS = frozenset({"/Widget", "/FreeText"})


@dataclass
class _PageScan:
    text_shows: int = 0
    invisible_shows: int = 0
    unmapped_shows: int = 0
    paints: int = 0
    image_shares: list[float] = field(default_factory=list)


@dataclass
class _State:
    det: float = 1.0
    render_mode: int = 0
    font_unmapped: bool = False


def _resolve(obj: object) -> object:
    return obj.get_object() if isinstance(obj, IndirectObject) else obj


def _font_unmapped(font: object) -> bool:
    """True when pypdf cannot map this font's codes to Unicode reliably."""
    font = _resolve(font)
    if not isinstance(font, DictionaryObject):
        return True
    if "/ToUnicode" in font:
        return False
    subtype = font.get("/Subtype")
    if subtype in ("/Type0", "/Type3"):
        return True
    if "/Encoding" in font:
        return False
    base = str(font.get("/BaseFont", ""))
    base = base.split("+", 1)[-1].lstrip("/")
    return base not in _STANDARD_LATIN_FONTS


def _det(m: list[object]) -> float:
    a, b, c, d = (float(_resolve(v)) for v in m[:4])  # type: ignore[arg-type]
    return a * d - b * c


def _scan(
    content: ContentStream | None,
    resources: DictionaryObject,
    reader: pypdf.PdfReader,
    scan: _PageScan,
    base: _State,
    depth: int,
    seen: frozenset[int],
) -> None:
    if content is None:
        return
    if depth > _MAX_FORM_DEPTH:
        raise CorruptDocumentError("form XObjects nested too deeply")
    fonts = _resolve(resources.get("/Font", DictionaryObject()))
    xobjects = _resolve(resources.get("/XObject", DictionaryObject()))
    stack: list[_State] = []
    st = _State(base.det, base.render_mode, base.font_unmapped)
    for operands, operator in content.operations:
        if operator == b"q":
            stack.append(_State(st.det, st.render_mode, st.font_unmapped))
        elif operator == b"Q":
            if stack:
                st = stack.pop()
        elif operator == b"cm":
            st.det *= _det(operands)
        elif operator == b"Tr":
            st.render_mode = int(operands[0])
        elif operator == b"Tf":
            font = fonts.get(operands[0]) if isinstance(fonts, DictionaryObject) else None
            st.font_unmapped = _font_unmapped(font)
        elif operator in _TEXT_SHOW:
            scan.text_shows += 1
            if st.render_mode in _INVISIBLE_MODES:
                scan.invisible_shows += 1
            if st.font_unmapped:
                scan.unmapped_shows += 1
        elif operator in _PAINT:
            scan.paints += 1
        elif operator == b"INLINE IMAGE":
            scan.image_shares.append(abs(st.det))
        elif operator == b"Do":
            if not isinstance(xobjects, DictionaryObject) or operands[0] not in xobjects:
                raise CorruptDocumentError("content refers to a missing XObject")
            ref = xobjects.raw_get(operands[0])
            xobj = _resolve(ref)
            if not isinstance(xobj, DictionaryObject):
                raise CorruptDocumentError("malformed XObject")
            subtype = xobj.get("/Subtype")
            if subtype == "/Image":
                scan.image_shares.append(abs(st.det))
            elif subtype == "/Form":
                ident = ref.idnum if isinstance(ref, IndirectObject) else id(xobj)
                if ident in seen:
                    raise CorruptDocumentError("form XObject refers to itself")
                matrix = xobj.get("/Matrix")
                det = st.det * (_det(list(matrix)) if isinstance(matrix, ArrayObject) else 1.0)
                form_res = _resolve(xobj.get("/Resources", resources))
                _scan(
                    ContentStream(xobj, reader),
                    form_res if isinstance(form_res, DictionaryObject) else resources,
                    reader,
                    scan,
                    _State(det, st.render_mode, st.font_unmapped),
                    depth + 1,
                    seen | {ident},
                )


def _check_catalog(reader: pypdf.PdfReader) -> None:
    root = _resolve(reader.trailer["/Root"])
    if not isinstance(root, DictionaryObject):
        raise CorruptDocumentError("PDF has no document catalog")
    oc = _resolve(root.get("/OCProperties"))
    if isinstance(oc, DictionaryObject):
        default = _resolve(oc.get("/D"))
        off = _resolve(default.get("/OFF")) if isinstance(default, DictionaryObject) else None
        if isinstance(off, ArrayObject) and len(off) > 0:
            raise UnsupportedContentError("hidden optional-content layers; their text is ambiguous")
    acroform = _resolve(root.get("/AcroForm"))
    if isinstance(acroform, DictionaryObject) and "/XFA" in acroform:
        raise UnsupportedContentError("XFA form; flatten or print to PDF first")


def _annotation_findings(page: pypdf.PageObject) -> tuple[bool, int]:
    """(has text-bearing annotations, number of other non-trivial annotations)."""
    annots = _resolve(page.get("/Annots"))
    if not isinstance(annots, ArrayObject):
        return False, 0
    text_bearing, other = False, 0
    for annot in annots:
        annot = _resolve(annot)
        if not isinstance(annot, DictionaryObject):
            continue
        subtype = annot.get("/Subtype")
        if subtype in _TEXT_BEARING_ANNOTS:
            text_bearing = True
        elif subtype not in _HARMLESS_ANNOTS:
            other += 1
    return text_bearing, other


def extract_pdf(data: bytes) -> Extraction:
    """Extract every page of a text-layer PDF, or raise a typed `IntakeError`."""
    if b"%PDF-" not in data[:1024]:
        raise FormatMismatchError("file does not start with a PDF header")
    try:
        return _extract(data)
    except IntakeError:
        raise
    except Exception as exc:
        # Any parser failure means the text cannot be trusted; refuse the file.
        raise CorruptDocumentError(f"PDF could not be parsed ({type(exc).__name__})") from exc


def _extract(data: bytes) -> Extraction:
    reader = pypdf.PdfReader(io.BytesIO(data), strict=True)
    if reader.is_encrypted:
        raise EncryptedDocumentError("PDF is encrypted")
    _check_catalog(reader)
    if len(reader.pages) == 0:
        raise EmptyDocumentError("PDF has no pages")

    texts: list[str] = []
    scanned: list[int] = []
    partial: dict[str, list[int]] = {}
    unsupported: list[int] = []
    blank: list[int] = []
    small_images: list[int] = []
    other_annots: list[int] = []
    for number, page in enumerate(reader.pages, start=1):
        text = page.extract_text()
        scan = _PageScan()
        res = _resolve(page.get("/Resources", DictionaryObject()))
        _scan(
            page.get_contents(),
            res if isinstance(res, DictionaryObject) else DictionaryObject(),
            reader,
            scan,
            _State(),
            0,
            frozenset(),
        )
        box = page.cropbox
        area = abs(float(box.width) * float(box.height)) or 1.0
        shares = [s / area for s in scan.image_shares]
        text_bearing, others = _annotation_findings(page)
        has_text = bool(text.strip())

        if scan.invisible_shows or (shares and not has_text):
            scanned.append(number)
        elif text_bearing:
            unsupported.append(number)
        elif scan.unmapped_shows:
            partial.setdefault("font without a Unicode mapping", []).append(number)
        elif any(s >= LARGE_IMAGE_SHARE for s in shares):
            partial.setdefault(f"image covering >= {LARGE_IMAGE_SHARE:.0%} of the page", []).append(number)
        elif not has_text and (scan.text_shows or scan.paints):
            partial.setdefault("text or graphics drawn but no text extracted", []).append(number)
        else:
            try:
                check_characters(text, page=number)
            except (PartialExtractionError, UnsupportedContentError):
                partial.setdefault("undecodable or symbol-font characters", []).append(number)
            if not has_text:
                blank.append(number)
        if shares:
            small_images.append(number)
        if others:
            other_annots.append(number)
        texts.append(text)

    if scanned:
        raise ScannedDocumentError(
            "image-only page(s) or an invisible (OCR) text layer; OCR is not supported in v1",
            pages=tuple(scanned),
        )
    if unsupported:
        raise UnsupportedContentError(
            "form fields or free-text annotations whose text is not in the page content; flatten first",
            pages=tuple(unsupported),
        )
    if partial:
        raise PartialExtractionError(
            "text could not be extracted completely: "
            + "; ".join(f"{why} on page(s) {_pages(pages)}" for why, pages in partial.items()),
            pages=tuple(sorted({p for pages in partial.values() for p in pages})),
        )
    if len(blank) == len(texts):
        raise EmptyDocumentError("PDF has no text on any page")

    warnings: list[str] = []
    if blank:
        warnings.append(f"blank page(s) with nothing drawn: {_pages(blank)}")
    if small_images:
        warnings.append(
            f"image(s) not extracted (e.g. seal, signature, logo) on page(s) {_pages(small_images)}"
        )
    if other_annots:
        warnings.append(f"annotations (comments, stamps) not extracted on page(s) {_pages(other_annots)}")

    starts: list[int] = []
    offset = 0
    for text in texts:
        starts.append(offset)
        offset += len(text) + len(PAGE_TERMINATOR)
    raw = "".join(t + PAGE_TERMINATOR for t in texts)

    # REQ-PMO-0009: font maps that name radicals instead of ideographs. Mapped 1:1 and recorded.
    full, subs, unmappable = map_radicals(raw)
    if unmappable:
        found = Counter((raw[o], "") for o in unmappable)
        raise PartialExtractionError(
            f"{len(unmappable)} CJK radical code point(s) with no equivalent unified ideograph "
            f"({describe(found)})",
            pages=tuple(sorted({bisect_right(starts, o) for o in unmappable})),
        )
    if subs:
        pairs = Counter((s.original, s.replacement) for s in subs)
        warnings.append(
            f"PDF font map produced {len(subs)} CJK radical code point(s) in place of ideographs; mapped 1:1 "
            f"with {CJK_MAPPING_VERSION}, every position recorded: {describe(pairs)}"
        )
    compat = Counter((ch, "") for ch in full if is_compat_ideograph(ch))
    if compat:
        warnings.append(
            f"{compat.total()} CJK compatibility ideograph(s) kept unchanged (distinct forms; searches "
            f"for the unified ideograph will not match them): {describe(compat)}"
        )
    return Extraction(
        full,
        tuple(starts),
        MEDIA_TYPE,
        f"pypdf {pypdf.__version__}",
        tuple(warnings),
        substitutions=subs,
        substitution_table=CJK_MAPPING_VERSION if subs else None,
    )


def _pages(pages: list[int]) -> str:
    return ", ".join(map(str, pages))
