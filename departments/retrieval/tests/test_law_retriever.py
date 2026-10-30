"""LawRetriever on in-memory ZZ fakes: fidelity (AC1), filtering (AC2), no padding (§2.5), staleness."""

from collections.abc import Callable
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from legalai_contracts import Retriever, SourceKind
from legalai_retrieval import (
    HashingEmbedder,
    IndexBuildError,
    IndexNotFoundError,
    LawRetriever,
    RetrievalConfig,
    SearchMode,
    StaleIndexError,
)


def _all_queries(zz_set: Any) -> list[tuple[str, str]]:
    qs = [(q["text"], q["as_of"]) for q in zz_set.raw["law_queries"]]
    return qs + [(q["text"], "2026-01-01") for q in zz_set.raw["law_negatives"]]


def test_implements_retriever_port(law_retriever: LawRetriever) -> None:
    assert isinstance(law_retriever, Retriever)


def test_ac1_every_span_equals_store_text(
    law_retriever: LawRetriever, source_store: Any, zz_set: Any, make_query: Callable[..., Any]
) -> None:
    returned = 0
    for text, as_of in _all_queries(zz_set):
        for span in law_retriever.retrieve(make_query(text, as_of), 10):
            returned += 1
            assert span.source is SourceKind.LAW
            assert span.text == source_store.get_text(
                span.doc_id, span.version_id, span.start_char, span.end_char
            )
            assert span.pinpoint
    assert returned > 0


def test_ac2_no_span_from_other_jurisdiction_or_out_of_force_version(
    law_retriever: LawRetriever, source_store: Any, zz_set: Any, make_query: Callable[..., Any]
) -> None:
    for jurisdiction in ("ZZ", "ZZ-OT"):
        for as_of in ("2019-06-01", "2022-06-01", "2023-05-01", "2026-01-01", "2031-01-01"):
            for text, _ in _all_queries(zz_set):
                for span in law_retriever.retrieve(make_query(text, as_of, jurisdiction), 10):
                    doc = source_store.get_document(span.doc_id, span.version_id)
                    assert doc.jurisdiction == jurisdiction
                    assert doc.in_force_on(date.fromisoformat(as_of))


def test_other_jurisdiction_near_duplicate_is_never_returned(
    law_retriever: LawRetriever, make_query: Callable[..., Any]
) -> None:
    # The ZZ-OT document repeats ZZ wording verbatim; a ZZ query must still never reach it.
    text = "约定的违约金过分高于造成的损失的、人民法院可以根据当事人的请求予以适当减少。"
    zz = law_retriever.retrieve(make_query(text, "2026-01-01", "ZZ"), 10)
    assert zz and all(s.doc_id != "zz-ot-contract" for s in zz)
    ot = law_retriever.retrieve(make_query(text, "2026-01-01", "ZZ-OT"), 10)
    assert ot and all(s.doc_id == "zz-ot-contract" for s in ot)


def test_temporal_versions(law_retriever: LawRetriever, make_query: Callable[..., Any]) -> None:
    q = "合同纠纷的诉讼时效期间是几年"
    old = law_retriever.retrieve(make_query(q, "2023-05-01"), 3)
    new = law_retriever.retrieve(make_query(q, "2026-01-01"), 3)
    assert old[0].version_id == "2020-01-01" and "二年" in old[0].text
    assert new[0].version_id == "2025-01-01" and "三年" in new[0].text
    # 第一百零三条之一 exists only from the 2024 amendment of the fictional criminal law.
    q2 = "犯罪人本人掩饰隐瞒自己的犯罪所得来源、也要处罚吗"
    before = law_retriever.retrieve(make_query(q2, "2022-06-01"), 10)
    assert all(s.version_id != "2024-03-01" and s.pinpoint != "第一百零三条之一" for s in before)
    after = law_retriever.retrieve(make_query(q2, "2026-01-01"), 10)
    assert after[0].pinpoint == "第一百零三条之一"


def test_future_document_only_after_it_takes_effect(
    law_retriever: LawRetriever, make_query: Callable[..., Any]
) -> None:
    q = "通过电子商务平台订立的合同、自用户提交订单成功时成立"
    assert all(s.doc_id != "zz-ecommerce" for s in law_retriever.retrieve(make_query(q, "2026-01-01"), 10))
    assert law_retriever.retrieve(make_query(q, "2031-01-01"), 1)[0].doc_id == "zz-ecommerce"


