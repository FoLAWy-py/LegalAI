"""Live comparison of local open-weight embedding models on the synthetic bilingual ZZ set.

Needs the optional `embeddings` extra and model weights already in the local Hugging Face cache
(nothing is downloaded: local_files_only). Skipped by default (`-m 'not live'`). Run:

    uv run --with 'sentence-transformers>=5.0' \
        pytest -m live -s departments/retrieval/tests/test_live_embeddings.py

Prints, per model: recall@1/@5 by query language pair for semantic-only (no glossary) and hybrid
(with glossary), and the similarity distribution used to calibrate `min_similarity`.
AC3 (cross-lingual top-5 >= 90%) is asserted for DEFAULT_EMBEDDING_MODEL only.
"""

import importlib.util
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from legalai_retrieval import (
    DEFAULT_EMBEDDING_MODEL,
    KNOWN_MODELS,
    CaseEvidenceRetriever,
    LawRetriever,
    RetrievalConfig,
    SearchMode,
    SentenceTransformerEmbedder,
)

pytestmark = pytest.mark.live

CROSS = {"zh-en", "en-zh"}


def _cached(name: str) -> bool:
    folder = Path.home() / ".cache" / "huggingface" / "hub" / ("models--" + name.replace("/", "--"))
    return folder.is_dir()


def _expected_rank(spans: list[Any], expected: set[tuple[str, str, str]]) -> int:
    return next(
        (
            i
            for i, s in enumerate(spans, 1)
            if (s.span.doc_id, s.span.version_id, s.span.pinpoint) in expected
        ),
        0,
    )


@pytest.mark.parametrize("name", sorted(KNOWN_MODELS))
def test_compare_embedder(
    name: str,
    tmp_path: Path,
    zz_set: Any,
    stores: dict[str, type],
    evaluators: dict[str, Callable[..., Any]],
    summary: Callable[[Any], str],
    make_query: Callable[..., Any],
) -> None:
    if importlib.util.find_spec("sentence_transformers") is None:
        pytest.skip("optional 'embeddings' extra not installed")
    if not _cached(name):
        pytest.skip(f"{name} weights not in the local Hugging Face cache")
    embedder = SentenceTransformerEmbedder.from_name(name)
    base = RetrievalConfig(data_dir=tmp_path)
    source_store = stores["source"](list(zz_set.law))
    case_store = stores["case"](list(zz_set.cases))
    LawRetriever(source_store, embedder, base).build_index(["ZZ", "ZZ-OT"])
    builder = CaseEvidenceRetriever(case_store, embedder, base)
    for case_id in ("zz-case-001", "zz-case-002", "zz-case-003"):
        builder.index_case(case_id)

    def law(cfg: RetrievalConfig) -> LawRetriever:
        return LawRetriever(source_store, embedder, cfg)

    def cases(cfg: RetrievalConfig) -> CaseEvidenceRetriever:
        return CaseEvidenceRetriever(case_store, embedder, cfg)

    print(f"\n===== {name} (license {KNOWN_MODELS[name].license}, min_similarity {embedder.min_similarity})")
    open_sem = replace(base, mode=SearchMode.SEMANTIC, use_glossary=False, min_semantic_similarity=-1.0)
    print(
        "semantic only, no glossary, no threshold: law  ", summary(evaluators["law"](law(open_sem), zz_set))
    )
    print(
        "                                          cases",
        summary(evaluators["cases"](cases(open_sem), zz_set)),
    )
    hybrid_report = evaluators["law"](law(base), zz_set)
    hybrid_cases = evaluators["cases"](cases(base), zz_set)
    print("hybrid + glossary, calibrated thresholds: law  ", summary(hybrid_report))
    print("                                          cases", summary(hybrid_cases))

    # Calibration evidence: similarity of the expected span vs. best similarity for negatives.
    probe = law(open_sem)
    pos: dict[str, list[float]] = {"same-language": [], "cross-lingual": []}
    for q in zz_set.raw["law_queries"]:
        res = probe.retrieve_scored(make_query(q["text"], q["as_of"]), 200)
        exp = {tuple(e) for e in q["expected"]}
        rank = _expected_rank(res, exp)
        if rank:
            sim = res[rank - 1].semantic_similarity
            assert sim is not None
            pos["cross-lingual" if q["category"] in CROSS else "same-language"].append(sim)
    neg = {}
    for q in zz_set.raw["law_negatives"]:
        res = probe.retrieve_scored(make_query(q["text"], "2026-01-01"), 1)
        neg[q["id"]] = res[0].semantic_similarity if res else None
    for label, sims in pos.items():
        if sims:
            sims.sort()
            print(f"expected-span similarity, {label}: min {sims[0]:.3f} p10 {sims[len(sims) // 10]:.3f}")
    print("best similarity per negative query:", {k: round(v, 3) for k, v in neg.items() if v is not None})
    case_probe = cases(open_sem)
    case_neg = {}
    for q in zz_set.raw["case_negatives"]:
        res = case_probe.search_case_scored(q["case_id"], q["text"], 1)
        case_neg[q["id"]] = round(res[0].semantic_similarity or 0.0, 3) if res else None
    print("best similarity per case negative:", case_neg)

    empty = [
        q["id"]
        for q in zz_set.raw["law_negatives"]
        if not law(base).retrieve(make_query(q["text"], "2026-01-01"), 5)
    ]
    print(f"negatives returning [] at calibrated thresholds: {len(empty)}/{len(zz_set.raw['law_negatives'])}")

    if name == DEFAULT_EMBEDDING_MODEL:
        hits, n = hybrid_report.recall(5, CROSS)
        assert hits / n >= 0.9, f"AC3 cross-lingual top-5 {hits}/{n}"
        zh_hits, zh_n = hybrid_report.recall(5, {"zh-zh"})
        assert zh_hits / zh_n >= 0.9, f"zh-zh top-5 {zh_hits}/{zh_n}"
        assert set(empty) == {q["id"] for q in zz_set.raw["law_negatives"]}, "negatives must return []"
        case_hits, case_n = hybrid_cases.recall(5)
        assert case_hits / case_n >= 0.9, f"case top-5 {case_hits}/{case_n}"
        case_empty = [
            q["id"]
            for q in zz_set.raw["case_negatives"]
            if not cases(base).search_case(q["case_id"], q["text"], 5)
        ]
        assert len(case_empty) == len(zz_set.raw["case_negatives"]), "case negatives must return []"
