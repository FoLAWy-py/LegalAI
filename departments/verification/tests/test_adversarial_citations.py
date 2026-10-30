"""REQ-PMO-0004 AC1 + AC2: adversarial citation set, 0 false SUPPORTED, Phase A makes no model call.

Each case corrupts one citation. The model used is an adversarial yes-man (`ApprovingModel`) that would
approve anything reaching it, so a bad citation can only be stopped by Phase A. CN text first: full-width
punctuation, Chinese quotation marks, ideographic space, compatibility/radical code points.
"""

import unicodedata
from collections.abc import Callable
from dataclasses import dataclass

import pytest

from legalai_contracts import (
    Citation,
    EvidenceOutline,
    ReportStatus,
    SourceKind,
    SourceSpan,
    Verdict,
)
from legalai_verification import IndependentVerifier
from legalai_verification._testkit import (
    ACT,
    ART1,
    ART1_QUOTE,
    ART2,
    ART2_QUOTE,
    ART3,
    CONTRACT,
    EMAIL,
    EMAIL_PAGE2_SENTENCE,
    EMAIL_QUOTE,
    EMAIL_SENTENCE,
    OLD_ART1,
    OTHER_EMAIL,
    RULES,
    RULES_ART1,
    SALE_ACT,
    SALE_S1,
    ApprovingModel,
    ExplodingModel,
    World,
    build_world,
    case_cite,
    element,
    good_elements,
    good_links,
    law_cite,
    link,
    outline,
    raw_citation,
)

CI = Verdict.CITATION_INVALID


def _store_text(world: World, kind: SourceKind, doc_id: str, version_id: str) -> str:
    if kind is SourceKind.LAW:
        return world.sources.full_text(doc_id, version_id)
    return world.cases.full_text(doc_id, version_id)


def altered(
    world: World,
    kind: SourceKind,
    doc_id: str,
    version_id: str,
    context: str,
    quote: str,
    old: str,
    new: str,
) -> Citation:
    """A contract-valid citation whose span text and quote were altered consistently (old -> new)."""
    start = _store_text(world, kind, doc_id, version_id).index(context)
    text, new_quote = context.replace(old, new), quote.replace(old, new)
    assert text != context, "alteration must change the span text"
    span = SourceSpan(
        source=kind,
        doc_id=doc_id,
        version_id=version_id,
        start_char=start,
        end_char=start + len(text),
        text=text,
    )
    return Citation(span=span, quote=new_quote)


def moved(
    world: World, kind: SourceKind, doc_id: str, version_id: str, context: str, quote: str, by: int
) -> Citation:
    """Same text and quote, offsets shifted by `by` code points (contract-valid)."""
    start = _store_text(world, kind, doc_id, version_id).index(context) + by
    span = SourceSpan(
        source=kind,
        doc_id=doc_id,
        version_id=version_id,
        start_char=start,
        end_char=start + len(context),
        text=context,
    )
    return Citation(span=span, quote=quote)


def at(
    doc_id: str, version_id: str, start: int, text: str, quote: str, kind: SourceKind = SourceKind.LAW
) -> Citation:
    span = SourceSpan(
        source=kind,
        doc_id=doc_id,
        version_id=version_id,
        start_char=start,
        end_char=start + len(text),
        text=text,
    )
    return Citation(span=span, quote=quote)


def law_case(c: Callable[[World], Citation], *, validate: bool = True) -> Callable[[World], EvidenceOutline]:
    """Outline whose only item is element e1 citing the corrupted law citation.

    `validate=False` builds it without contract validation (a draft that bypassed the validators)."""
    return lambda w: outline(
        w, (element("e1", "被告未按照约定交付标的物", c(w), validate=validate),), validate=validate
    )


def evidence_case(
    c: Callable[[World], Citation], *, validate: bool = True
) -> Callable[[World], EvidenceOutline]:
    """Outline with a corrupted evidence link l1. Its element e1 also fails Phase A (fabricated law),
    so no item in the outline may reach the model."""

    def build(w: World) -> EvidenceOutline:
        anchor = element("e1", "被告未按照约定交付标的物", at("zz-no-such-act", "v1", 0, ART1, ART1_QUOTE))
        lk = link("l1", "e1", c(w), "证明乙方自认无法按期交付货物", validate=validate)
        return outline(w, (anchor,), (lk,), validate=validate)

    return build


