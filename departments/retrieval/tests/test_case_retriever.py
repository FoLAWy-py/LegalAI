"""CaseEvidenceRetriever: case isolation (AC2), fidelity and page pinpoints (AC1), deletion (P9)."""

import hashlib
from collections.abc import Callable
from typing import Any

import pytest

from legalai_contracts import EvidenceRetriever, SourceKind
from legalai_retrieval import (
    CaseEvidenceRetriever,
    HashingEmbedder,
    IndexBuildError,
    IndexNotFoundError,
    RetrievalConfig,
    StaleIndexError,
)

CASES = ("zz-case-001", "zz-case-002", "zz-case-003")


def _queries(zz_set: Any) -> list[str]:
    texts = [q["text"] for q in zz_set.raw["case_queries"]] + [
        q["text"] for q in zz_set.raw["case_negatives"]
    ]
    return texts + [q["text"] for q in zz_set.raw["law_queries"][:10]]


def test_implements_evidence_retriever_port(case_retriever: CaseEvidenceRetriever) -> None:
    assert isinstance(case_retriever, EvidenceRetriever)


def test_ac1_fidelity_and_page_pinpoints(
    case_retriever: CaseEvidenceRetriever, case_store: Any, zz_set: Any
) -> None:
    returned = 0
    for case_id in CASES:
        for text in _queries(zz_set):
            for span in case_retriever.search_case(case_id, text, 10):
                returned += 1
                doc = case_store.get_document(span.doc_id, span.version_id)
                assert span.source is SourceKind.CASE_FILE
                assert span.text == case_store.get_text(
                    span.doc_id, span.version_id, span.start_char, span.end_char
                )
                assert span.pinpoint == f"p. {doc.page_of(span.start_char)}"
    assert returned > 0


def test_ac2_search_never_leaves_its_case(
    case_retriever: CaseEvidenceRetriever, case_store: Any, zz_set: Any
) -> None:
    for case_id in CASES:
        for text in _queries(zz_set):
            for span in case_retriever.search_case(case_id, text, 10):
                assert case_store.get_document(span.doc_id, span.version_id).case_id == case_id


def test_text_unique_to_another_case_is_not_found(case_retriever: CaseEvidenceRetriever) -> None:
    other = "办公椅五百把、总价款五万ZZ元"  # only in zz-case-002
    assert case_retriever.search_case("zz-case-002", other, 5)[0].doc_id == "c2-contract"
    assert all(s.doc_id.startswith("c1-") for s in case_retriever.search_case("zz-case-001", other, 5))
    assert all(s.doc_id.startswith("c3-") for s in case_retriever.search_case("zz-case-003", other, 5))


def test_page_pinpoint_on_second_page(case_retriever: CaseEvidenceRetriever) -> None:
    top = case_retriever.search_case("zz-case-001", "卖方逾期交货的违约金是怎么约定的", 1)[0]
    assert top.doc_id == "c1-contract" and "第五条" in top.text and top.pinpoint == "p. 2"


def test_criminal_case_zh_queries(case_retriever: CaseEvidenceRetriever) -> None:
    top = case_retriever.search_case("zz-case-003", "被告人以承诺高额回报的方式向公众宣传", 3)
    assert any(s.doc_id in {"c3-indictment", "c3-witness"} for s in top)


def test_no_padding_for_unrelated_text(case_retriever: CaseEvidenceRetriever, zz_set: Any) -> None:
    for q in zz_set.raw["case_negatives"]:
        assert case_retriever.search_case(q["case_id"], q["text"], 10) == [], q["id"]


def test_offline_case_recall_floor(
    case_retriever: CaseEvidenceRetriever,
    zz_set: Any,
    evaluators: dict[str, Callable[..., Any]],
    summary: Callable[[Any], str],
) -> None:
    """Regression floor for the deterministic path only (measured 7/20 at R@5 on 2026-10-30).

    Most case queries are short paraphrases ("买方付款期限" vs "甲方…十五日内"); with the
    non-semantic fake they stay below the lexical threshold and correctly return fewer results
    rather than padded ones. Case recall with a real model is asserted in test_live_embeddings.py.
    """
    report = evaluators["cases"](case_retriever, zz_set)
    print(summary(report))
    hits, n = report.recall(5)
    assert hits / n >= 0.35
    for qid in ("cq01", "cq10", "cq11", "ccq01", "ccq08"):  # lexically answerable
        assert 0 < report.ranks[qid][1] <= 5, qid


def test_index_directory_does_not_reveal_case_id(
    case_retriever: CaseEvidenceRetriever, config: RetrievalConfig
) -> None:
    names = {p.name for p in (config.root / "cases").iterdir()}
    assert names == {hashlib.sha256(c.encode()).hexdigest() for c in CASES}


def test_delete_case_removes_index_and_only_that_case(
    case_retriever: CaseEvidenceRetriever, case_store: Any, config: RetrievalConfig
) -> None:
    target = config.root / "cases" / hashlib.sha256(b"zz-case-001").hexdigest()
    assert target.is_dir()
    assert case_retriever.delete_case("zz-case-001") is True
    assert not target.exists()
    with pytest.raises(IndexNotFoundError):
        case_retriever.search_case("zz-case-001", "违约金", 5)
    fresh = CaseEvidenceRetriever(case_store, HashingEmbedder(), config)
    with pytest.raises(IndexNotFoundError):
        fresh.search_case("zz-case-001", "违约金", 5)
    assert fresh.search_case("zz-case-002", "违约金", 5)
    assert case_retriever.delete_case("zz-case-001") is False


def test_unindexed_case_is_an_error(case_store: Any, config: RetrievalConfig) -> None:
    with pytest.raises(IndexNotFoundError):
        CaseEvidenceRetriever(case_store, HashingEmbedder(), config).search_case("zz-case-404", "x", 5)


def test_build_rejects_document_of_another_case(
    zz_set: Any, stores: dict[str, type], config: RetrievalConfig
) -> None:
    class LeakyStore(stores["case"]):  # type: ignore[misc,name-defined]
        def list_documents(self, case_id: str) -> list[Any]:
            return list(self.docs.values())

    with pytest.raises(IndexBuildError, match="another case"):
        CaseEvidenceRetriever(LeakyStore(list(zz_set.cases)), HashingEmbedder(), config).index_case(
            "zz-case-001"
        )


def test_changed_case_text_is_detected(case_retriever: CaseEvidenceRetriever, case_store: Any) -> None:
    span = case_retriever.search_case("zz-case-003", "被告人是否明知公司没有吸收存款的资质", 1)[0]
    key = (span.doc_id, span.version_id)
    text = case_store.texts[key]
    case_store.texts[key] = text[: span.start_char] + "Y" * len(span.text) + text[span.end_char :]
    with pytest.raises(StaleIndexError):
        case_retriever.search_case("zz-case-003", "被告人是否明知公司没有吸收存款的资质", 1)


def test_empty_search_text_rejected(case_retriever: CaseEvidenceRetriever) -> None:
    with pytest.raises(ValueError, match="non-empty"):
        case_retriever.search_case("zz-case-001", "   ", 5)


def test_rebuild_replaces_index(case_retriever: CaseEvidenceRetriever, config: RetrievalConfig) -> None:
    stats = case_retriever.index_case("zz-case-003")
    assert stats.documents == 5 and stats.chunks > 0
    leftovers = [p for p in (config.root / "cases").iterdir() if p.name.startswith(".")]
    assert leftovers == []
