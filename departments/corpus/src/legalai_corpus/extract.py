"""Mechanical text extraction from official raw files. Rules: departments/corpus/docs/normalization.md.

Nothing here edits wording. The only transformations are the documented whitespace/paragraph rules
(NORMALIZATION_VERSION). Every failure to locate the configured content raises ExtractionError.
"""

import io
import re
import statistics
import unicodedata
from dataclasses import dataclass
from html.parser import HTMLParser

NORMALIZATION_VERSION = "corpus-norm-1"

_ASCII_WS = re.compile(r"[ \t\n\r\f]+")
BLOCK_TAGS = frozenset(
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
VOID_TAGS = frozenset(
    [
        "br",
        "img",
        "hr",
        "meta",
        "input",
        "link",
        "area",
        "base",
        "col",
        "embed",
        "source",
        "track",
        "wbr",
        "param",
    ]
)
SKIP_TAGS = frozenset(["script", "style", "noscript", "template"])


class ExtractionError(Exception):
    """The configured content could not be extracted unambiguously. Never silently degraded."""


@dataclass(frozen=True)
class HtmlRule:
    """Where the legal text lives in an HTML page.

    `container_attr` = (attribute, value): the first element whose attribute equals `value` (for
    `class`, contains the class token). `start_marker` / `end_marker`, if given, must each occur exactly
    once in the container text; the text is cut to start at the start marker and end after the end marker.
    """

    container_attr: tuple[str, str]
    encoding: str = "utf-8"
    start_marker: str | None = None
    end_marker: str | None = None


@dataclass(frozen=True)
class PdfRule:
    """How to read an official PDF. `drop_line_patterns` remove running headers / page numbers (regex,
    full-line match after whitespace trim). Paragraph breaks follow normalization.md §3."""

    drop_line_patterns: tuple[str, ...] = ()
    start_marker: str | None = None
    end_marker: str | None = None
    indent_chars: float = 1.5


def normalize_paragraph(raw: str) -> str:
    """Rule N1/N2: collapse ASCII whitespace runs to one space, then trim Unicode whitespace at both ends."""
    return _ASCII_WS.sub(" ", raw).strip()


def join_paragraphs(paragraphs: list[str]) -> str:
    """Rule N3: drop empty paragraphs, join with a single '\\n', no trailing newline."""
    return "\n".join(p for p in paragraphs if p)


def cut_markers(text: str, start: str | None, end: str | None) -> str:
    """Rule N4: cut to [start marker, end of end marker]. Each marker must occur exactly once."""
    begin = 0
    if start is not None:
        if text.count(start) != 1:
            raise ExtractionError(f"start marker occurs {text.count(start)} times (need exactly 1)")
        begin = text.index(start)
    stop = len(text)
    if end is not None:
        tail = text[begin:]
        if tail.count(end) != 1:
            raise ExtractionError(f"end marker occurs {tail.count(end)} times after start (need exactly 1)")
        stop = begin + tail.index(end) + len(end)
    result = text[begin:stop]
    if not result:
        raise ExtractionError("extracted text is empty")
    return result


class _HtmlContainerText(HTMLParser):
    def __init__(self, rule: HtmlRule) -> None:
        super().__init__(convert_charrefs=True)
        self._attr, self._value = rule.container_attr
        self._stack: list[str] = []  # open tags inside the container (container tag at index 0)
        self._skip = 0
        self._buf: list[str] = []
        self.paragraphs: list[str] = []
        self.found = False
        self.done = False

    def _matches(self, attrs: list[tuple[str, str | None]]) -> bool:
        for name, value in attrs:
            if name != self._attr or value is None:
                continue
            if name == "class":
                if self._value in value.split():
                    return True
            elif value == self._value:
                return True
        return False

    def _break(self) -> None:
        self.paragraphs.append(normalize_paragraph("".join(self._buf)))
        self._buf = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.done:
            return
        if not self._stack:
            if not self.found and tag not in VOID_TAGS and self._matches(attrs):
                self.found = True
                self._stack.append(tag)
            return
        if tag in SKIP_TAGS:
            self._skip += 1
        if tag in BLOCK_TAGS:
            self._break()
        if tag not in VOID_TAGS:
            self._stack.append(tag)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._stack and not self.done and tag in BLOCK_TAGS:
            self._break()

    def handle_endtag(self, tag: str) -> None:
        if not self._stack or self.done or tag not in self._stack:
            return
        while self._stack:
            open_tag = self._stack.pop()
            if open_tag in SKIP_TAGS:
                self._skip -= 1
            if open_tag in BLOCK_TAGS:
                self._break()
            if open_tag == tag:
                break
        if not self._stack:
            self._break()
            self.done = True

    def handle_data(self, data: str) -> None:
        if self._stack and not self.done and self._skip == 0:
            self._buf.append(data)


def extract_html(raw: bytes, rule: HtmlRule) -> str:
    """Return the normalized text of the configured container of an official HTML page."""
    try:
        html = raw.decode(rule.encoding, errors="strict")
    except UnicodeDecodeError as err:
        raise ExtractionError(f"raw file is not valid {rule.encoding}: {err}") from err
    parser = _HtmlContainerText(rule)
    parser.feed(html)
    parser.close()
    if not parser.found:
        raise ExtractionError(f"container {rule.container_attr} not found")
    if not parser.done:
        raise ExtractionError(f"container {rule.container_attr} is never closed")
    return cut_markers(join_paragraphs(parser.paragraphs), rule.start_marker, rule.end_marker)


@dataclass(frozen=True)
class PdfLine:
    page: int
    x0: float
    x1: float
    text: str
    char_width: float


def pdf_lines(raw: bytes) -> list[PdfLine]:
    """Text lines of a PDF in reading order as reported by pdfminer.six (one per LTTextLine)."""
    from pdfminer.high_level import extract_pages
    from pdfminer.layout import LAParams, LTChar, LTTextContainer, LTTextLine

    lines: list[PdfLine] = []
    for page_no, page in enumerate(extract_pages(io.BytesIO(raw), laparams=LAParams()), start=1):
        for box in page:
            if not isinstance(box, LTTextContainer):
                continue
            for line in box:
                if not isinstance(line, LTTextLine):
                    continue
                widths = [c.width for c in line if isinstance(c, LTChar) and c.width > 0]
                text = line.get_text().rstrip("\n")
                if text.strip():
                    width = statistics.median(widths) if widths else 10.0
                    lines.append(PdfLine(page_no, line.x0, line.x1, text, width))
    return lines


def extract_pdf(raw: bytes, rule: PdfRule) -> str:
    """Return normalized text of an official PDF (normalization.md §3: line joining by indentation)."""
    drops = [re.compile(p) for p in rule.drop_line_patterns]
    body = [ln for ln in pdf_lines(raw) if not any(d.fullmatch(ln.text.strip()) for d in drops)]
    if not body:
        raise ExtractionError("PDF has no text layer (OCR is out of scope)")
    margins: dict[int, float] = {}
    for ln in body:
        margins[ln.page] = min(margins.get(ln.page, ln.x0), ln.x0)
    paragraphs: list[str] = []
    buf = ""
    for ln in body:
        indented = ln.x0 - margins[ln.page] >= rule.indent_chars * ln.char_width
        piece = normalize_paragraph(ln.text)
        if indented and buf:
            paragraphs.append(normalize_paragraph(buf))
            buf = ""
        buf += piece
    paragraphs.append(normalize_paragraph(buf))
    return cut_markers(join_paragraphs(paragraphs), rule.start_marker, rule.end_marker)


# Code points that a PDF font map (or a careless source) can substitute for ordinary ideographs.
# They render identically but differ by code point, so quote matching would silently fail (or succeed
# against the wrong text). Ingestion never stores them silently (normalization.md N6).
COMPAT_RANGES: tuple[tuple[int, int, str], ...] = (
    (0x2E80, 0x2EFF, "CJK Radicals Supplement"),
    (0x2F00, 0x2FDF, "Kangxi Radicals"),
    (0xF900, 0xFAFF, "CJK Compatibility Ideographs"),
    (0x2F800, 0x2FA1F, "CJK Compatibility Ideographs Supplement"),
)


def compat_block(ch: str) -> str | None:
    cp = ord(ch)
    for lo, hi, name in COMPAT_RANGES:
        if lo <= cp <= hi:
            return name
    return None


def scan_compat(text: str) -> dict[str, int]:
    """Count suspicious code points by 'U+XXXX' (empty dict = clean)."""
    counts: dict[str, int] = {}
    for ch in text:
        if compat_block(ch) is not None:
            key = f"U+{ord(ch):04X}"
            counts[key] = counts.get(key, 0) + 1
    return counts


def map_compat_to_unified(text: str) -> tuple[str, list[dict[str, object]]]:
    """Replace ONLY flagged code points by their NFKC image when that image is one CJK Unified Ideograph.

    Returns (new_text, changes). Raises ExtractionError if a flagged code point has no such image.
    Offsets are unchanged because every replacement is one code point for one code point.
    """
    out: list[str] = []
    changes: list[dict[str, object]] = []
    for i, ch in enumerate(text):
        block = compat_block(ch)
        if block is None:
            out.append(ch)
            continue
        image = unicodedata.normalize("NFKC", ch)
        if len(image) != 1 or not ("一" <= image <= "鿿" or "㐀" <= image <= "䶿"):
            raise ExtractionError(f"U+{ord(ch):04X} ({block}) at {i} has no single unified ideograph image")
        out.append(image)
        changes.append({"offset": i, "from": f"U+{ord(ch):04X}", "to": f"U+{ord(image):04X}", "block": block})
    return "".join(out), changes