@dataclass(frozen=True)
class Case:
    name: str
    build: Callable[[World], EvidenceOutline]
    item_id: str
    expected: Verdict


L = SourceKind.LAW
C = SourceKind.CASE_FILE

LAW_CASES = [
    # fabricated / unresolvable
    Case(
        "fabricated_doc_id",
        law_case(lambda w: at("zz-fabricated-act", "v2025", 30, ART1, ART1_QUOTE)),
        "e1",
        CI,
    ),
    Case("fabricated_version_id", law_case(lambda w: at(ACT, "v2099", 30, ART1, ART1_QUOTE)), "e1", CI),
    # altered text / quote
    Case(
        "altered_quote_and_span",
        law_case(lambda w: altered(w, L, ACT, "v2025", ART1, ART1_QUOTE, "承担“违约责任”", "赔偿全部损失")),
        "e1",
        CI,
    ),
    Case(
        "altered_quote_bypassing_contract",
        law_case(
            lambda w: raw_citation(
                source=L,
                doc_id=ACT,
                version_id="v2025",
                start_char=w.sources.full_text(ACT, "v2025").index(ART1),
                end_char=w.sources.full_text(ACT, "v2025").index(ART1) + len(ART1),
                text=ART1,
                quote="当事人一方未按照约定交付标的物的，应当赔偿对方全部损失",
            ),
            validate=False,
        ),
        "e1",
        CI,
    ),
    Case(
        "altered_span_text_bypassing_contract",
        law_case(
            lambda w: raw_citation(
                source=L,
                doc_id=ACT,
                version_id="v2025",
                start_char=w.sources.full_text(ACT, "v2025").index(ART1),
                end_char=w.sources.full_text(ACT, "v2025").index(ART1) + len(ART1),
                text=ART1.replace("违约责任", "赔偿责任"),
                quote="未按照约定交付标的物",
            ),
            validate=False,
        ),
        "e1",
        CI,
    ),
    # offsets
    Case(
        "shifted_offsets_plus_one",
        law_case(lambda w: moved(w, L, ACT, "v2025", ART1, ART1_QUOTE, 1)),
        "e1",
        CI,
    ),
    Case(
        "shifted_offsets_minus_one",
        law_case(lambda w: moved(w, L, ACT, "v2025", ART1, ART1_QUOTE, -1)),
        "e1",
        CI,
    ),
    Case(
        "utf16_offsets_after_non_bmp_char",
        law_case(lambda w: moved(w, L, RULES, "v1", RULES_ART1, "应当提供证据", 1)),
        "e1",
        CI,
    ),
    Case(
        "offsets_beyond_document_end",
        law_case(lambda w: at(ACT, "v2025", len(w.sources.full_text(ACT, "v2025")) - 3, ART2, ART2_QUOTE)),
        "e1",
        CI,
    ),
    # outdated / not in force
    Case(
        "outdated_version",
        law_case(lambda w: law_cite(w, ACT, "v2020", OLD_ART1, "应当赔偿对方损失")),
        "e1",
        Verdict.NOT_IN_FORCE,
    ),
    Case(
        "outdated_quote_against_current_version",
        law_case(
            lambda w: at(
                ACT, "v2025", w.sources.full_text(ACT, "v2020").index(OLD_ART1), OLD_ART1, "赔偿对方损失"
            )
        ),
        "e1",
        CI,
    ),
    Case(
        "future_version",
        law_case(lambda w: law_cite(w, "zz-future-act", "v1", ART1, ART1_QUOTE)),
        "e1",
        Verdict.NOT_IN_FORCE,
    ),
    Case(
        "expires_exactly_on_as_of",
        law_case(lambda w: law_cite(w, "zz-interim-rules", "v1", ART1, ART1_QUOTE)),
        "e1",
        Verdict.NOT_IN_FORCE,
    ),
    # jurisdiction / authority / kind
    Case(
        "wrong_jurisdiction",
        law_case(lambda w: law_cite(w, "zz-b-contract-act", "v1", ART1, ART1_QUOTE)),
        "e1",
        Verdict.WRONG_JURISDICTION,
    ),
    Case(
        "secondary_source_as_law",
        law_case(lambda w: law_cite(w, "zz-commentary", "v1", ART1, ART1_QUOTE)),
        "e1",
        CI,
    ),
    Case(
        "case_file_cited_as_legal_basis",
        lambda w: outline(
            w,
            (
                element(
                    "e1",
                    "被告未按照约定交付标的物",
                    case_cite(w, EMAIL, EMAIL_SENTENCE, EMAIL_QUOTE),
                    validate=False,
                ),
            ),
            validate=False,
        ),
        "e1",
        CI,
    ),
    Case(
        "empty_legal_basis",
        lambda w: outline(w, (element("e1", "x", validate=False),), validate=False),
        "e1",
        CI,
    ),
    Case(
        "blank_quote_ideographic_space",
        law_case(lambda w: law_cite(w, ACT, "v2025", ART1, "\u3000")),
        "e1",
        CI,
    ),
    Case(
        "one_bad_citation_among_good",
        lambda w: outline(
            w,
            (
                element(
                    "e1",
                    "被告未按照约定交付标的物",
                    law_cite(w, ACT, "v2025", ART1, ART1_QUOTE),
                    at("zz-fabricated-act", "v1", 0, ART2, ART2_QUOTE),
                ),
            ),
        ),
        "e1",
        CI,
    ),
]

