"""Case-file retrieval: the `EvidenceRetriever` port over an injected `CaseFileStore`.

Each case has its own index directory, named by the SHA-256 of the case id (no user text in
paths). A search loads only that directory, so spans from another case cannot be scored or
returned. Case indexes hold confidential derived data (P9) and are removed by `delete_case`.
"""

import hashlib
import shutil
from pathlib import Path

from legalai_contracts import CaseDocument, CaseFileStore, SourceKind, SourceSpan
from legalai_retrieval.chunking import chunk_case
from legalai_retrieval.config import RetrievalConfig, SearchMode
from legalai_retrieval.embedding import Embedder
from legalai_retrieval.errors import IndexBuildError, IndexNotFoundError, StaleIndexError
from legalai_retrieval.glossary import Glossary
from legalai_retrieval.index import Hit, IndexedText, SearchIndex, sha256_text
from legalai_retrieval.results import IndexStats, ScoredSpan, check_limit

_KIND = "case"


def _page_pinpoint(doc: CaseDocument, start: int, end: int) -> str:
    first, last = doc.page_of(start), doc.page_of(end - 1)
    return f"p. {first}" if first == last else f"pp. {first}-{last}"


class CaseEvidenceRetriever:
    """Hybrid case-file retriever implementing `legalai_contracts.EvidenceRetriever`.

    Guarantees for every span returned by `search_case(case_id, ...)`:
    - it comes from a document of `case_id` only (separate per-case index, re-checked against
      the store);
    - its text equals `CaseFileStore.get_text` for its offsets, re-read at query time
      (else `StaleIndexError`);
    - its pinpoint is the page ("p. N") computed from the store's page map;
    - it passed the documented eligibility threshold; `[]` if nothing did.

    Raises `IndexNotFoundError` if the case has not been indexed (or was deleted).
    """

    def __init__(self, store: CaseFileStore, embedder: Embedder, config: RetrievalConfig) -> None:
        self._store = store
        self._embedder = embedder
        self._config = config
        self._glossary = Glossary.default() if config.use_glossary else Glossary.empty()
        self._cache: dict[str, SearchIndex[CaseDocument]] = {}

    def _dir(self, case_id: str) -> Path:
        if not case_id:
            raise ValueError("case_id must be non-empty")
        return self._config.root / "cases" / hashlib.sha256(case_id.encode("utf-8")).hexdigest()

    def index_case(self, case_id: str) -> IndexStats:
        """(Re)build the index of every document the store lists for `case_id`."""
        directory = self._dir(case_id)
        docs = sorted(self._store.list_documents(case_id), key=lambda d: (d.doc_id, d.version_id))
        if not docs:
            raise IndexBuildError("store lists no documents for this case")
        seen: set[tuple[str, str]] = set()
        items: list[IndexedText[CaseDocument]] = []
        for doc in docs:
            key = (doc.doc_id, doc.version_id)
            if doc.case_id != case_id:
                raise IndexBuildError(f"{key} belongs to another case")
            if key in seen:
                raise IndexBuildError(f"duplicate document version {key}")
            seen.add(key)
            text = self._store.get_text(doc.doc_id, doc.version_id, 0, doc.char_count)
            if len(text) != doc.char_count:
                raise IndexBuildError(f"{key}: store text length {len(text)} != char_count {doc.char_count}")
            units = chunk_case(text, doc.page_starts, self._config.max_chunk_chars, context=doc.title)
            items.append(IndexedText(doc, text, units))
        index = SearchIndex.build(_KIND, case_id, items, self._embedder)
        index.save(directory)
        self._cache[case_id] = index
        return IndexStats(case_id, len(index.documents), len(index.chunks))

    def delete_case(self, case_id: str) -> bool:
        """Delete the case's index (and any interrupted build). Returns whether anything existed."""
        directory = self._dir(case_id)
        self._cache.pop(case_id, None)
        existed = directory.exists()
        if existed:
            shutil.rmtree(directory)
        if directory.parent.is_dir():
            for leftover in directory.parent.glob(f".{directory.name}.*"):
                shutil.rmtree(leftover)
                existed = True
        return existed

    def _index(self, case_id: str) -> SearchIndex[CaseDocument]:
        if case_id not in self._cache:
            try:
                self._cache[case_id] = SearchIndex.load(
                    self._dir(case_id), _KIND, case_id, CaseDocument, self._embedder
                )
            except IndexNotFoundError as exc:
                raise IndexNotFoundError("case has not been indexed") from exc
        return self._cache[case_id]

    def search_case(self, case_id: str, text: str, limit: int) -> list[SourceSpan]:
        """Up to `limit` eligible passages of this case, best first; `[]` if none is eligible."""
        return [s.span for s in self.search_case_scored(case_id, text, limit)]

    def search_case_scored(self, case_id: str, text: str, limit: int) -> list[ScoredSpan]:
        """As `search_case`, with the scores and eligibility signals of each span."""
        check_limit(limit)
        if not text.strip():
            raise ValueError("search text must be non-empty")
        index = self._index(case_id)
        candidates = [i for i, c in enumerate(index.chunks) if index.documents[c.doc].case_id == case_id]
        if not candidates:
            return []
        analysis = self._glossary.analyze(text)
        vector = None
        if self._config.mode is not SearchMode.LEXICAL:
            vector = self._embedder.embed_queries([text])[0]
        threshold = self._config.min_semantic_similarity
        hits = index.search(
            analysis,
            vector,
            candidates,
            self._config,
            self._embedder.min_similarity if threshold is None else threshold,
        )
        return [self._materialize(index, hit, case_id) for hit in hits[:limit]]

    def _materialize(self, index: SearchIndex[CaseDocument], hit: Hit, case_id: str) -> ScoredSpan:
        chunk = index.chunks[hit.chunk]
        indexed = index.documents[chunk.doc]
        fresh = self._store.get_document(indexed.doc_id, indexed.version_id)
        if fresh != indexed or fresh.case_id != case_id:
            raise StaleIndexError(
                f"{indexed.doc_id}@{indexed.version_id}: store metadata changed since indexing"
            )
        text = self._store.get_text(fresh.doc_id, fresh.version_id, chunk.start, chunk.end)
        if len(text) != chunk.end - chunk.start or sha256_text(text) != chunk.text_sha256:
            raise StaleIndexError(
                f"{indexed.doc_id}@{indexed.version_id}: text at offsets changed since indexing"
            )
        span = SourceSpan(
            source=SourceKind.CASE_FILE,
            doc_id=fresh.doc_id,
            version_id=fresh.version_id,
            start_char=chunk.start,
            end_char=chunk.end,
            text=text,
            pinpoint=_page_pinpoint(fresh, chunk.start, chunk.end),
        )
        return ScoredSpan(span, hit.score, hit.coverage, hit.similarity, hit.bm25)