def test_out_of_force_versions_do_not_influence_scores(
    zz_set: Any, stores: dict[str, type], tmp_path: Path, make_query: Callable[..., Any]
) -> None:
    """Filter-before-rank: removing every version not in force on as_of leaves scores unchanged."""
    as_of = "2026-01-01"
    full = LawRetriever(
        stores["source"](list(zz_set.law)), HashingEmbedder(), RetrievalConfig(tmp_path / "a")
    )
    full.build_index(["ZZ"])
    in_force = [
        (d, t) for d, t in zz_set.law if d.jurisdiction == "ZZ" and d.in_force_on(date.fromisoformat(as_of))
    ]
    pruned = LawRetriever(stores["source"](in_force), HashingEmbedder(), RetrievalConfig(tmp_path / "b"))
    pruned.build_index(["ZZ"])
    for q in zz_set.raw["law_queries"]:
        a = full.retrieve_scored(make_query(q["text"], as_of), 10)
        b = pruned.retrieve_scored(make_query(q["text"], as_of), 10)
        assert [(s.span, round(s.bm25, 9), s.lexical_coverage) for s in a] == [
            (s.span, round(s.bm25, 9), s.lexical_coverage) for s in b
        ]


def test_no_padding_off_topic_returns_empty(
    law_retriever: LawRetriever, zz_set: Any, make_query: Callable[..., Any]
) -> None:
    for q in zz_set.raw["law_negatives"]:
        assert law_retriever.retrieve(make_query(q["text"], "2026-01-01"), 10) == [], q["id"]


def test_every_result_meets_a_documented_threshold(
    law_retriever: LawRetriever, config: RetrievalConfig, zz_set: Any, make_query: Callable[..., Any]
) -> None:
    min_sim = HashingEmbedder().min_similarity
    for q in zz_set.raw["law_queries"]:
        for s in law_retriever.retrieve_scored(make_query(q["text"], q["as_of"]), 10):
            sim_ok = s.semantic_similarity is not None and s.semantic_similarity >= min_sim
            assert s.lexical_coverage >= config.min_lexical_coverage or sim_ok


def test_fewer_than_limit_when_few_are_eligible(
    law_retriever: LawRetriever, make_query: Callable[..., Any]
) -> None:
    spans = law_retriever.retrieve(make_query("第一百零三条之一", "2026-01-01"), 50)
    assert 0 < len(spans) < 50


def test_offline_recall_floor_with_fake_embedder(
    law_retriever: LawRetriever,
    zz_set: Any,
    evaluators: dict[str, Callable[..., Any]],
    summary: Callable[[Any], str],
) -> None:
    """Regression floor for the deterministic path (lexical + glossary + non-semantic fake).

    This is NOT AC3: the fake has no semantic ability. AC3 is measured with a real local model in
    test_live_embeddings.py. Chinese (CN first) must stay high even offline.
    Floors are just under the values measured on 2026-10-30: zh-zh 33/35, cross-lingual 23/39.
    """
    report = evaluators["law"](law_retriever, zz_set)
    print(summary(report))
    zh_hits, zh_n = report.recall(5, {"zh-zh"})
    assert zh_hits / zh_n >= 0.9
    x_hits, x_n = report.recall(5, {"zh-en", "en-zh"})
    assert x_hits / x_n >= 0.55


def test_lexical_mode_needs_no_embeddings(
    source_store: Any, config: RetrievalConfig, make_query: Callable[..., Any]
) -> None:
    retriever = LawRetriever(source_store, HashingEmbedder(), replace(config, mode=SearchMode.LEXICAL))
    retriever.build_index(["ZZ"])
    top = retriever.retrieve_scored(make_query("向社会公众吸收资金", "2026-01-01"), 3)
    assert top and all(s.semantic_similarity is None for s in top)


def test_unindexed_jurisdiction_is_an_error_not_empty(
    law_retriever: LawRetriever, make_query: Callable[..., Any]
) -> None:
    with pytest.raises(IndexNotFoundError):
        law_retriever.retrieve(make_query("合同", "2026-01-01", "ZZ-NO"), 5)