# CN exactness: every alteration below is a plausible OCR/IME/normalization artefact. Each must fail.
CN_EXACTNESS_CASES = [
    Case(
        "cn_halfwidth_comma",
        law_case(lambda w: altered(w, L, ACT, "v2025", ART1, ART1_QUOTE, "，", ",")),
        "e1",
        CI,
    ),
    Case(
        "cn_halfwidth_full_stop",
        law_case(lambda w: altered(w, L, ACT, "v2025", ART1, ART1_QUOTE, "。", ".")),
        "e1",
        CI,
    ),
    Case(
        "cn_ascii_double_quotes",
        law_case(lambda w: altered(w, L, ACT, "v2025", ART1, ART1_QUOTE, "“违约责任”", '"违约责任"')),
        "e1",
        CI,
    ),
    Case(
        "cn_corner_brackets_for_curly_quotes",
        law_case(lambda w: altered(w, L, ACT, "v2025", ART1, ART1_QUOTE, "“违约责任”", "「违约责任」")),
        "e1",
        CI,
    ),
    Case(
        "cn_ascii_space_for_ideographic_space",
        law_case(lambda w: altered(w, L, ACT, "v2025", ART1, "第一条\u3000当事人", "\u3000", " ")),
        "e1",
        CI,
    ),
    Case(
        "cn_kangxi_radical_one_nfkc_equal",
        law_case(lambda w: altered(w, L, ACT, "v2025", ART1, ART1_QUOTE, "一", "\u2f00")),
        "e1",
        CI,
    ),
    Case(
        "cn_compatibility_ideograph_nfc_equal",
        law_case(lambda w: altered(w, L, ACT, "v2025", ART3, "支付违约金", "金", "\uf90a")),
        "e1",
        CI,
    ),
    Case(
        "cn_traditional_for_simplified",
        law_case(lambda w: altered(w, L, ACT, "v2025", ART1, ART1_QUOTE, "约定", "約定")),
        "e1",
        CI,
    ),
    Case(
        "cn_zero_width_space_inserted",
        law_case(lambda w: altered(w, L, ACT, "v2025", ART1, ART1_QUOTE, "违约", "违\u200b约")),
        "e1",
        CI,
    ),
    Case(
        "cn_bom_prefixed",
        law_case(lambda w: altered(w, L, ACT, "v2025", ART1, ART1_QUOTE, "第", "\ufeff第")),
        "e1",
        CI,
    ),
    Case(
        "en_no_break_space",
        law_case(lambda w: altered(w, L, SALE_ACT, "v1", SALE_S1, "fails to deliver", "s. 1", "s.\u00a01")),
        "e1",
        CI,
    ),
]

