"""REQ-PMO-0005 AC2: the runner reports correct metric values for trivial baselines (hand-computed).

Hand counts of the synthetic set (see test_synthetic_dataset.test_hand_counted_totals):
11 cases (1 expected abstention: ZZ-CRIM-010); 36 expected elements (14 in en queries, 22 in zh queries);
62 expected links (23 en, 39 zh); 3 expected gaps (1 en, 2 zh); 98 expected citations; 80 adversarial items.
English-query cases: 001, 002, 003, 009, 010. Chinese-query cases: 004, 005, 006, 007, 008, 011.
"""

from datetime import UTC, datetime

import pytest

from legalai_contracts import (
    Citation,
    DraftAnswer,
    Element,
    EvidenceLink,
    EvidenceOutline,
    Gap,
    GapKind,
    LegalQuery,
    SourceKind,
    SourceSpan,
    VerificationReport,
)
from legalai_evaluation import (
    AbstainingVerifier,
    AlwaysAbstainBuilder,
    EvalReport,
    GateVerdict,
    OracleBuilder,
    OutlineStatus,
    OverallVerdict,
    Ratio,
    RubberStampVerifier,
    SyntheticDataset,
    load_synthetic_dataset,
    render_markdown,
    run_evaluation,
)

FIXED_TIME = datetime(2026, 10, 30, tzinfo=UTC)


@pytest.fixture(scope="module")
def dataset() -> SyntheticDataset:
    return load_synthetic_dataset()


def r(n: int, d: int) -> Ratio:
    return Ratio(numerator=n, denominator=d)


def gate(report: EvalReport) -> dict[str, GateVerdict]:
    return {g.metric: g.verdict for g in report.gate.results}


def test_always_abstain_baseline(dataset: SyntheticDataset) -> None:
    report = run_evaluation(dataset, AlwaysAbstainBuilder(), AbstainingVerifier(), created_at=FIXED_TIME)
    o = report.overall
    assert o.cases == 11
    assert o.contract_valid == r(11, 11)
    assert o.builder_errors == 0
    assert o.citation_resolvability == r(0, 0)
    assert o.exact_quote_match == r(0, 0)
    assert o.element_recall == r(0, 36)
    assert o.element_precision == r(0, 0)
    assert o.evidence_link_precision == r(0, 0)
    assert o.evidence_link_recall == r(0, 62)
    assert o.gap_precision == r(0, 0)
    assert o.gap_recall == r(0, 3)
    assert o.abstention_recall == r(1, 1)
    assert o.false_abstention == r(10, 10)
    assert o.verifier_pass == r(0, 0)
    assert o.law_recall_at_k is None and o.case_recall_at_k is None
    assert report.adversarial.items == 80
    assert report.adversarial.false_pass == 0
    # Nothing was cited, so the hard citation gates cannot be measured: fail closed as INCOMPLETE.
    assert gate(report)["citation_resolvability"] is GateVerdict.NOT_MEASURED
    assert gate(report)["adversarial_false_pass"] is GateVerdict.PASS
    assert report.gate.verdict is OverallVerdict.INCOMPLETE
    assert set(report.by_jurisdiction) == {"ZZ"}
    assert set(report.by_language) == {"en", "zh"}
    en, zh = report.by_language["en"], report.by_language["zh"]
    assert (en.cases, zh.cases) == (5, 6)
    assert en.element_recall == r(0, 14) and zh.element_recall == r(0, 22)
    assert en.evidence_link_recall == r(0, 23) and zh.evidence_link_recall == r(0, 39)
    assert en.gap_recall == r(0, 1) and zh.gap_recall == r(0, 2)
    assert en.abstention_recall == r(1, 1) and zh.abstention_recall == r(0, 0)
    assert en.false_abstention == r(4, 4) and zh.false_abstention == r(6, 6)
    assert all(c.status is OutlineStatus.ABSTAINED for c in report.cases)