def test_invalid_limit(law_retriever: LawRetriever, make_query: Callable[..., Any]) -> None:
    with pytest.raises(ValueError, match="limit"):
        law_retriever.retrieve(make_query("合同", "2026-01-01"), 0)


def test_index_persists_and_reloads(
    law_retriever: LawRetriever, source_store: Any, config: RetrievalConfig, make_query: Callable[..., Any]
) -> None:
    q = make_query("非法吸收公众存款", "2026-01-01")
    fresh = LawRetriever(source_store, HashingEmbedder(), config)
    assert fresh.indexed_jurisdictions() == ["ZZ", "ZZ-OT"]
    assert fresh.retrieve(q, 5) == law_retriever.retrieve(q, 5)
    assert all(p.is_relative_to(config.data_dir / "retrieval") for p in config.data_dir.rglob("*"))


def test_embedder_mismatch_requires_rebuild(
    law_retriever: LawRetriever, source_store: Any, config: RetrievalConfig, make_query: Callable[..., Any]
) -> None:
    other = LawRetriever(source_store, HashingEmbedder(dimension=64), config)
    with pytest.raises(StaleIndexError, match="embedder"):
        other.retrieve(make_query("合同", "2026-01-01"), 5)


def test_changed_store_text_is_detected(
    law_retriever: LawRetriever, source_store: Any, make_query: Callable[..., Any]
) -> None:
    q = make_query("非法吸收公众存款数额巨大", "2026-01-01")
    span = law_retriever.retrieve(q, 1)[0]
    key = (span.doc_id, span.version_id)
    original = source_store.texts[key]
    source_store.texts[key] = original[: span.start_char] + "X" * len(span.text) + original[span.end_char :]
    with pytest.raises(StaleIndexError, match="text"):
        law_retriever.retrieve(q, 1)


def test_changed_store_metadata_is_detected(
    law_retriever: LawRetriever, source_store: Any, make_query: Callable[..., Any]
) -> None:
    q = make_query("非法吸收公众存款数额巨大", "2026-01-01")
    span = law_retriever.retrieve(q, 1)[0]
    key = (span.doc_id, span.version_id)
    # The corpus later records that this version ended: the indexed copy must not be trusted.
    source_store.docs[key] = source_store.docs[key].model_copy(update={"effective_to": date(2025, 6, 1)})
    with pytest.raises(StaleIndexError, match="metadata"):
        law_retriever.retrieve(q, 1)


def test_build_rejects_document_from_wrong_jurisdiction(
    zz_set: Any, stores: dict[str, type], config: RetrievalConfig
) -> None:
    class LeakyStore(stores["source"]):  # type: ignore[misc,name-defined]
        def list_documents(self, jurisdiction: str) -> list[Any]:
            return list(self.docs.values())

    with pytest.raises(IndexBuildError, match="jurisdiction"):
        LawRetriever(LeakyStore(list(zz_set.law)), HashingEmbedder(), config).build_index(["ZZ"])


def test_build_rejects_text_length_mismatch(
    zz_set: Any, stores: dict[str, type], config: RetrievalConfig
) -> None:
    class Truncating(stores["source"]):  # type: ignore[misc,name-defined]
        def get_text(self, doc_id: str, version_id: str, start_char: int, end_char: int) -> str:
            return str(super().get_text(doc_id, version_id, start_char, end_char))[:-1]

    with pytest.raises(IndexBuildError, match="char_count"):
        LawRetriever(Truncating(list(zz_set.law)), HashingEmbedder(), config).build_index(["ZZ"])


def test_build_rejects_empty_jurisdiction(source_store: Any, config: RetrievalConfig) -> None:
    with pytest.raises(IndexBuildError, match="no documents"):
        LawRetriever(source_store, HashingEmbedder(), config).build_index(["ZZ-NO"])


def test_invalid_jurisdiction_code_cannot_escape_data_dir(source_store: Any, config: RetrievalConfig) -> None:
    with pytest.raises(ValueError, match="jurisdiction"):
        LawRetriever(source_store, HashingEmbedder(), config).build_index(["../ZZ"])
