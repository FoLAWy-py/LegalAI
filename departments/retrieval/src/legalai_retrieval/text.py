"""Text analysis for lexical search.

Chinese has no whitespace, so CJK runs are indexed as overlapping character bigrams (no dictionary,
so no segmentation errors on unseen legal terms), plus unigrams so that single-character glossary
terms can match. Latin-script words are lower-cased and lightly stemmed. Article references
(第五百七十七条, 第577条, Article 577, Rule 401, § 2-201) become a shared token so a numeric
reference matches across scripts.

Normalised text is used only to derive tokens. Span offsets always refer to the original text.
"""

import re
import unicodedata
from collections.abc import Iterator
from dataclasses import dataclass

# CJK Unified Ideographs Extension A, the basic block, and Compatibility Ideographs.
_CJK = "".join(f"{chr(a)}-{chr(b)}" for a, b in ((0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xF900, 0xFAFF)))
_SCAN_RE = re.compile(rf"(?P<cjk>[{_CJK}]+)|(?P<word>[a-z0-9]+)")

_ZERO = chr(0x3007)  # IDEOGRAPHIC NUMBER ZERO
_CN_NUMERALS = f"零{_ZERO}一二两三四五六七八九十百千万"
_CN_DIGIT = {"零": 0, _ZERO: 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5}
_CN_DIGIT.update({"六": 6, "七": 7, "八": 8, "九": 9})
_CN_UNIT = {"十": 10, "百": 100, "千": 1000}

# Applied to NFKC + casefolded text, so full-width digits are already ASCII.
_REF_RE = re.compile(
    rf"第(?P<cn>[{_CN_NUMERALS}0-9]+)条(?:之(?P<cnsub>[{_CN_NUMERALS}0-9]+))?"
    r"|(?:(?<![a-z])(?:article|art\.|section|sec\.|rule)\s+|§+\s*)(?P<en>\d+(?:-\d+)?)"
)

_STOPWORD_TEXT = (
    "a an the of to in on for by with and or is are be been being was were it its that this these those "
    "as at from if can could may might will would shall should what which who whom whose when where why how "
    "does do did has have had i we you he she they me us him her them my our your their there here than then "
    "so such any some into onto upon about under over"
)
ENGLISH_STOPWORDS = frozenset(_STOPWORD_TEXT.split())
"""Removed from both documents and queries. Negations (not, no) are kept on purpose."""

CJK_STOP_CHARS = frozenset(
    "的了吗呢吧啊么是否能可以请问我你他她它们这那"  # function words, pronouns
    "什怎如何哪些有在和与或及就都也还要会对把被让给"  # question words, particles, prepositions
)
"""Function characters. They still form bigrams but never count toward query coverage."""

CJK_QUERY_FILLERS = (
    "什么时候",
    "多长时间",
    "能不能",
    "可不可以",
    "是不是",
    "有没有",
    "怎么办",
    "为什么",
    "什么",
    "时候",
    "开始",
    "多长",
    "多久",
    "多少",
    "怎样",
    "哪里",
    "一般",
    "还能",
)
"""Question filler words. Like stop characters, they never count toward query coverage."""


def normalize(text: str) -> str:
    """NFKC + casefold. Only for deriving tokens; never used to compute span offsets."""
    return unicodedata.normalize("NFKC", text).casefold()


def cn_to_int(numeral: str) -> int | None:
    """Parse a Chinese (or ASCII) integer numeral such as 五百七十七 or 577. None if unparseable."""
    if numeral.isdigit():
        return int(numeral)
    total = section = number = 0
    for ch in numeral:
        if ch in _CN_DIGIT:
            number = _CN_DIGIT[ch]
        elif ch in _CN_UNIT:
            section += (number or 1) * _CN_UNIT[ch]
            number = 0
        elif ch == "万":
            total += (section + number) * 10000
            section = number = 0
        else:
            return None
    return total + section + number


def int_to_cn(n: int) -> str:
    """Chinese numeral for 1..99 (used for paragraph pinpoints such as 第二款); digits otherwise."""
    digits = "零一二三四五六七八九"
    if 0 < n < 10:
        return digits[n]
    if 10 <= n < 100:
        tens, ones = divmod(n, 10)
        return ("" if tens == 1 else digits[tens]) + "十" + (digits[ones] if ones else "")
    return str(n)


def stem(word: str) -> str:
    """Light, deterministic English suffix stripping (deliver/delivers/delivered -> deliver)."""
    if len(word) <= 3 or not word.isalpha():
        return word
    w = word
    for suffix, replacement in (
        ("ations", "ate"),
        ("ation", "ate"),
        ("ments", ""),
        ("ment", ""),
        ("ings", ""),
        ("ing", ""),
        ("ies", "y"),
        ("ied", "y"),
        ("sses", "ss"),
        ("ed", ""),
        ("ery", "er"),
        ("s", ""),
    ):
        if w.endswith(suffix) and len(w) - len(suffix) >= 3:
            if suffix == "s" and w.endswith(("ss", "us", "is")):
                break
            w = w[: len(w) - len(suffix)] + replacement
            if suffix in ("ing", "ings", "ed") and len(w) > 3 and w[-1] == w[-2] and w[-1] not in "lsz":
                w = w[:-1]
            break
    if len(w) > 4 and w.endswith("e"):
        w = w[:-1]
    return w


