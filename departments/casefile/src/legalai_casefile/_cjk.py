"""CJK look-alike code points in PDF output (REQ-PMO-0009).

Some PDF generators share one glyph between an ideograph and its look-alike radical, and their ToUnicode map
then names the radical (e.g. 人 U+4EBA is written as KANGXI RADICAL MAN U+2F08). The text looks right but
differs by code point. For PDF output only:

- Every code point in CJK Radicals Supplement (U+2E80-U+2EFF) or Kangxi Radicals (U+2F00-U+2FDF) is
  replaced 1:1 by its Unicode `Equivalent_Unified_Ideograph` (UCD file committed in `ucd/`, hash-checked).
  The replacement is always a single code point, so text length and every offset are unchanged. Each
  replaced position is recorded as a `CodePointSubstitution`, so the extractor's output is reproducible.
- A radical with no equivalent ideograph (U+2E80 and unassigned code points) cannot be mapped; the caller
  refuses the document.
- CJK Compatibility Ideographs are never mapped (they are deliberately distinct forms); they are only
  counted so the caller can warn.
"""

import hashlib
import re
import unicodedata
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from functools import cache
from importlib.resources import files

from legalai_casefile.errors import CasefileError

TABLE_FILE = "EquivalentUnifiedIdeograph-15.1.0.txt"
TABLE_SHA256 = "460a08f497d0f3e45aae734708848fadf1ced44b752971bac37c23da55b33aa9"
TABLE_URL = "https://www.unicode.org/Public/15.1.0/ucd/EquivalentUnifiedIdeograph.txt"
CJK_MAPPING_VERSION = "casefile-cjk-radicals/1 (UCD 15.1.0 Equivalent_Unified_Ideograph)"
RADICAL_BLOCKS = ((0x2E80, 0x2EFF), (0x2F00, 0x2FDF))
COMPAT_BLOCKS = ((0xF900, 0xFAFF), (0x2F800, 0x2FA1F))

_LINE = re.compile(r"^([0-9A-F]{4,6})(?:\.\.([0-9A-F]{4,6}))?\s*;\s*([0-9A-F]{4,6})\b")


@dataclass(frozen=True)
class CodePointSubstitution:
    """One replaced code point.

    At `offset` the extractor produced `original`; the stored text holds `replacement` there.
    """

    offset: int
    original: str
    replacement: str


def _in(blocks: Sequence[tuple[int, int]], cp: int) -> bool:
    return any(lo <= cp <= hi for lo, hi in blocks)


def is_radical(ch: str) -> bool:
    return _in(RADICAL_BLOCKS, ord(ch))


def is_compat_ideograph(ch: str) -> bool:
    """A CJK compatibility ideograph proper (excludes the twelve unified ideographs in that block)."""
    return _in(COMPAT_BLOCKS, ord(ch)) and unicodedata.decomposition(ch) != ""


@cache
def radical_table() -> dict[str, str]:
    """Radical -> equivalent unified ideograph, from the committed UCD file (hash-verified)."""
    raw = files("legalai_casefile").joinpath("ucd", TABLE_FILE).read_bytes()
    if hashlib.sha256(raw).hexdigest() != TABLE_SHA256:
        raise CasefileError(f"{TABLE_FILE} does not match its recorded SHA-256")
    table: dict[str, str] = {}
    for line in raw.decode("utf-8").splitlines():
        m = _LINE.match(line)
        if not m:
            continue
        lo = int(m.group(1), 16)
        hi = int(m.group(2), 16) if m.group(2) else lo
        target = chr(int(m.group(3), 16))
        for cp in range(lo, hi + 1):
            if _in(RADICAL_BLOCKS, cp):
                table[chr(cp)] = target
    return table


def map_radicals(text: str) -> tuple[str, tuple[CodePointSubstitution, ...], tuple[int, ...]]:
    """Return (mapped text, substitutions, offsets of radicals that have no equivalent)."""
    table = radical_table()
    out = list(text)
    subs: list[CodePointSubstitution] = []
    unmappable: list[int] = []
    for offset, ch in enumerate(text):
        if not is_radical(ch):
            continue
        target = table.get(ch)
        if target is None:
            unmappable.append(offset)
        else:
            out[offset] = target
            subs.append(CodePointSubstitution(offset, ch, target))
    return "".join(out), tuple(subs), tuple(unmappable)


def restore_extracted_text(text: str, substitutions: Iterable[CodePointSubstitution]) -> str:
    """Rebuild the extractor's output from stored text and its substitution record.

    Raises `ValueError` if a recorded position does not hold the recorded replacement.
    """
    chars = list(text)
    for sub in substitutions:
        if not 0 <= sub.offset < len(chars) or chars[sub.offset] != sub.replacement:
            raise ValueError(f"substitution record does not match the text at offset {sub.offset}")
        chars[sub.offset] = sub.original
    return "".join(chars)


def describe(pairs: Counter[tuple[str, str]]) -> str:
    """`U+2F08->U+4EBA x119, ...` (code points only, most frequent first)."""
    return ", ".join(
        f"U+{ord(a):04X}->U+{ord(b):04X} x{n}" if b else f"U+{ord(a):04X} x{n}"
        for (a, b), n in pairs.most_common()
    )
