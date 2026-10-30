"""Fixtures: in-memory ZZ fake stores built from tests/fixtures, and recall evaluation helpers.

The fakes implement the contract ports only; they stand in for corpus and casefile, which are
built in parallel (REQ-PMO-0001/0002). All data is synthetic (jurisdiction ZZ / ZZ-OT).
"""

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from legalai_contracts import CaseDocument, DocType, LegalQuery, SourceDocument
from legalai_retrieval import (
    CaseEvidenceRetriever,
    Embedder,
    HashingEmbedder,
    LawRetriever,
    RetrievalConfig,
)

DATA = Path(__file__).parent / "fixtures"
PAGE_MARK = "<<<PAGE>>>\n"
FIXED_TIME = datetime(2026, 10, 30, tzinfo=UTC)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class FakeSourceStore:
    """In-memory SourceStore."""

    def __init__(self, docs: list[tuple[SourceDocument, str]]) -> None:
        self.docs = {(d.doc_id, d.version_id): d for d, _ in docs}
        self.texts = {(d.doc_id, d.version_id): t for d, t in docs}
        self.calls: list[str] = []

    def list_documents(self, jurisdiction: str) -> list[SourceDocument]:
        self.calls.append(f"list:{jurisdiction}")
        return [d for d in self.docs.values() if d.jurisdiction == jurisdiction]

    def get_document(self, doc_id: str, version_id: str) -> SourceDocument:
        return self.docs[(doc_id, version_id)]

    def get_text(self, doc_id: str, version_id: str, start_char: int, end_char: int) -> str:
        text = self.texts[(doc_id, version_id)]
        if not 0 <= start_char < end_char <= len(text):
            raise IndexError("offsets outside document")
        return text[start_char:end_char]


class FakeCaseFileStore:
    """In-memory CaseFileStore."""

    def __init__(self, docs: list[tuple[CaseDocument, str]]) -> None:
        self.docs = {(d.doc_id, d.version_id): d for d, _ in docs}
        self.texts = {(d.doc_id, d.version_id): t for d, t in docs}

    def list_documents(self, case_id: str) -> list[CaseDocument]:
        return [d for d in self.docs.values() if d.case_id == case_id]

    def get_document(self, doc_id: str, version_id: str) -> CaseDocument:
        return self.docs[(doc_id, version_id)]

    def get_text(self, doc_id: str, version_id: str, start_char: int, end_char: int) -> str:
        text = self.texts[(doc_id, version_id)]
        if not 0 <= start_char < end_char <= len(text):
            raise IndexError("offsets outside document")
        return text[start_char:end_char]


def make_source_document(meta: dict[str, Any], text: str) -> SourceDocument:
    return SourceDocument(
        doc_id=meta["doc_id"],
        version_id=meta["version_id"],
        title=meta["title"],
        jurisdiction=meta["jurisdiction"],
        doc_type=DocType(meta["doc_type"]),
        language=meta["language"],
        effective_from=date.fromisoformat(meta["effective_from"]),
        effective_to=date.fromisoformat(meta["effective_to"]) if meta["effective_to"] else None,
        source_uri=f"synthetic://zz/{meta['doc_id']}/{meta['version_id']}",
        retrieved_at=FIXED_TIME,
        content_sha256=_sha(text),
        char_count=len(text),
    )


def make_case_document(meta: dict[str, Any], raw: str) -> tuple[CaseDocument, str]:
    pages = raw.split(PAGE_MARK)
    starts, pos = [], 0
    for page in pages:
        starts.append(pos)
        pos += len(page)
    text = "".join(pages)
    doc = CaseDocument(
        case_id=meta["case_id"],
        doc_id=meta["doc_id"],
        version_id=meta["version_id"],
        title=meta["title"],
        language=meta["language"],
        media_type="text/plain",
        received_at=FIXED_TIME,
        content_sha256=_sha(text),
        char_count=len(text),
        page_starts=tuple(starts),
    )
    return doc, text


@dataclass
class ZZSet:
    raw: dict[str, Any]
    law: list[tuple[SourceDocument, str]] = field(default_factory=list)
    cases: list[tuple[CaseDocument, str]] = field(default_factory=list)


@pytest.fixture(scope="session")
def zz_set() -> ZZSet:
    raw = json.loads((DATA / "zz_bilingual.json").read_text(encoding="utf-8"))
    out = ZZSet(raw)
    for meta in raw["law_documents"]:
        text = (DATA / meta["file"]).read_text(encoding="utf-8")
        out.law.append((make_source_document(meta, text), text))
    for meta in raw["case_documents"]:
        out.cases.append(make_case_document(meta, (DATA / meta["file"]).read_text(encoding="utf-8")))
    return out


