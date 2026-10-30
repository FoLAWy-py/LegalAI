"""Metric primitives on tiny hand-built `ZZ` examples. Every expected number here is computed by hand."""

from datetime import date

from legalai_contracts import (
    Citation,
    Element,
    EvidenceLink,
    EvidenceOutline,
    EvidenceRelation,
    Gap,
    GapKind,
    LegalQuery,
    ModelTrace,
    PartyRole,
    SourceKind,
    SourceSpan,
    TaskType,
)
from legalai_evaluation.metrics import QuoteRange, max_matching, quote_range, recall_hits, score_outline

LAW = "SYNTHETIC ZZ art.7: Whoever takes property of another without consent commits taking."
# Offsets by hand: "takes" starts at 28, "without consent" at 54.
CASE = "SYNTHETIC record: the bicycle was in the shed. The owner gave no permission."
# "the bicycle was in the shed" starts at 18; "The owner gave no permission" at 47.

QUERY = LegalQuery(
    query_id="q-mini",
    text="SYNTHETIC mini case",
    jurisdiction="ZZ",
    as_of=date(2024, 1, 1),
    response_language="en",
    task_type=TaskType.EVIDENCE_OUTLINE,
    case_id="zz-mini",
    party_role=PartyRole.PROSECUTION,
)
TRACE = (ModelTrace(model="test", prompt_id="test", prompt_version="0", temperature=0),)


def law(quote: str) -> Citation:
    span = SourceSpan(
        source=SourceKind.LAW, doc_id="zz-law", version_id="v1", start_char=0, end_char=len(LAW), text=LAW
    )
    return Citation(span=span, quote=quote)


def case(quote: str) -> Citation:
    span = SourceSpan(
        source=SourceKind.CASE_FILE,
        doc_id="zz-file",
        version_id="v1",
        start_char=0,
        end_char=len(CASE),
        text=CASE,
    )
    return Citation(span=span, quote=quote)


def outline(elements: list[Element], links: list[EvidenceLink], gaps: list[Gap]) -> EvidenceOutline:
    return EvidenceOutline(
        query=QUERY,
        cause_of_action="Taking (SYNTHETIC)",
        elements=tuple(elements),
        links=tuple(links),
        gaps=tuple(gaps),
        traces=TRACE,
    )


def test_hand_offsets_are_right() -> None:
    assert LAW.find("takes") == 28
    assert LAW.find("without consent") == 54
    assert CASE.find("the bicycle was in the shed") == 18
    assert CASE.find("The owner gave no permission") == 47


def test_quote_range_is_absolute() -> None:
    span = SourceSpan(
        source=SourceKind.LAW, doc_id="d", version_id="v", start_char=100, end_char=111, text="abc quote x"
    )
    assert quote_range(Citation(span=span, quote="quote")) == QuoteRange("d", "v", 104, 109)


def test_overlap_and_containment() -> None:
    a = QuoteRange("d", "v", 10, 20)
    assert a.overlaps(QuoteRange("d", "v", 19, 30))
    assert not a.overlaps(QuoteRange("d", "v", 20, 30))  # end is exclusive
    assert not a.overlaps(QuoteRange("d", "v2", 10, 20))  # other version
    span = SourceSpan(
        source=SourceKind.LAW, doc_id="d", version_id="v", start_char=5, end_char=20, text="x" * 15
    )
    assert a.within(span)
    assert not QuoteRange("d", "v", 4, 10).within(span)


def test_max_matching_beats_greedy() -> None:
    # Greedy would give left0 -> right0 and leave left1 unmatched; the maximum matching is 2.
    compatible = {(0, 0), (0, 1), (1, 0)}
    assert max_matching(2, 2, lambda i, j: (i, j) in compatible) == {0: 1, 1: 0}


def expected_outline() -> EvidenceOutline:
    return outline(
        [
            Element(element_id="E1", description="took property", legal_basis=(law("takes"),)),
            Element(element_id="E2", description="without consent", legal_basis=(law("without consent"),)),
        ],
        [
            EvidenceLink(
                link_id="L1",
                element_id="E1",
                citation=case("the bicycle was in the shed"),
                relation=EvidenceRelation.SUPPORTS,
                purpose="Where the bicycle was found.",
            ),
        ],
        [Gap(element_id="E2", kind=GapKind.NO_EVIDENCE, description="No evidence on consent.")],
    )


