"""Result types returned alongside contract `SourceSpan`s."""

from dataclasses import dataclass

from legalai_contracts import SourceSpan


@dataclass(frozen=True)
class ScoredSpan:
    """A returned span with the signals that made it eligible (for evaluation and audit).

    `score` orders results (RRF in hybrid mode, BM25 in lexical, cosine in semantic) and is not
    comparable across queries. `lexical_coverage` and `semantic_similarity` are the values tested
    against the documented eligibility thresholds.
    """

    span: SourceSpan
    score: float
    lexical_coverage: float
    semantic_similarity: float | None
    bm25: float


@dataclass(frozen=True)
class IndexStats:
    """What an index build wrote."""

    scope: str
    documents: int
    chunks: int


def check_limit(limit: int) -> None:
    if limit < 1:
        raise ValueError("limit must be >= 1")
