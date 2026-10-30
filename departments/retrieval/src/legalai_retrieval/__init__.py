"""LegalAI retrieval department. Public API: only names in __all__ may be imported by other departments.

- `LawRetriever` implements the `Retriever` port (law, filtered by jurisdiction and as_of before ranking).
- `CaseEvidenceRetriever` implements the `EvidenceRetriever` port (one case's files only).
- `Embedder` is the local embedding port; `SentenceTransformerEmbedder` runs open-weight models from
  local files (optional `embeddings` extra); `HashingEmbedder` is a deterministic non-semantic fake.
"""

from legalai_retrieval.cases import CaseEvidenceRetriever
from legalai_retrieval.config import DEFAULT_MIN_LEXICAL_COVERAGE, RetrievalConfig, SearchMode
from legalai_retrieval.embedding import (
    DEFAULT_EMBEDDING_MODEL,
    KNOWN_MODELS,
    Embedder,
    EmbeddingModelSpec,
    HashingEmbedder,
    SentenceTransformerEmbedder,
)
from legalai_retrieval.errors import IndexBuildError, IndexNotFoundError, RetrievalError, StaleIndexError
from legalai_retrieval.law import LawRetriever
from legalai_retrieval.results import IndexStats, ScoredSpan

__all__ = [
    "DEFAULT_EMBEDDING_MODEL",
    "DEFAULT_MIN_LEXICAL_COVERAGE",
    "KNOWN_MODELS",
    "CaseEvidenceRetriever",
    "Embedder",
    "EmbeddingModelSpec",
    "HashingEmbedder",
    "IndexBuildError",
    "IndexNotFoundError",
    "IndexStats",
    "LawRetriever",
    "RetrievalConfig",
    "RetrievalError",
    "ScoredSpan",
    "SearchMode",
    "SentenceTransformerEmbedder",
    "StaleIndexError",
]
