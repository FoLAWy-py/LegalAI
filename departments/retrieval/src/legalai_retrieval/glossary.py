"""Bilingual (zh <-> en) legal-term glossary used only to expand search queries.

A glossary hit never asserts that two legal concepts are equivalent (ADR-0004 §6). It only lets a
query in one language reach candidate spans written in the other. Ranking, thresholds, filtering
and span fidelity are unaffected by it.
"""

from dataclasses import dataclass
from importlib import resources

from legalai_retrieval.text import (
    Expansion,
    QueryAnalysis,
    iter_words,
    normalize,
    query_units,
    term_tokens,
)

GLOSSARY_VERSION = "zh-en-1"


@dataclass(frozen=True)
class Concept:
    zh: tuple[str, ...]
    en: tuple[str, ...]


def _parse(text: str) -> tuple[Concept, ...]:
    concepts: list[Concept] = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) != 2:
            raise ValueError(f"glossary line {lineno}: expected 'zh<TAB>en', got {raw!r}")
        zh = tuple(normalize(t.strip()) for t in parts[0].split("|") if t.strip())
        en = tuple(normalize(t.strip()) for t in parts[1].split("|") if t.strip())
        if not zh or not en:
            raise ValueError(f"glossary line {lineno}: empty side")
        concepts.append(Concept(zh, en))
    return tuple(concepts)


class Glossary:
    """Concept groups of Chinese and English terms. Matching any member expands to all members."""

    def __init__(self, concepts: tuple[Concept, ...], version: str) -> None:
        self.version = version
        self._concepts = concepts
        self._alternatives: list[tuple[frozenset[str], ...]] = []
        self._en_patterns: list[list[tuple[str, ...]]] = []
        for c in concepts:
            alts = {term_tokens(t) for t in (*c.zh, *c.en)}
            self._alternatives.append(tuple(sorted((a for a in alts if a), key=sorted)))
            self._en_patterns.append([tuple(w.stem for w in iter_words(t)) for t in c.en])

    @classmethod
    def default(cls) -> "Glossary":
        text = (
            resources.files("legalai_retrieval").joinpath("resources/glossary_zh_en.tsv").read_text("utf-8")
        )
        return cls(_parse(text), GLOSSARY_VERSION)

    @classmethod
    def empty(cls) -> "Glossary":
        return cls((), "none")

    def analyze(self, query: str) -> QueryAnalysis:
        """Split `query` into content units and attach the glossary expansions that cover them."""
        norm = normalize(query)
        units = query_units(norm)
        words = list(iter_words(norm))
        expansions: list[Expansion] = []
        for idx, concept in enumerate(self._concepts):
            spans: list[tuple[int, int]] = []
            for term in concept.zh:
                start = norm.find(term)
                while start != -1:
                    spans.append((start, start + len(term)))
                    start = norm.find(term, start + 1)
            for pattern in self._en_patterns[idx]:
                n = len(pattern)
                for i in range(len(words) - n + 1):
                    if tuple(w.stem for w in words[i : i + n]) == pattern:
                        spans.append((words[i].start, words[i + n - 1].end))
            for s, e in spans:
                covered = frozenset(j for j, u in enumerate(units) if s <= u.start and u.end <= e)
                if covered:
                    expansions.append(Expansion(covered, self._alternatives[idx]))
        return QueryAnalysis(tuple(units), tuple(expansions))
