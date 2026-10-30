"""Split document text into retrievable units aligned with legal structure.

Law: one unit per article / rule / section (第X条, Article N, Rule N, Section N, § N). An article
longer than `max_chars` is split into its paragraphs (款), pinpointed as 第X条第N款 or "Article N, para. N".
Chapter-level headings (编/章/节, Part/Chapter/Title) are not spans; they become indexing context.
Text without recognisable structure falls back to line-based units ("para. N").

Case files: line-based units (short lines merged), never crossing a page boundary, "p. N".

Every unit's offsets index the original text exactly and exclude surrounding whitespace.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from itertools import pairwise

from legalai_retrieval.text import int_to_cn

CHUNKER_VERSION = "1"


# Full-width / ideographic characters are built with chr() so the source stays unambiguous.
_IDEO_SPACE = chr(0x3000)
_IDEO_ZERO = chr(0x3007)
_FW_DIGITS = f"{chr(0xFF10)}-{chr(0xFF19)}"
_FW_LPAREN, _FW_RPAREN = chr(0xFF08), chr(0xFF09)
_FW_STOPS = chr(0xFF01) + chr(0xFF1F) + chr(0xFF1B)  # full-width ! ? ;
_CLOSERS = chr(0x201D) + chr(0x2019) + "\"')" + _FW_RPAREN  # closing quotes and brackets

_CN_NUM = f"零{_IDEO_ZERO}一二两三四五六七八九十百千万0-9{_FW_DIGITS}"
_CN_ARTICLE = re.compile(
    rf"^[ \t{_IDEO_SPACE}]*(第[{_CN_NUM}]+条(?:之[{_CN_NUM}]+)?)(?=[\s{_IDEO_SPACE}【({_FW_LPAREN}]|$)"
)
_CN_HEADING = re.compile(rf"^[ \t{_IDEO_SPACE}]*第[{_CN_NUM}]+(编|分编|章|节)(?=[\s{_IDEO_SPACE}]|$)")
_EN_ARTICLE = re.compile(
    r"^[ \t]*((?:Article|ARTICLE|Art\.|Section|SECTION|Sec\.|Rule|RULE)[ \t]+\d+[A-Za-z0-9\-]*"
    r"|§+[ \t]*\d+[A-Za-z0-9\-]*)(?=[\s.:]|$)"
)
_EN_HEADING = re.compile(
    r"^[ \t]*(PART|Part|TITLE|Title|CHAPTER|Chapter|SUBCHAPTER|Subchapter|DIVISION|Division)"
    r"[ \t]+[IVXLC\d]+\b"
)
_HEADING_LEVEL = {
    "编": 0,
    "分编": 1,
    "章": 2,
    "节": 3,
    "part": 0,
    "title": 0,
    "chapter": 2,
    "subchapter": 3,
    "division": 3,
}
_SENTENCE_END = re.compile(rf"[。{_FW_STOPS}.!?;][{re.escape(_CLOSERS)}]*\s*")
MIN_UNIT_CHARS = 40


@dataclass(frozen=True)
class TextUnit:
    """A retrievable span of the original text plus non-span context used only for indexing."""

    start: int
    end: int
    pinpoint: str
    context: str


def _trim(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def _lines(text: str, start: int, end: int) -> list[tuple[int, int]]:
    """Non-blank lines in [start, end), trimmed, as absolute offsets."""
    out: list[tuple[int, int]] = []
    pos = start
    while pos < end:
        nl = text.find("\n", pos, end)
        line_end = end if nl == -1 else nl
        s, e = _trim(text, pos, line_end)
        if s < e:
            out.append((s, e))
        pos = line_end + 1
    return out


def _sentences(text: str, start: int, end: int) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    pos = start
    for m in _SENTENCE_END.finditer(text, start, end):
        s, e = _trim(text, pos, m.end())
        if s < e:
            out.append((s, e))
        pos = m.end()
    s, e = _trim(text, pos, end)
    if s < e:
        out.append((s, e))
    return out


def _bounded(text: str, start: int, end: int, max_chars: int) -> list[tuple[int, int]]:
    """Split [start, end) into pieces of at most max_chars: lines, then sentences, then hard cuts.

    Adjacent pieces are packed back together while they fit, so pieces are as large as allowed.
    """
    if end - start <= max_chars:
        return [(start, end)]
    pieces: list[tuple[int, int]] = []
    for ls, le in _lines(text, start, end):
        if le - ls <= max_chars:
            pieces.append((ls, le))
            continue
        for ss, se in _sentences(text, ls, le):
            if se - ss <= max_chars:
                pieces.append((ss, se))
            else:
                pieces.extend(_trim(text, i, min(i + max_chars, se)) for i in range(ss, se, max_chars))
    packed: list[tuple[int, int]] = []
    for s, e in pieces:
        if s >= e:
            continue
        if packed and e - packed[-1][0] <= max_chars:
            packed[-1] = (packed[-1][0], e)
        else:
            packed.append((s, e))
    return packed


def _paragraph_pinpoint(label: str, n: int) -> str:
    if label.startswith("第"):
        return f"{label}第{int_to_cn(n)}款"
    return f"{label}, para. {n}"


@dataclass
class _Open:
    label: str
    context: str
    start: int
    end: int


def chunk_law(text: str, max_chars: int) -> list[TextUnit]:
    """Units aligned with articles/rules/sections; see module docstring."""
    if max_chars < 50:
        raise ValueError("max_chars must be at least 50")
    units: list[TextUnit] = []
    path: list[tuple[int, str]] = []
    current: _Open | None = None
    preamble: list[tuple[int, int]] = []
    found_article = False

    def close() -> None:
        nonlocal current
        if current is None:
            return
        s, e = _trim(text, current.start, current.end)
        paragraphs = _lines(text, s, e)
        if e - s <= max_chars or len(paragraphs) <= 1:
            for ps, pe in _bounded(text, s, e, max_chars):
                units.append(TextUnit(ps, pe, current.label, current.context))
        else:
            for n, (ps, pe) in enumerate(paragraphs, 1):
                pin = _paragraph_pinpoint(current.label, n)
                for bs, be in _bounded(text, ps, pe, max_chars):
                    units.append(TextUnit(bs, be, pin, current.context))
        current = None

    for ls, le in _lines(text, 0, len(text)):
        line = text[ls:le]
        heading = _CN_HEADING.match(line) or _EN_HEADING.match(line)
        if heading:
            close()
            level = _HEADING_LEVEL[heading.group(1).lower()]
            path = [(lvl, h) for lvl, h in path if lvl < level] + [(level, line)]
            continue
        article = _CN_ARTICLE.match(line) or _EN_ARTICLE.match(line)
        if article:
            close()
            found_article = True
            label = re.sub(r"\s+", " ", article.group(1)).rstrip(".")
            current = _Open(label, " / ".join(h for _, h in path), ls, le)
        elif current is not None:
            current.end = le
        else:
            preamble.append((ls, le))
    close()

    if not found_article:
        return chunk_lines(text, 0, len(text), max_chars, lambda n: f"para. {n}", context="")
    if preamble:
        s, e = preamble[0][0], preamble[-1][1]
        head = [TextUnit(bs, be, "preamble", "") for bs, be in _bounded(text, s, e, max_chars)]
        units = head + units
    return units


def chunk_lines(
    text: str,
    start: int,
    end: int,
    max_chars: int,
    pinpoint: Callable[[int], str],
    context: str,
) -> list[TextUnit]:
    """Line-based units of [start, end): each line is a unit, bounded by max_chars; a line shorter
    than MIN_UNIT_CHARS (a header, a salutation) is merged with the following lines until it is not."""
    packed: list[tuple[int, int]] = []
    for ls, le in _lines(text, start, end):
        for s, e in _bounded(text, ls, le, max_chars):
            if packed and packed[-1][1] - packed[-1][0] < MIN_UNIT_CHARS and e - packed[-1][0] <= max_chars:
                packed[-1] = (packed[-1][0], e)
            else:
                packed.append((s, e))
    return [TextUnit(s, e, pinpoint(n), context) for n, (s, e) in enumerate(packed, 1)]


def _page_label(page: int) -> Callable[[int], str]:
    return lambda _n: f"p. {page}"


def chunk_case(text: str, page_starts: tuple[int, ...], max_chars: int, context: str) -> list[TextUnit]:
    """Line-based units within each page (never crossing a page boundary); pinpoint "p. N"."""
    if max_chars < 50:
        raise ValueError("max_chars must be at least 50")
    bounds = [*page_starts, len(text)]
    units: list[TextUnit] = []
    for page, (ps, pe) in enumerate(pairwise(bounds), 1):
        units.extend(chunk_lines(text, ps, pe, max_chars, _page_label(page), context))
    return units
