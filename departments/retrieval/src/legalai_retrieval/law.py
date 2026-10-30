"""Law retrieval: the `Retriever` port over an injected `SourceStore`."""

import re
from collections.abc import Iterable
from pathlib import Path

from legalai_contracts import LegalQuery, SourceDocument, SourceKind, SourceSpan, SourceStore
from legalai_retrieval.chunking import chunk_law
from legalai_retrieval.config import RetrievalConfig, SearchMode
from legalai_retrieval.embedding import Embedder
from legalai_retrieval.errors import IndexBuildError, IndexNotFoundError, StaleIndexError
from legalai_retrieval.glossary import Glossary
from legalai_retrieval.index import Hit, IndexedText, SearchIndex, sha256_text
from legalai_retrieval.results import IndexStats, ScoredSpan, check_limit

_JURISDICTION = re.compile(r"[A-Z]{2}(-[A-Z0-9]{1,3})?")
_KIND = "law"


class LawRetriever:
    """Hybrid (lexical + semantic) law retriever implementing `legalai_contracts.Retriever`.

    Guarantees for every span returned by `retrieve`:
    - its document version has exactly `query.jurisdiction` and is in force on `query.as_of`
      (filtered before any scoring; BM25 statistics come from the filtered set only);
    - its text equals `SourceStore.get_text` for its offsets, re-read at query time, and the
      store's document metadata still equals what was indexed (else `StaleIndexError`);
    - it starts at a structural unit (article / rule / section / paragraph) and has a pinpoint;
    - it passed the documented eligibility threshold (`RetrievalConfig`). No padding: if nothing
      is eligible, the result is `[]`.

    Raises `IndexNotFoundError` if `query.jurisdiction` was never indexed.
    """

    def __init__(
        self,
        store: SourceStore,
        embedder: Embedder,
        config: RetrievalConfig,
    ) -> None:
        self._store = store
        self._embedder = embedder
        self._config = config
        self._glossary = Glossary.default() if config.use_glossary else Glossary.empty()
        self._cache: dict[str, SearchIndex[SourceDocument]] = {}

    def _dir(self, jurisdiction: str) -> Path:
        if not _JURISDICTION.fullmatch(jurisdiction):
            raise ValueError(f"invalid jurisdiction code {jurisdiction!r}")
        return self._config.root / _KIND / jurisdiction

    def build_index(self, jurisdictions: Iterable[str]) -> list[IndexStats]:
        """(Re)build the index of every version the store lists for each jurisdiction."""
        stats: list[IndexStats] = []
        for jurisdiction in jurisdictions:
            directory = self._dir(jurisdiction)
            docs = sorted(self._store.list_documents(jurisdiction), key=lambda d: (d.doc_id, d.version_id))
            if not docs:
                raise IndexBuildError(f"store lists no documents for jurisdiction {jurisdiction!r}")
            seen: set[tuple[str, str]] = set()
            items: list[IndexedText[SourceDocument]] = []
            for doc in docs:
                key = (doc.doc_id, doc.version_id)
                if doc.jurisdiction != jurisdiction:
                    raise IndexBuildError(
                        f"{key} has jurisdiction {doc.jurisdiction!r}, expected {jurisdiction!r}"
                    )
                if key in seen:
                    raise IndexBuildError(f"duplicate document version {key}")
                seen.add(key)
                text = self._store.get_text(doc.doc_id, doc.version_id, 0, doc.char_count)
                if len(text) != doc.char_count:
                    raise IndexBuildError(
                        f"{key}: store text length {len(text)} != char_count {doc.char_count}"
                    )
                items.append(IndexedText(doc, text, chunk_law(text, self._config.max_chunk_chars)))
            index = SearchIndex.build(_KIND, jurisdiction, items, self._embedder)
            index.save(directory)
            self._cache[jurisdiction] = index
            stats.append(IndexStats(jurisdiction, len(index.documents), len(index.chunks)))
        return stats

    def indexed_jurisdictions(self) -> list[str]:
        """Jurisdictions with an index on disk."""
        base = self._config.root / _KIND
        if not base.is_dir():
            return []
        return sorted(p.name for p in base.iterdir() if p.is_dir() and _JURISDICTION.fullmatch(p.name))

    def _index(self, jurisdiction: str) -> SearchIndex[SourceDocument]:
        if jurisdiction not in self._cache:
            try:
                self._cache[jurisdiction] = SearchIndex.load(
                    self._dir(jurisdiction), _KIND, jurisdiction, SourceDocument, self._embedder
                )
            except IndexNotFoundError as exc:
                raise IndexNotFoundError(f"jurisdiction {jurisdiction!r} has not been indexed") from exc
        return self._cache[jurisdiction]

    def retrieve(self, query: LegalQuery, limit: int) -> list[SourceSpan]:
        """Up to `limit` eligible law spans, best first; `[]` if none is eligible."""
        return [s.span for s in self.retrieve_scored(query, limit)]

    def retrieve_scored(self, query: LegalQuery, limit: int) -> list[ScoredSpan]:
        """As `retrieve`, with the scores and eligibility signals of each span."""
        check_limit(limit)
        index = self._index(query.jurisdiction)
        candidates = [
            i
            for i, chunk in enumerate(index.chunks)
            if index.documents[chunk.doc].jurisdiction == query.jurisdiction
            and index.documents[chunk.doc].in_force_on(query.as_of)
        ]
        if not candidates:
            return []
        analysis = self._glossary.analyze(query.text)
        vector = None
        if self._config.mode is not SearchMode.LEXICAL:
            vector = self._embedder.embed_queries([query.text])[0]
        threshold = self._config.min_semantic_similarity
        hits = index.search(
            analysis,
            vector,
            candidates,
            self._config,
            self._embedder.min_similarity if threshold is None else threshold,
        )
        return [self._materialize(index, hit, query) for hit in hits[:limit]]

    def _materialize(self, index: SearchIndex[SourceDocument], hit: Hit, query: LegalQuery) -> ScoredSpan:
        chunk = index.chunks[hit.chunk]
        indexed = index.documents[chunk.doc]
        fresh = self._store.get_document(indexed.doc_id, indexed.version_id)
        if fresh != indexed:
            raise StaleIndexError(
                f"{indexed.doc_id}@{indexed.version_id}: store metadata changed since indexing"
            )
        if fresh.jurisdiction != query.jurisdiction or not fresh.in_force_on(query.as_of):
            raise StaleIndexError(
                f"{indexed.doc_id}@{indexed.version_id}: failed jurisdiction/as_of re-check"
            )
        text = self._store.get_text(fresh.doc_id, fresh.version_id, chunk.start, chunk.end)
        if len(text) != chunk.end - chunk.start or sha256_text(text) != chunk.text_sha256:
            raise StaleIndexError(
                f"{indexed.doc_id}@{indexed.version_id}: text at offsets changed since indexing"
            )
        span = SourceSpan(
            source=SourceKind.LAW,
            doc_id=fresh.doc_id,
            version_id=fresh.version_id,
            start_char=chunk.start,
            end_char=chunk.end,
            text=text,
            pinpoint=chunk.pinpoint,
        )
        return ScoredSpan(span, hit.score, hit.coverage, hit.similarity, hit.bm25)