EVIDENCE_CASES = [
    Case(
        "evidence_from_another_case",
        evidence_case(lambda w: case_cite(w, OTHER_EMAIL, EMAIL_SENTENCE, EMAIL_QUOTE)),
        "l1",
        CI,
    ),
    Case(
        "fabricated_case_doc_id",
        evidence_case(lambda w: at("zz-email-404", "v1", 0, EMAIL_SENTENCE, EMAIL_QUOTE, C)),
        "l1",
        CI,
    ),
    Case(
        "fabricated_case_version",
        evidence_case(lambda w: at(EMAIL, "v9", 0, EMAIL_SENTENCE, EMAIL_QUOTE, C)),
        "l1",
        CI,
    ),
    Case(
        "evidence_fullwidth_digits_to_ascii",
        evidence_case(
            lambda w: altered(
                w, C, EMAIL, "v1", EMAIL_PAGE2_SENTENCE, "ZZ币１０，０００元", "１０，０００", "10,000"
            )
        ),
        "l1",
        CI,
    ),
    Case(
        "evidence_curly_quotes_dropped",
        evidence_case(
            lambda w: altered(w, C, EMAIL, "v1", EMAIL_PAGE2_SENTENCE, "支付“违约金”", "“违约金”", "违约金")
        ),
        "l1",
        CI,
    ),
    Case(
        "evidence_altered_fact",
        evidence_case(lambda w: altered(w, C, EMAIL, "v1", EMAIL_SENTENCE, EMAIL_QUOTE, "无法", "可以")),
        "l1",
        CI,
    ),
    Case(
        "evidence_shifted_offsets",
        evidence_case(lambda w: moved(w, C, EMAIL, "v1", EMAIL_SENTENCE, EMAIL_QUOTE, 2)),
        "l1",
        CI,
    ),
    Case(
        "evidence_offsets_beyond_end",
        evidence_case(
            lambda w: at(EMAIL, "v1", len(w.cases.full_text(EMAIL, "v1")) - 2, EMAIL_SENTENCE, EMAIL_QUOTE, C)
        ),
        "l1",
        CI,
    ),
    Case(
        "law_span_cited_as_evidence",
        evidence_case(lambda w: law_cite(w, ACT, "v2025", ART1, ART1_QUOTE), validate=False),
        "l1",
        CI,
    ),
    Case(
        "evidence_quote_bypassing_contract",
        evidence_case(
            lambda w: raw_citation(
                source=C,
                doc_id=EMAIL,
                version_id="v1",
                start_char=w.cases.full_text(EMAIL, "v1").index(EMAIL_SENTENCE),
                end_char=w.cases.full_text(EMAIL, "v1").index(EMAIL_SENTENCE) + len(EMAIL_SENTENCE),
                text=EMAIL_SENTENCE,
                quote="我方已按期交付货物",
            ),
            validate=False,
        ),
        "l1",
        CI,
    ),
    Case(
        "evidence_blank_quote",
        evidence_case(lambda w: case_cite(w, EMAIL, EMAIL_SENTENCE + "\n", "\n")),
        "l1",
        CI,
    ),
]

ALL_CASES = LAW_CASES + CN_EXACTNESS_CASES + EVIDENCE_CASES


def _run(
    case: Case, model: ApprovingModel | ExplodingModel
) -> tuple[World, dict[str, Verdict], ReportStatus]:
    world = build_world()
    verifier = IndependentVerifier(source_store=world.sources, case_store=world.cases, model=model)
    report = verifier.verify_outline(case.build(world))
    return world, {i.item_id: i.verdict for i in report.items}, report.status


@pytest.mark.parametrize("case", ALL_CASES, ids=lambda c: c.name)
def test_bad_citation_is_never_supported_even_by_a_yes_man_model(case: Case) -> None:
    model = ApprovingModel()
    _, verdicts, status = _run(case, model)
    assert verdicts[case.item_id] is case.expected
    assert Verdict.SUPPORTED not in verdicts.values()
    assert status is ReportStatus.FAIL
    assert model.calls == [], "Phase A failure must be decisive: the model must not be consulted"