def test_oracle_with_rubber_stamp_fails_the_adversarial_gate(dataset: SyntheticDataset) -> None:
    report = run_evaluation(dataset, OracleBuilder(dataset), RubberStampVerifier(), created_at=FIXED_TIME)
    o = report.overall
    assert o.citation_resolvability == r(98, 98)
    assert o.exact_quote_match == r(98, 98)
    assert o.citation_scope == r(98, 98)
    assert o.element_recall == r(36, 36) and o.element_precision == r(36, 36)
    assert o.evidence_link_precision == r(62, 62) and o.evidence_link_recall == r(62, 62)
    assert o.gap_precision == r(3, 3) and o.gap_recall == r(3, 3) and o.gap_kind_agreement == r(3, 3)
    assert o.abstention_recall == r(1, 1) and o.false_abstention == r(0, 10)
    assert o.verifier_pass == r(10, 10) and o.verifier_false_pass == 0
    assert report.adversarial.false_pass == 80
    assert report.adversarial.target_false_supported == 80
    assert all(v == r(10, 10) for v in report.adversarial.false_pass_by_kind.values())
    assert gate(report)["adversarial_false_pass"] is GateVerdict.FAIL
    assert report.gate.verdict is OverallVerdict.FAIL


def test_oracle_with_abstaining_verifier_passes_the_gate(dataset: SyntheticDataset) -> None:
    report = run_evaluation(dataset, OracleBuilder(dataset), AbstainingVerifier(), created_at=FIXED_TIME)
    assert gate(report)["citation_resolvability"] is GateVerdict.PASS
    assert gate(report)["exact_quote_match"] is GateVerdict.PASS
    assert gate(report)["adversarial_false_pass"] is GateVerdict.PASS
    assert gate(report)["element_recall"] is GateVerdict.NO_THRESHOLD
    assert report.gate.verdict is OverallVerdict.PASS


class ScriptedBuilder:
    """Returns given outlines by query id and abstains on everything else."""

    def __init__(self, outlines: dict[str, EvidenceOutline]) -> None:
        self._outlines = outlines

    def build_outline(self, query: LegalQuery) -> EvidenceOutline:
        if query.query_id in self._outlines:
            return self._outlines[query.query_id]
        return AlwaysAbstainBuilder().build_outline(query)


def _partially_wrong_builder(dataset: SyntheticDataset) -> ScriptedBuilder:
    # ZZ-CRIM-001 (3 elements, 5 links): drop E3 and its link L5, add a link to a fabricated document,
    # and add a spurious gap on E2.
    base = dataset.case("ZZ-CRIM-001").expected
    good_links = [link for link in base.links if link.element_id != "E3"]
    fake_span = SourceSpan(
        source=SourceKind.CASE_FILE,
        doc_id="zz-fabricated",
        version_id="v1",
        start_char=0,
        end_char=9,
        text="SYNTHETIC",
    )
    fabricated = EvidenceLink(
        link_id="L-fab",
        element_id="E1",
        citation=Citation(span=fake_span, quote="SYNTHETIC"),
        relation=good_links[0].relation,
        purpose="Fabricated exhibit.",
    )
    case_001 = EvidenceOutline(
        query=base.query,
        cause_of_action=base.cause_of_action,
        elements=base.elements[:2],
        links=(*good_links, fabricated),
        gaps=(Gap(element_id="E2", kind=GapKind.INSUFFICIENT, description="Spurious gap."),),
        traces=base.traces,
    )
    # ZZ-CRIM-010 expects abstention; answer it anyway, citing Article 30 of the 2022 version (not in force).
    abstain_case = dataset.case("ZZ-CRIM-010")
    doc = dataset.source_store.get_document("zz-penal-code", "2022")
    text = dataset.source_store.get_text(doc.doc_id, doc.version_id, 0, doc.char_count)
    start = text.index("Article 30 (")
    end = text.index("\n", start)
    a30 = SourceSpan(
        source=SourceKind.LAW,
        doc_id=doc.doc_id,
        version_id=doc.version_id,
        start_char=start,
        end_char=end,
        text=text[start:end],
        pinpoint="Article 30",
    )
    case_010 = EvidenceOutline(
        query=abstain_case.query,
        cause_of_action="Crypto-asset market manipulation",
        elements=(
            Element(
                element_id="E1",
                description="Orders placed without intent to execute.",
                legal_basis=(Citation(span=a30, quote="without intending them to be executed"),),
            ),
        ),
        gaps=(Gap(element_id="E1", kind=GapKind.NO_EVIDENCE, description="Not linked."),),
        traces=base.traces,
    )
    return ScriptedBuilder({base.query.query_id: case_001, abstain_case.query.query_id: case_010})