def test_perfect_outline_scores_full() -> None:
    s = score_outline(expected_outline(), expected_outline())
    assert (s.expected_elements, s.produced_elements, s.matched_elements) == (2, 2, 2)
    assert (s.expected_links, s.produced_links, s.matched_links) == (1, 1, 1)
    assert (s.expected_gaps, s.produced_gaps, s.matched_gaps, s.gap_kind_agreements) == (1, 1, 1, 1)


def test_partially_wrong_outline_hand_computed() -> None:
    produced = outline(
        [
            # Cites the whole sentence: overlaps both E1 and E2 anchors.
            Element(
                element_id="P-a",
                description="whole rule",
                legal_basis=(law("Whoever takes property of another without consent commits taking."),),
            ),
            Element(element_id="P-b", description="consent", legal_basis=(law("without consent"),)),
            # Cites the article heading only: matches nothing.
            Element(element_id="P-c", description="heading", legal_basis=(law("SYNTHETIC ZZ art.7"),)),
        ],
        [
            # Right element and passage: correct.
            EvidenceLink(
                link_id="M1",
                element_id="P-a",
                citation=case("bicycle was in the shed"),
                relation=EvidenceRelation.SUPPORTS,
                purpose="Where the bicycle was found.",
            ),
            # Same passage, wrong relation: incorrect.
            EvidenceLink(
                link_id="M2",
                element_id="P-a",
                citation=case("the bicycle"),
                relation=EvidenceRelation.CONTRADICTS,
                purpose="Where the bicycle was found.",
            ),
            # Passage not in the expected outline: incorrect.
            EvidenceLink(
                link_id="M3",
                element_id="P-c",
                citation=case("The owner gave no permission"),
                relation=EvidenceRelation.SUPPORTS,
                purpose="The owner's position.",
            ),
        ],
        [
            Gap(element_id="P-b", kind=GapKind.INSUFFICIENT, description="Weak."),  # real gap, other kind
            Gap(element_id="P-a", kind=GapKind.NO_EVIDENCE, description="Spurious."),  # E1 has no gap
        ],
    )
    s = score_outline(expected_outline(), produced)
    # Elements: P-a <-> E1, P-b <-> E2; P-c unmatched. Recall 2/2, precision 2/3.
    assert (s.expected_elements, s.produced_elements, s.matched_elements) == (2, 3, 2)
    # Links: only M1 matches L1. Precision 1/3, recall 1/1.
    assert (s.expected_links, s.produced_links, s.matched_links) == (1, 3, 1)
    # Gaps: P-b's gap matches E2's (kind differs); P-a's gap is spurious. Precision 1/2, recall 1/1, kind 0.
    assert (s.expected_gaps, s.produced_gaps, s.matched_gaps, s.gap_kind_agreements) == (1, 2, 1, 0)


def test_abstaining_or_missing_outline_scores_nothing_produced() -> None:
    for produced in (
        None,
        EvidenceOutline(query=QUERY, cause_of_action="", abstained=True, abstain_reason="x", traces=TRACE),
    ):
        s = score_outline(expected_outline(), produced)
        assert (s.produced_elements, s.matched_elements, s.produced_links, s.produced_gaps) == (0, 0, 0, 0)
        assert (s.expected_elements, s.expected_links, s.expected_gaps) == (2, 1, 1)


def test_recall_hits_counts_distinct_targets() -> None:
    targets = [QuoteRange("d", "v", 10, 15), QuoteRange("d", "v", 10, 15), QuoteRange("d", "v", 40, 45)]
    span = SourceSpan(
        source=SourceKind.LAW, doc_id="d", version_id="v", start_char=0, end_char=20, text="x" * 20
    )
    assert recall_hits(targets, [span]) == (2, 1)
    assert recall_hits(targets, []) == (2, 0)