@pytest.mark.parametrize("case", ALL_CASES, ids=lambda c: c.name)
def test_phase_a_makes_no_model_call(case: Case) -> None:
    model = ExplodingModel()
    _, verdicts, _ = _run(case, model)
    assert model.calls == []
    assert verdicts[case.item_id] is case.expected


def test_zero_false_supported_over_whole_adversarial_set() -> None:
    false_supported = []
    for case in ALL_CASES:
        _, verdicts, status = _run(case, ApprovingModel())
        if verdicts[case.item_id] is Verdict.SUPPORTED or status is ReportStatus.PASS:
            false_supported.append(case.name)
    assert len(ALL_CASES) >= 40
    assert false_supported == []


def test_bad_items_fail_while_good_items_pass_in_one_outline() -> None:
    world = build_world()
    e1, e2 = good_elements(world)
    l1, l2 = good_links(world)
    bad = [
        element("e3", "SYNTHETIC", altered(world, L, ACT, "v2025", ART1, ART1_QUOTE, "，", ",")),
        element("e4", "SYNTHETIC", law_cite(world, ACT, "v2020", OLD_ART1, "应当赔偿对方损失")),
        element("e5", "SYNTHETIC", law_cite(world, "zz-b-contract-act", "v1", ART1, ART1_QUOTE)),
    ]
    bad_link = link(
        "l3", "e1", case_cite(world, OTHER_EMAIL, EMAIL_SENTENCE, EMAIL_QUOTE), "证明乙方无法交付"
    )
    model = ApprovingModel()
    verifier = IndependentVerifier(source_store=world.sources, case_store=world.cases, model=model)
    report = verifier.verify_outline(outline(world, (e1, e2, *bad), (l1, l2, bad_link)))
    verdicts = {i.item_id: i.verdict for i in report.items}
    assert [i.item_id for i in report.items] == ["e1", "e2", "e3", "e4", "e5", "l1", "l2", "l3"]
    assert verdicts == {
        "e1": Verdict.SUPPORTED,
        "e2": Verdict.SUPPORTED,
        "e3": CI,
        "e4": Verdict.NOT_IN_FORCE,
        "e5": Verdict.WRONG_JURISDICTION,
        "l1": Verdict.SUPPORTED,
        "l2": Verdict.SUPPORTED,
        "l3": CI,
    }
    assert report.status is ReportStatus.FAIL
    assert len(model.calls) == 4  # only the four good items reached Phase B


def test_normalization_cases_really_are_normalization_equal() -> None:
    """Guards the suite itself: these alterations would pass a verifier that normalized text."""
    assert unicodedata.normalize("NFC", "违约\uf90a") == "违约金"
    assert unicodedata.normalize("NFKC", "第\u2f00条") == "第一条"
    assert unicodedata.normalize("NFKC", "１０，０００") == "10,000"
    assert unicodedata.normalize("NFKC", "\u3000") == " "


def test_text_of_another_case_is_never_read() -> None:
    case = next(c for c in EVIDENCE_CASES if c.name == "evidence_from_another_case")
    world, verdicts, _ = _run(case, ApprovingModel())
    assert verdicts["l1"] is CI
    assert all(read[0] != OTHER_EMAIL for read in world.cases.text_reads)


def test_correct_code_point_offsets_after_non_bmp_char_pass_phase_a() -> None:
    world = build_world()
    model = ApprovingModel()
    verifier = IndependentVerifier(source_store=world.sources, case_store=world.cases, model=model)
    el = element("e1", "当事人应当对其主张提供证据", law_cite(world, RULES, "v1", RULES_ART1, "应当提供证据"))
    report = verifier.verify_outline(outline(world, (el,)))
    assert report.items[0].verdict is Verdict.SUPPORTED
    assert report.status is ReportStatus.PASS
    assert len(model.calls) == 1


def test_contract_link_of_contract_document_on_page_two_resolves() -> None:
    """A correct citation on page 2 of a case file (full-width digits kept) passes Phase A."""
    world = build_world()
    model = ApprovingModel()
    verifier = IndependentVerifier(source_store=world.sources, case_store=world.cases, model=model)
    e1, _ = good_elements(world)
    lk = link(
        "l1",
        "e1",
        case_cite(world, CONTRACT, "违约金ZZ币１０，０００元", "ZZ币１０，０００元"),
        "证明约定了违约金",
    )
    report = verifier.verify_outline(outline(world, (e1,), (lk,)))
    assert [i.verdict for i in report.items] == [Verdict.SUPPORTED, Verdict.SUPPORTED]


