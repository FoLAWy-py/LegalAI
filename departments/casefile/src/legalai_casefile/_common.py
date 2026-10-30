"""Shared extraction result, character checks and language heuristic."""

import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass

from legalai_casefile.errors import EmptyDocumentError, PartialExtractionError, UnsupportedContentError

PAGE_TERMINATOR = "\f"
"""Ends every PDF page in the stored text, so each page owns at least one character."""

_ALLOWED_CONTROLS = frozenset("\t\n\r\f")


@dataclass(frozen=True)
class Extraction:
    """Exact text extracted from one file, with page boundaries (code-point offsets)."""

    text: str
    page_starts: tuple[int, ...]
    media_type: str
    extractor: str
    warnings: tuple[str, ...] = ()


def check_characters(text: str, *, page: int | None = None) -> None:
    """Refuse text carrying signs of lossy extraction or font-dependent meaning.

    - U+FFFD: a decoder or extractor already replaced something it could not read.
    - Control characters other than tab, LF, CR, FF: raw glyph ids leaking through (no Unicode map).
    - Lone surrogates: broken UTF-16 in a mapping table.
    - Private-use code points: meaning depends on a specific (symbol) font.
    """
    pages = (page,) if page is not None else ()
    bad_replacement = bad_control = bad_surrogate = bad_private = 0
    for ch in text:
        cp = ord(ch)
        if cp == 0xFFFD:
            bad_replacement += 1
        elif (cp < 0x20 or 0x7F <= cp < 0xA0) and ch not in _ALLOWED_CONTROLS:
            bad_control += 1
        elif 0xD800 <= cp <= 0xDFFF:
            bad_surrogate += 1
        elif unicodedata.category(ch) == "Co":
            bad_private += 1
    if bad_replacement or bad_control or bad_surrogate:
        raise PartialExtractionError(
            f"{bad_replacement} replacement, {bad_control} control and {bad_surrogate} surrogate "
            "character(s) indicate text that could not be decoded or mapped to Unicode",
            pages=pages,
        )
    if bad_private:
        raise UnsupportedContentError(
            f"{bad_private} private-use character(s); their meaning depends on a symbol font",
            pages=pages,
        )


def single_page(text: str, media_type: str, extractor: str, warnings: Sequence[str] = ()) -> Extraction:
    """Validate a non-paginated text and wrap it as a one-page extraction."""
    if not text.strip():
        raise EmptyDocumentError("no text")
    check_characters(text)
    return Extraction(text, (0,), media_type, extractor, tuple(warnings))


def _is_han(cp: int) -> bool:
    return (
        0x3400 <= cp <= 0x4DBF or 0x4E00 <= cp <= 0x9FFF or 0xF900 <= cp <= 0xFAFF or 0x20000 <= cp <= 0x323AF
    )


def detect_language(text: str) -> str:
    """Heuristic BCP 47 tag: `zh`, `en`, `mul` (substantially mixed) or `und`.

    Scores Han characters against ASCII letters / 4 (roughly one Han character per English word).
    Share of Han >= 0.8 -> `zh`; <= 0.2 -> `en`; otherwise `mul`. Callers who know better pass the
    language explicitly; v1 jurisdictions are CN and US, so Latin script is assumed to be English.
    """
    han = latin = 0
    for ch in text:
        cp = ord(ch)
        if _is_han(cp):
            han += 1
        elif ch.isascii() and ch.isalpha():
            latin += 1
    zh, en = float(han), latin / 4
    if zh + en == 0:
        return "und"
    share = zh / (zh + en)
    if share >= 0.8:
        return "zh"
    if share <= 0.2:
        return "en"
    return "mul"
