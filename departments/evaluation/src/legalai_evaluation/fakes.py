"""In-memory implementations of the store and retrieval ports, for synthetic `ZZ` data only.

They are deliberately simple and deterministic. They are fixtures for exercising builders,
verifiers and the eval runner, not reference implementations of corpus, casefile or retrieval.
"""

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from legalai_contracts import (
    CaseDocument,
    LegalQuery,
    SourceDocument,
    SourceKind,
    SourceSpan,
)

_LATIN_WORD = re.compile(r"[a-z0-9]+")
_CJK_RUN = re.compile(r"[㐀-䶿一-鿿]+")
_STOPWORDS = frozenset(
    {"the", "and", "for", "that", "with", "was", "has", "our", "its", "are", "this", "not", "from"}
)


def tokens(text: str) -> frozenset[str]:
    """Lower-cased Latin words (3+ chars, minus stopwords) and CJK character bigrams of `text`."""
    lowered = text.lower()
    found = {w for w in _LATIN_WORD.findall(lowered) if len(w) >= 3 and w not in _STOPWORDS}
    for run in _CJK_RUN.findall(text):
        if len(run) == 1:
            found.add(run)
        found.update(run[i : i + 2] for i in range(len(run) - 1))
    return frozenset(found)


def _check_range(char_count: int, start_char: int, end_char: int) -> None:
    if not 0 <= start_char < end_char <= char_count:
        raise ValueError(f"range [{start_char}, {end_char}) outside document of {char_count} chars")


class InMemorySourceStore:
    """`SourceStore` over a fixed set of law document versions held in memory.

    Guarantees: `get_text` returns exactly the stored characters; unknown documents raise `KeyError`;
    out-of-range offsets raise `ValueError`.
    """

    def __init__(self, documents: Iterable[tuple[SourceDocument, str]]) -> None:
        self._docs: dict[tuple[str, str], tuple[SourceDocument, str]] = {}
        for doc, text in documents:
            key = (doc.doc_id, doc.version_id)
            if key in self._docs:
                raise ValueError(f"duplicate law document {key}")
            if len(text) != doc.char_count:
                raise ValueError(f"char_count mismatch for {key}")
            self._docs[key] = (doc, text)

    def list_documents(self, jurisdiction: str) -> list[SourceDocument]:
        return [doc for doc, _ in self._docs.values() if doc.jurisdiction == jurisdiction]

    def all_documents(self) -> list[SourceDocument]:
        """Every document version in the store, in insertion order."""
        return [doc for doc, _ in self._docs.values()]

    def get_document(self, doc_id: str, version_id: str) -> SourceDocument:
        return self._docs[(doc_id, version_id)][0]

    def get_text(self, doc_id: str, version_id: str, start_char: int, end_char: int) -> str:
        doc, text = self._docs[(doc_id, version_id)]
        _check_range(doc.char_count, start_char, end_char)
        return text[start_char:end_char]


class InMemoryCaseFileStore:
    """`CaseFileStore` over fixed synthetic case files held in memory. Same guarantees as the source store."""

    def __init__(self, documents: Iterable[tuple[CaseDocument, str]]) -> None:
        self._docs: dict[tuple[str, str], tuple[CaseDocument, str]] = {}
        for doc, text in documents:
            key = (doc.doc_id, doc.version_id)
            if key in self._docs:
                raise ValueError(f"duplicate case document {key}")
            if len(text) != doc.char_count:
                raise ValueError(f"char_count mismatch for {key}")
            self._docs[key] = (doc, text)

    def list_documents(self, case_id: str) -> list[CaseDocument]:
        return [doc for doc, _ in self._docs.values() if doc.case_id == case_id]

    def all_documents(self) -> list[CaseDocument]:
        """Every case document version in the store, in insertion order."""
        return [doc for doc, _ in self._docs.values()]

    def get_document(self, doc_id: str, version_id: str) -> CaseDocument:
        return self._docs[(doc_id, version_id)][0]

    def get_text(self, doc_id: str, version_id: str, start_char: int, end_char: int) -> str:
        doc, text = self._docs[(doc_id, version_id)]
        _check_range(doc.char_count, start_char, end_char)
        return text[start_char:end_char]


@dataclass(frozen=True)
class IndexedSpan:
    """A retrievable span plus extra search terms (e.g. bilingual keywords for cross-lingual search)."""

    span: SourceSpan
    keywords: tuple[str, ...] = ()


def _rank(query_text: str, candidates: Sequence[IndexedSpan], limit: int) -> list[SourceSpan]:
    if limit <= 0:
        return []
    wanted = tokens(query_text)
    scored = []
    for position, item in enumerate(candidates):
        terms = tokens(item.span.text) | tokens(" ".join(item.keywords))
        scored.append((-len(wanted & terms), position, item.span))
    scored.sort(key=lambda entry: (entry[0], entry[1]))
    return [span for _, _, span in scored[:limit]]


class InMemoryRetriever:
    """`Retriever` over article-level law spans: lexical overlap ranking, filtered to the query's
    jurisdiction (exact code) and to versions in force on `as_of`.

    Returns up to `limit` spans, best first; ties keep index order. Returns nothing when no law in the
    jurisdiction is in force on `as_of`.
    """

    def __init__(self, store: InMemorySourceStore, spans: Sequence[IndexedSpan]) -> None:
        for item in spans:
            if item.span.source is not SourceKind.LAW:
                raise ValueError("InMemoryRetriever indexes law spans only")
            store.get_document(item.span.doc_id, item.span.version_id)
        self._store = store
        self._spans = tuple(spans)

    def retrieve(self, query: LegalQuery, limit: int) -> list[SourceSpan]:
        eligible = []
        for item in self._spans:
            doc = self._store.get_document(item.span.doc_id, item.span.version_id)
            if doc.jurisdiction == query.jurisdiction and doc.in_force_on(query.as_of):
                eligible.append(item)
        return _rank(query.text, eligible, limit)


class InMemoryEvidenceRetriever:
    """`EvidenceRetriever` over line-level case-file passages of one case at a time.

    Returns up to `limit` passages of `case_id` only, ranked by lexical overlap with `text`;
    ties keep document order. Unknown case ids return an empty list.
    """

    def __init__(self, store: InMemoryCaseFileStore, spans: Sequence[IndexedSpan]) -> None:
        by_case: dict[str, list[IndexedSpan]] = {}
        for item in spans:
            if item.span.source is not SourceKind.CASE_FILE:
                raise ValueError("InMemoryEvidenceRetriever indexes case-file spans only")
            doc = store.get_document(item.span.doc_id, item.span.version_id)
            by_case.setdefault(doc.case_id, []).append(item)
        self._by_case: Mapping[str, tuple[IndexedSpan, ...]] = {k: tuple(v) for k, v in by_case.items()}

    def search_case(self, case_id: str, text: str, limit: int) -> list[SourceSpan]:
        return _rank(text, self._by_case.get(case_id, ()), limit)