def test_partially_wrong_builder_hand_computed(dataset: SyntheticDataset) -> None:
    report = run_evaluation(
        dataset, _partially_wrong_builder(dataset), RubberStampVerifier(), created_at=FIXED_TIME
    )
    o = report.overall
    assert o.contract_valid == r(11, 11)
    # Citations: case 001 has 2 element + 5 link citations, one fabricated; case 010 has 1, resolvable but
    # not in force on as_of.
    assert o.citation_resolvability == r(7, 8)
    assert o.exact_quote_match == r(7, 8)
    assert o.citation_scope == r(6, 8)
    assert o.element_recall == r(2, 36)
    assert o.element_precision == r(2, 3)
    assert o.evidence_link_precision == r(4, 5)
    assert o.evidence_link_recall == r(4, 62)
    assert o.gap_precision == r(0, 2)
    assert o.gap_recall == r(0, 3)
    assert o.abstention_recall == r(0, 1)
    assert o.false_abstention == r(9, 10)
    assert o.verifier_pass == r(2, 2)
    assert o.verifier_false_pass == 2
    assert gate(report)["citation_resolvability"] is GateVerdict.FAIL
    assert report.gate.verdict is OverallVerdict.FAIL
    en, zh = report.by_language["en"], report.by_language["zh"]
    assert en.citation_resolvability == r(7, 8) and zh.citation_resolvability == r(0, 0)
    assert en.element_recall == r(2, 14) and en.element_precision == r(2, 3)
    assert zh.element_recall == r(0, 22)


class ExplodingBuilder:
    def build_outline(self, query: LegalQuery) -> EvidenceOutline:
        raise RuntimeError("model unavailable")


class UnvalidatedBuilder:
    """Bypasses contract validation with model_construct: a non-abstaining outline with no elements."""

    def build_outline(self, query: LegalQuery) -> EvidenceOutline:
        good = AlwaysAbstainBuilder().build_outline(query)
        return EvidenceOutline.model_construct(**{**dict(good), "abstained": False, "abstain_reason": None})


class WrongQueryBuilder:
    def build_outline(self, query: LegalQuery) -> EvidenceOutline:
        return AlwaysAbstainBuilder().build_outline(query.model_copy(update={"query_id": "other"}))


@pytest.mark.parametrize(
    ("builder", "status"),
    [
        (ExplodingBuilder(), OutlineStatus.ERROR),
        (UnvalidatedBuilder(), OutlineStatus.INVALID),
        (WrongQueryBuilder(), OutlineStatus.INVALID),
    ],
)
def test_broken_builders_are_scored_as_failures(
    dataset: SyntheticDataset, builder: object, status: OutlineStatus
) -> None:
    report = run_evaluation(dataset, builder, AbstainingVerifier(), created_at=FIXED_TIME)  # type: ignore[arg-type]
    assert report.overall.contract_valid == r(0, 11)
    assert all(c.status is status and c.error for c in report.cases)
    assert report.overall.builder_errors == (11 if status is OutlineStatus.ERROR else 0)
    assert report.overall.abstention_recall == r(0, 1)
    assert report.overall.element_recall == r(0, 36)


def test_fail_fast_propagates(dataset: SyntheticDataset) -> None:
    with pytest.raises(RuntimeError, match="model unavailable"):
        run_evaluation(dataset, ExplodingBuilder(), AbstainingVerifier(), fail_fast=True)