SPAN_TEXT = "phase_a:span_text"
EXPECTED_CHECK = {
    "fabricated_doc_id": "phase_a:resolve",
    "fabricated_version_id": "phase_a:resolve",
    "altered_quote_and_span": SPAN_TEXT,
    "altered_quote_bypassing_contract": "phase_a:quote_verbatim",
    "altered_span_text_bypassing_contract": SPAN_TEXT,
    "shifted_offsets_plus_one": SPAN_TEXT,
    "shifted_offsets_minus_one": SPAN_TEXT,
    "utf16_offsets_after_non_bmp_char": SPAN_TEXT,
    "offsets_beyond_document_end": "phase_a:offsets",
    "outdated_version": "phase_a:in_force",
    "outdated_quote_against_current_version": SPAN_TEXT,
    "future_version": "phase_a:in_force",
    "expires_exactly_on_as_of": "phase_a:in_force",
    "wrong_jurisdiction": "phase_a:jurisdiction",
    "secondary_source_as_law": "phase_a:doc_type",
    "case_file_cited_as_legal_basis": "phase_a:source_kind",
    "empty_legal_basis": "phase_a:no_citation",
    "blank_quote_ideographic_space": "phase_a:quote_empty",
    "one_bad_citation_among_good": "phase_a:resolve",
    "cn_halfwidth_comma": SPAN_TEXT,
    "cn_halfwidth_full_stop": SPAN_TEXT,
    "cn_ascii_double_quotes": SPAN_TEXT,
    "cn_corner_brackets_for_curly_quotes": SPAN_TEXT,
    "cn_ascii_space_for_ideographic_space": SPAN_TEXT,
    "cn_kangxi_radical_one_nfkc_equal": SPAN_TEXT,
    "cn_compatibility_ideograph_nfc_equal": SPAN_TEXT,
    "cn_traditional_for_simplified": SPAN_TEXT,
    "cn_zero_width_space_inserted": SPAN_TEXT,
    "cn_bom_prefixed": SPAN_TEXT,
    "en_no_break_space": SPAN_TEXT,
    "evidence_from_another_case": "phase_a:case_membership",
    "fabricated_case_doc_id": "phase_a:resolve",
    "fabricated_case_version": "phase_a:resolve",
    "evidence_fullwidth_digits_to_ascii": SPAN_TEXT,
    "evidence_curly_quotes_dropped": SPAN_TEXT,
    "evidence_altered_fact": SPAN_TEXT,
    "evidence_shifted_offsets": SPAN_TEXT,
    "evidence_offsets_beyond_end": "phase_a:offsets",
    "law_span_cited_as_evidence": "phase_a:source_kind",
    "evidence_quote_bypassing_contract": "phase_a:quote_verbatim",
    "evidence_blank_quote": "phase_a:quote_empty",
}


@pytest.mark.parametrize("case", ALL_CASES, ids=lambda c: c.name)
def test_each_case_fails_at_the_intended_check(case: Case) -> None:
    world = build_world()
    verifier = IndependentVerifier(source_store=world.sources, case_store=world.cases, model=ApprovingModel())
    report = verifier.verify_outline(case.build(world))
    item = next(i for i in report.items if i.item_id == case.item_id)
    assert item.method == EXPECTED_CHECK[case.name]


def test_case_file_mismatch_rationale_does_not_leak_characters() -> None:
    """P9: a mismatch in a confidential case file is reported by position only."""
    case = next(c for c in EVIDENCE_CASES if c.name == "evidence_altered_fact")
    world = build_world()
    verifier = IndependentVerifier(source_store=world.sources, case_store=world.cases, model=ApprovingModel())
    item = next(i for i in verifier.verify_outline(case.build(world)).items if i.item_id == "l1")
    assert "U+" not in item.rationale
    assert "无法" not in item.rationale and "可以" not in item.rationale
