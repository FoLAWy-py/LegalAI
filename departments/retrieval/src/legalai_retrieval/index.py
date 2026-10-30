"""On-disk search index for one scope (one jurisdiction, or one case) and the hybrid scorer."""

import hashlib
import json
import math
import shutil
import tempfile
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from legalai_contracts import CaseDocument, SourceDocument
from legalai_retrieval.chunking import CHUNKER_VERSION, TextUnit
from legalai_retrieval.config import RetrievalConfig, SearchMode
from legalai_retrieval.embedding import Embedder, Matrix
from legalai_retrieval.errors import IndexNotFoundError, StaleIndexError
from legalai_retrieval.text import QueryAnalysis, tokenize

INDEX_FORMAT = 1
_MANIFEST = "index.json"
_VECTORS = "embeddings.npy"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ChunkRecord:
    doc: int
    start: int
    end: int
    pinpoint: str
    text_sha256: str
    length: int


@dataclass(frozen=True)
class Hit:
    chunk: int
    score: float
    coverage: float
    similarity: float | None
    bm25: float


@dataclass(frozen=True)
class IndexedText[D: (SourceDocument, CaseDocument)]:
    """One document version, its full text as read from the store, and its units."""

    document: D
    text: str
    units: list[TextUnit]


class SearchIndex[D: (SourceDocument, CaseDocument)]:
    def __init__(
        self,
        kind: str,
        scope: str,
        embedder_id: str,
        documents: list[D],
        chunks: list[ChunkRecord],
        postings: dict[str, list[tuple[int, int]]],
        vectors: Matrix,
    ) -> None:
        if vectors.shape[0] != len(chunks):
            raise StaleIndexError("embedding rows do not match chunk count")
        self.kind = kind
        self.scope = scope
        self.embedder_id = embedder_id
        self.documents: list[D] = documents
        self.chunks = chunks
        self.postings = postings
        self.vectors = vectors

    @classmethod
    def build(
        cls, kind: str, scope: str, items: Sequence[IndexedText[D]], embedder: Embedder
    ) -> "SearchIndex[D]":
        documents: list[D] = []
        chunks: list[ChunkRecord] = []
        postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
        index_texts: list[str] = []
        for doc_idx, item in enumerate(items):
            documents.append(item.document)
            for unit in item.units:
                span_text = item.text[unit.start : unit.end]
                index_text = f"{unit.context}\n{span_text}" if unit.context else span_text
                tokens = tokenize(index_text)
                chunk_idx = len(chunks)
                for tok, tf in sorted(Counter(tokens).items()):
                    postings[tok].append((chunk_idx, tf))
                chunks.append(
                    ChunkRecord(
                        doc_idx, unit.start, unit.end, unit.pinpoint, sha256_text(span_text), len(tokens)
                    )
                )
                index_texts.append(index_text)
        empty: Matrix = np.zeros((0, 1), dtype=np.float32)
        vectors = embedder.embed_documents(index_texts) if index_texts else empty
        return cls(kind, scope, embedder.model_id, documents, chunks, dict(postings), vectors)

    # ---------- persistence ----------

    def save(self, directory: Path) -> None:
        """Write atomically: a complete new directory replaces the old one."""
        directory.parent.mkdir(parents=True, exist_ok=True)
        tmp = Path(tempfile.mkdtemp(prefix=f".{directory.name}.tmp-", dir=directory.parent))
        try:
            manifest = {
                "format": INDEX_FORMAT,
                "chunker": CHUNKER_VERSION,
                "kind": self.kind,
                "scope": self.scope,
                "embedder": self.embedder_id,
                "documents": [d.model_dump(mode="json") for d in self.documents],
                "chunks": [[c.doc, c.start, c.end, c.pinpoint, c.text_sha256, c.length] for c in self.chunks],
                "postings": {t: [list(p) for p in ps] for t, ps in sorted(self.postings.items())},
            }
            (tmp / _MANIFEST).write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
            np.save(tmp / _VECTORS, self.vectors, allow_pickle=False)
            old: Path | None = None
            if directory.exists():
                old = Path(tempfile.mkdtemp(prefix=f".{directory.name}.old-", dir=directory.parent))
                old.rmdir()
                directory.rename(old)
            tmp.rename(directory)
            if old is not None:
                shutil.rmtree(old)
        finally:
            if tmp.exists():
                shutil.rmtree(tmp)

    @classmethod
    def load(
        cls, directory: Path, kind: str, scope: str, doc_type: type[D], embedder: Embedder
    ) -> "SearchIndex[D]":
        manifest_path = directory / _MANIFEST
        if not manifest_path.is_file():
            raise IndexNotFoundError(f"no {kind} index for this scope at {directory}")
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        if raw.get("format") != INDEX_FORMAT or raw.get("chunker") != CHUNKER_VERSION:
            raise StaleIndexError("index format or chunker version changed; rebuild the index")
        if raw.get("kind") != kind or raw.get("scope") != scope:
            raise StaleIndexError(f"index at {directory} belongs to another scope")
        if raw.get("embedder") != embedder.model_id:
            built_with = raw.get("embedder")
            raise StaleIndexError(
                f"index built with embedder {built_with!r}, configured {embedder.model_id!r}; rebuild"
            )
        documents = [doc_type.model_validate(d) for d in raw["documents"]]
        chunks = [
            ChunkRecord(int(a), int(b), int(c), str(p), str(h), int(n)) for a, b, c, p, h, n in raw["chunks"]
        ]
        postings = {t: [(int(c), int(f)) for c, f in ps] for t, ps in raw["postings"].items()}
        vectors = np.load(directory / _VECTORS, allow_pickle=False).astype(np.float32)
        return cls(kind, scope, raw["embedder"], documents, chunks, postings, vectors)

    # ---------- search ----------

    def search(
        self,
        analysis: QueryAnalysis,
        query_vector: Matrix | None,
        candidates: Sequence[int],
        config: RetrievalConfig,
        min_similarity: float,
    ) -> list[Hit]:
        """Eligible hits among `candidates` only, best first. Nothing outside `candidates` is scored."""
        if not candidates:
            return []
        cand_set = set(candidates)
        n = len(candidates)
        avgdl = sum(self.chunks[c].length for c in candidates) / n or 1.0
        bm25: dict[int, float] = defaultdict(float)
        matched: dict[int, set[str]] = defaultdict(set)
        k1, b = config.bm25_k1, config.bm25_b
        for tok in sorted(analysis.search_tokens):
            posts = [(c, tf) for c, tf in self.postings.get(tok, ()) if c in cand_set]
            if not posts:
                continue
            df = len(posts)
            idf = math.log(1.0 + (n - df + 0.5) / (df + 0.5))
            for c, tf in posts:
                norm = k1 * (1.0 - b + b * self.chunks[c].length / avgdl)
                bm25[c] += idf * tf * (k1 + 1.0) / (tf + norm)
                matched[c].add(tok)

        sims: dict[int, float] = {}
        if query_vector is not None and config.mode is not SearchMode.LEXICAL:
            cand_arr = np.asarray(candidates, dtype=np.int64)
            scores = self.vectors[cand_arr] @ query_vector.reshape(-1)
            sims = {int(c): float(s) for c, s in zip(cand_arr, scores, strict=True)}

        lexical_rank = {c: r for r, c in enumerate(sorted(bm25, key=lambda c: (-bm25[c], c)), 1)}
        semantic_rank = {c: r for r, c in enumerate(sorted(sims, key=lambda c: (-sims[c], c)), 1)}

        hits: list[Hit] = []
        for c in candidates:
            coverage = analysis.coverage(matched[c]) if c in matched else 0.0
            sim = sims.get(c)
            lex_ok = coverage >= config.min_lexical_coverage
            sem_ok = sim is not None and sim >= min_similarity
            if config.mode is SearchMode.LEXICAL:
                eligible, score = lex_ok, bm25.get(c, 0.0)
            elif config.mode is SearchMode.SEMANTIC:
                eligible, score = sem_ok, sim if sim is not None else 0.0
            else:
                eligible = lex_ok or sem_ok
                score = 0.0
                if c in lexical_rank:
                    score += 1.0 / (config.rrf_k + lexical_rank[c])
                if c in semantic_rank:
                    score += 1.0 / (config.rrf_k + semantic_rank[c])
            if eligible:
                hits.append(Hit(c, score, coverage, sim, bm25.get(c, 0.0)))
        hits.sort(key=lambda h: (-h.score, h.chunk))
        return hits
