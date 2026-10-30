"""Derive structural units (pinpoints) from stored text. Units only point into the text; they never alter it.

Profiles:
- `cn-law`: 编 / 分编 / 章 / 节 headings and 条 articles; 款 (paragraphs) and 项 (items) inside articles.
- `cn-amendment`: amendment acts and decisions numbered 一、二、… (and any 第X条 articles they contain).
- `none`: no structure (whole document is one unit).
A new jurisdiction adds a profile here; the contracts do not change (REQ-PMO-0002 §2.5).
"""

import re
from dataclasses import asdict, dataclass

_NUM = "零〇一二三四五六七八九十百千"
_HEADINGS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("part", re.compile(rf"^第[{_NUM}]+编(?=\s|$)")),
    ("subpart", re.compile(rf"^第[{_NUM}]+分编(?=\s|$)")),
    ("chapter", re.compile(rf"^第[{_NUM}]+章(?=\s|$)")),
    ("section", re.compile(rf"^第[{_NUM}]+节(?=\s|$)")),
)
_ARTICLE = re.compile(rf"^第[{_NUM}]+条(?:之[{_NUM}]+)?(?=\s|$)")
_ITEM = re.compile(rf"^[\uff08(][{_NUM}]+[\uff09)]")  # full-width or ASCII parentheses
_AMENDMENT_ITEM = re.compile(rf"^[{_NUM}]+、")
PROFILES = ("cn-law", "cn-amendment", "none")


class StructureError(Exception):
    """The text does not parse cleanly under its profile (e.g. duplicate article numbers)."""


@dataclass(frozen=True)
class Unit:
    """A structural unit: [start, end) character offsets into the stored text."""

    kind: str
    label: str
    pinpoint: str
    start: int
    end: int

    def to_json(self) -> dict[str, object]:
        return asdict(self)


def _lines(text: str) -> list[tuple[int, int, str]]:
    out, pos = [], 0
    for line in text.split("\n"):
        out.append((pos, pos + len(line), line))
        pos += len(line) + 1
    return out


def derive_units(text: str, profile: str) -> list[Unit]:
    """Return units in document order. Raises StructureError on ambiguity (fail closed)."""
    if profile not in PROFILES:
        raise StructureError(f"unknown structure profile {profile!r}")
    if profile == "none":
        return [Unit("document", "", "", 0, len(text))]
    lines = _lines(text)
    units: list[Unit] = []
    # 1. top-level units (headings, articles, amendment items) with provisional ends
    tops: list[tuple[str, str, int, int]] = []  # kind, label, line index, start
    for i, (start, _end, line) in enumerate(lines):
        found = _top_level(line, profile)
        if found is not None:
            tops.append((found[0], found[1], i, start))
    seen: set[tuple[str, str]] = set()
    for n, (kind, label, line_idx, start) in enumerate(tops):
        if kind in ("article", "amendment_item"):
            if (kind, label) in seen:
                raise StructureError(f"duplicate {kind} {label}")
            seen.add((kind, label))
        if kind in ("article", "amendment_item"):
            nxt = tops[n + 1][2] if n + 1 < len(tops) else len(lines)
            end_line = nxt - 1
        else:
            # a heading spans until the next heading of the same or higher level
            rank = [k for k, _ in _HEADINGS].index(kind)
            end_line = len(lines) - 1
            for kind2, _l2, idx2, _s2 in tops[n + 1 :]:
                if kind2 in [k for k, _ in _HEADINGS[: rank + 1]]:
                    end_line = idx2 - 1
                    break
        end = lines[end_line][1]
        pin = label if kind != "amendment_item" else f"{label}、"
        units.append(Unit(kind, label, pin, start, end))
        if kind == "article":
            units.extend(_paragraphs(lines, line_idx, end_line, label))
    return units


def _top_level(line: str, profile: str) -> tuple[str, str] | None:
    for kind, pattern in _HEADINGS:
        m = pattern.match(line)
        if m:
            return kind, m.group(0)
    m = _ARTICLE.match(line)
    if m:
        return "article", m.group(0)
    if profile == "cn-amendment":
        m = _AMENDMENT_ITEM.match(line)
        if m:
            return "amendment_item", m.group(0)[:-1]
    return None


def _paragraphs(lines: list[tuple[int, int, str]], first: int, last: int, article: str) -> list[Unit]:
    """款 = each line of the article that is not an item; 项 = lines that start with a parenthesised
    Chinese numeral (full-width or ASCII parentheses), attached to the current 款."""
    out: list[Unit] = []
    kuan = 0
    kuan_start = kuan_end = 0
    pending: Unit | None = None
    for idx in range(first, last + 1):
        start, end, line = lines[idx]
        item = _ITEM.match(line)
        if item and kuan > 0:
            label = item.group(0)
            out.append(Unit("item", label, f"{article}第{_cn(kuan)}款{label}", start, end))
            kuan_end = end
            continue
        if pending is not None:
            out.append(Unit("paragraph", pending.label, pending.pinpoint, kuan_start, kuan_end))
        kuan += 1
        kuan_start, kuan_end = start, end
        pending = Unit("paragraph", f"第{_cn(kuan)}款", f"{article}第{_cn(kuan)}款", start, end)
    if pending is not None:
        out.append(Unit("paragraph", pending.label, pending.pinpoint, kuan_start, kuan_end))
    return out


def _cn(n: int) -> str:
    """Chinese numeral for 1..99 (paragraph counters only; never used to rewrite source text)."""
    digits = "零一二三四五六七八九"
    if n < 10:
        return digits[n]
    tens, ones = divmod(n, 10)
    return ("" if tens == 1 else digits[tens]) + "十" + ("" if ones == 0 else digits[ones])