class ExplodingVerifier:
    def verify(self, draft: DraftAnswer) -> VerificationReport:
        raise RuntimeError("verifier down")

    def verify_outline(self, outline: EvidenceOutline) -> VerificationReport:
        raise RuntimeError("verifier down")


def test_verifier_errors_are_never_counted_as_pass(dataset: SyntheticDataset) -> None:
    report = run_evaluation(dataset, OracleBuilder(dataset), ExplodingVerifier(), created_at=FIXED_TIME)
    assert report.adversarial.false_pass == 0
    assert report.adversarial.verifier_errors == 80
    assert report.overall.verifier_pass == r(0, 0)
    assert all(c.verification_error for c in report.cases if not c.expects_abstention)


class EmptyRetriever:
    def retrieve(self, query: LegalQuery, limit: int) -> list[SourceSpan]:
        return []


class EmptyEvidenceRetriever:
    def search_case(self, case_id: str, text: str, limit: int) -> list[SourceSpan]:
        return []


def test_retrieval_recall(dataset: SyntheticDataset) -> None:
    full = run_evaluation(
        dataset,
        AlwaysAbstainBuilder(),
        AbstainingVerifier(),
        retriever=dataset.retriever,
        evidence_retriever=dataset.evidence_retriever,
        retrieval_k=1000,
        created_at=FIXED_TIME,
    )
    assert full.retrieval_k == 1000
    assert full.overall.law_recall_at_k == r(36, 36)
    assert full.overall.case_recall_at_k == r(62, 62)
    empty = run_evaluation(
        dataset,
        AlwaysAbstainBuilder(),
        AbstainingVerifier(),
        retriever=EmptyRetriever(),
        evidence_retriever=EmptyEvidenceRetriever(),
        created_at=FIXED_TIME,
    )
    assert empty.overall.law_recall_at_k == r(0, 36)
    assert empty.overall.case_recall_at_k == r(0, 62)
    assert empty.by_language["en"].law_recall_at_k == r(0, 14)
    with pytest.raises(ValueError, match="both"):
        run_evaluation(dataset, AlwaysAbstainBuilder(), AbstainingVerifier(), retriever=dataset.retriever)


def test_report_is_versioned_pinned_and_round_trips(dataset: SyntheticDataset, tmp_path: object) -> None:
    report = run_evaluation(dataset, OracleBuilder(dataset), AbstainingVerifier(), created_at=FIXED_TIME)
    assert report.report_schema_version == "1.0.0"
    assert report.dataset_id == "ZZ-SYNTH-CRIM-OUTLINE"
    assert report.dataset_version == "1.0.0"
    assert report.dataset_fingerprint == dataset.fingerprint()
    assert report.builder_name == "OracleBuilder" and report.verifier_name == "AbstainingVerifier"
    assert EvalReport.model_validate_json(report.to_json()) == report
    again = run_evaluation(dataset, OracleBuilder(dataset), AbstainingVerifier(), created_at=FIXED_TIME)
    assert again.overall == report.overall and again.gate == report.gate
    assert [c.traces for c in report.cases] == [c.expected.traces for c in dataset.cases]


def test_markdown_summary(dataset: SyntheticDataset) -> None:
    report = run_evaluation(dataset, AlwaysAbstainBuilder(), AbstainingVerifier(), created_at=FIXED_TIME)
    md = render_markdown(report)
    assert "Release gate: INCOMPLETE" in md
    assert dataset.fingerprint() in md
    assert "| element recall | 0.0% (0/36) |" in md
    assert "## By query language" in md


def test_ratio_rejects_inconsistent_values() -> None:
    with pytest.raises(ValueError):
        Ratio(numerator=1, denominator=2, value=0.9)
    with pytest.raises(ValueError):
        Ratio(numerator=3, denominator=2)
    assert Ratio(numerator=0, denominator=0).value is None