@pytest.fixture
def source_store(zz_set: ZZSet) -> FakeSourceStore:
    return FakeSourceStore(list(zz_set.law))


@pytest.fixture
def case_store(zz_set: ZZSet) -> FakeCaseFileStore:
    return FakeCaseFileStore(list(zz_set.cases))


@pytest.fixture
def embedder() -> Embedder:
    return HashingEmbedder()


@pytest.fixture
def config(tmp_path: Path) -> RetrievalConfig:
    return RetrievalConfig(data_dir=tmp_path / "data")


@pytest.fixture
def law_retriever(source_store: FakeSourceStore, embedder: Embedder, config: RetrievalConfig) -> LawRetriever:
    retriever = LawRetriever(source_store, embedder, config)
    retriever.build_index(["ZZ", "ZZ-OT"])
    return retriever


@pytest.fixture
def case_retriever(
    case_store: FakeCaseFileStore, embedder: Embedder, config: RetrievalConfig
) -> CaseEvidenceRetriever:
    retriever = CaseEvidenceRetriever(case_store, embedder, config)
    for case_id in CASE_IDS:
        retriever.index_case(case_id)
    return retriever


CASE_IDS = ("zz-case-001", "zz-case-002", "zz-case-003")


def law_query(text: str, as_of: str, jurisdiction: str = "ZZ", qid: str = "q") -> LegalQuery:
    return LegalQuery(
        query_id=qid,
        text=text,
        jurisdiction=jurisdiction,
        as_of=date.fromisoformat(as_of),
        response_language="zh-CN",
    )


@dataclass
class RecallReport:
    """Per-category hit counts at k (1, 5) plus per-query ranks; rank 0 = not found within limit."""

    ranks: dict[str, tuple[str, int]] = field(default_factory=dict)

    def recall(self, k: int, categories: set[str] | None = None) -> tuple[int, int]:
        rows = [r for c, r in self.ranks.values() if categories is None or c in categories]
        return sum(1 for r in rows if 0 < r <= k), len(rows)

    def misses(self, k: int) -> list[str]:
        return [qid for qid, (_, r) in self.ranks.items() if not 0 < r <= k]


def evaluate_law(retriever: LawRetriever, zz: ZZSet, limit: int = 10) -> RecallReport:
    report = RecallReport()
    for q in zz.raw["law_queries"]:
        spans = retriever.retrieve(law_query(q["text"], q["as_of"], qid=q["id"]), limit)
        expected = {tuple(e) for e in q["expected"]}
        rank = next(
            (i for i, s in enumerate(spans, 1) if (s.doc_id, s.version_id, s.pinpoint) in expected),
            0,
        )
        report.ranks[q["id"]] = (q["category"], rank)
    return report


def evaluate_cases(retriever: CaseEvidenceRetriever, zz: ZZSet, limit: int = 10) -> RecallReport:
    report = RecallReport()
    for q in zz.raw["case_queries"]:
        spans = retriever.search_case(q["case_id"], q["text"], limit)
        rank = next(
            (
                i
                for i, s in enumerate(spans, 1)
                if any(s.doc_id == d and needle in s.text for d, needle in q["expected"])
            ),
            0,
        )
        report.ranks[q["id"]] = (q["category"], rank)
    return report


@pytest.fixture
def evaluators() -> dict[str, Callable[..., RecallReport]]:
    return {"law": evaluate_law, "cases": evaluate_cases}


@pytest.fixture
def make_query() -> Callable[..., LegalQuery]:
    return law_query


@pytest.fixture
def stores() -> dict[str, type]:
    """The fake store classes, for tests that build their own (e.g. with a mutated document set)."""
    return {"source": FakeSourceStore, "case": FakeCaseFileStore}


CROSS_LINGUAL = {"zh-en", "en-zh"}


def summarize(report: RecallReport) -> str:
    rows = []
    for label, cats in (
        ("zh-zh", {"zh-zh"}),
        ("en-en", {"en-en"}),
        ("cross-lingual", CROSS_LINGUAL),
        ("all", None),
    ):
        h1, n = report.recall(1, cats)
        h5, _ = report.recall(5, cats)
        if n:
            rows.append(f"{label}: R@1 {h1}/{n}={h1 / n:.2f} R@5 {h5}/{n}={h5 / n:.2f}")
    return " | ".join(rows) + f" | misses@5: {report.misses(5)}"


@pytest.fixture
def summary() -> Callable[[RecallReport], str]:
    return summarize
