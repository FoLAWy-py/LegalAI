"""Typed configuration, injected by interface (retrieval never reads environment variables)."""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class SearchMode(StrEnum):
    HYBRID = "hybrid"
    LEXICAL = "lexical"
    SEMANTIC = "semantic"


DEFAULT_MIN_LEXICAL_COVERAGE = 0.6
"""A chunk is lexically eligible if it covers >= 60% of the query's content units (characters for
Chinese, words for English, article references), counting glossary translations. See REQ-PMO-0003 §8."""


@dataclass(frozen=True)
class RetrievalConfig:
    """Retrieval settings.

    Eligibility (the anti-padding rule): a chunk can be returned only if its lexical coverage is
    >= `min_lexical_coverage` or its embedding similarity is >= the semantic threshold (the
    embedder's calibrated `min_similarity` unless `min_semantic_similarity` overrides it). In
    LEXICAL / SEMANTIC mode only that signal counts. Eligible chunks are ordered by reciprocal-rank
    fusion of the BM25 and similarity rankings. If nothing is eligible the result is empty.
    """

    data_dir: Path
    """LEGALAI_DATA_DIR. Indexes are written under `data_dir / "retrieval"` only."""
    mode: SearchMode = SearchMode.HYBRID
    min_lexical_coverage: float = DEFAULT_MIN_LEXICAL_COVERAGE
    min_semantic_similarity: float | None = None
    rrf_k: int = 60
    bm25_k1: float = 1.2
    bm25_b: float = 0.75
    max_chunk_chars: int = 800
    use_glossary: bool = True

    def __post_init__(self) -> None:
        if not 0.0 < self.min_lexical_coverage <= 1.0:
            raise ValueError("min_lexical_coverage must be in (0, 1]")
        if self.min_semantic_similarity is not None and not -1.0 <= self.min_semantic_similarity <= 1.0:
            raise ValueError("min_semantic_similarity must be in [-1, 1]")
        if self.rrf_k < 1 or self.max_chunk_chars < 50:
            raise ValueError("rrf_k must be >= 1 and max_chunk_chars >= 50")

    @property
    def root(self) -> Path:
        return self.data_dir / "retrieval"