def _ref_token(m: re.Match[str]) -> str | None:
    if m.group("en") is not None:
        return "§" + m.group("en")
    main = cn_to_int(m.group("cn"))
    if main is None:
        return None
    sub = m.group("cnsub")
    if sub is None:
        return f"§{main}"
    sub_n = cn_to_int(sub)
    return f"§{main}-{sub_n}" if sub_n is not None else f"§{main}"


def _cjk_tokens(run: str) -> list[str]:
    # Bigrams carry the lexical signal; unigrams exist so single-character glossary terms can match.
    return [run[i : i + 2] for i in range(len(run) - 1)] + list(run)


def tokenize(text: str) -> list[str]:
    """Document-side tokens (with repetition): article refs, CJK bigrams, stemmed non-stop words."""
    norm = normalize(text)
    tokens: list[str] = []
    for m in _REF_RE.finditer(norm):
        tok = _ref_token(m)
        if tok:
            tokens.append(tok)
    for m in _SCAN_RE.finditer(norm):
        if m.group("cjk"):
            tokens.extend(_cjk_tokens(m.group("cjk")))
        else:
            word = m.group("word")
            if word not in ENGLISH_STOPWORDS:
                tokens.append(stem(word))
    return tokens


def term_tokens(term: str) -> frozenset[str]:
    """Tokens that must all be present in a chunk for `term` to count as present."""
    return frozenset(tokenize(term))


@dataclass(frozen=True)
class QueryUnit:
    """One content position of the query: a CJK character, a word, or an article reference."""

    start: int
    end: int
    direct: frozenset[str]


@dataclass(frozen=True)
class Expansion:
    """A glossary hit: query units it covers, and token sets of which any one, if present, covers them."""

    units: frozenset[int]
    alternatives: tuple[frozenset[str], ...]


@dataclass(frozen=True)
class QueryAnalysis:
    units: tuple[QueryUnit, ...]
    expansions: tuple[Expansion, ...]

    @property
    def search_tokens(self) -> frozenset[str]:
        """Distinct tokens used for BM25: direct tokens plus every expansion alternative."""
        out: set[str] = set()
        for u in self.units:
            out |= u.direct
        for e in self.expansions:
            for alt in e.alternatives:
                out |= alt
        return frozenset(out)

    def coverage(self, present: frozenset[str] | set[str]) -> float:
        """Fraction of query content units matched literally or via a glossary expansion, in [0, 1]."""
        if not self.units:
            return 0.0
        covered = {i for i, u in enumerate(self.units) if u.direct & present}
        for e in self.expansions:
            if any(alt <= present for alt in e.alternatives):
                covered |= e.units
        return len(covered) / len(self.units)


@dataclass(frozen=True)
class WordPosition:
    start: int
    end: int
    stem: str
    stop: bool


def iter_words(norm: str) -> Iterator[WordPosition]:
    for m in _SCAN_RE.finditer(norm):
        if m.group("word"):
            word = m.group("word")
            yield WordPosition(m.start(), m.end(), stem(word), word in ENGLISH_STOPWORDS)


def query_units(norm: str) -> list[QueryUnit]:
    """Content units of a normalised query. Article references are masked and become one unit each."""
    units: list[QueryUnit] = []
    masked = list(norm)
    for m in _REF_RE.finditer(norm):
        tok = _ref_token(m)
        if tok:
            units.append(QueryUnit(m.start(), m.end(), frozenset({tok})))
            for i in range(m.start(), m.end()):
                masked[i] = " "
    masked_text = "".join(masked)
    filler: set[int] = set()
    for word in CJK_QUERY_FILLERS:
        pos = masked_text.find(word)
        while pos != -1:
            filler.update(range(pos, pos + len(word)))
            pos = masked_text.find(word, pos + 1)
    for m in _SCAN_RE.finditer(masked_text):
        if m.group("cjk"):
            run, base = m.group("cjk"), m.start()
            if len(run) == 1:
                if run not in CJK_STOP_CHARS and base not in filler:
                    units.append(QueryUnit(base, base + 1, frozenset({run})))
                continue
            for i, ch in enumerate(run):
                if ch in CJK_STOP_CHARS or base + i in filler:
                    continue
                adjacent = set()
                if i > 0:
                    adjacent.add(run[i - 1 : i + 1])
                if i < len(run) - 1:
                    adjacent.add(run[i : i + 2])
                units.append(QueryUnit(base + i, base + i + 1, frozenset(adjacent)))
        else:
            word = m.group("word")
            if word not in ENGLISH_STOPWORDS:
                units.append(QueryUnit(m.start(), m.end(), frozenset({stem(word)})))
    units.sort(key=lambda u: u.start)
    return units
