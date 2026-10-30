"""Metric primitives: independent citation checks, element/link/gap matching and retrieval recall.

Evaluation measures independently of verification (P2, P6): citation checks here re-read the stores directly.

Matching rules (documented so scores are reproducible):
- A citation's *quote range* is `(doc_id, version_id, start, end)` of the first occurrence of the quote in
  its span.
- A produced element matches an expected element if any of their legal-basis quote ranges overlap. Matching is
  one-to-one (maximum bipartite matching, deterministic order).
- A produced link matches an expected link if their elements are matched to each other, the relation is
  equal and their quote ranges overlap. Also one-to-one.
- For each matched element pair, correct gaps = min(produced gaps, expected gaps) on that pair.
"""

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass

from legalai_contracts import (
    CaseFileStore,
    Citation,
    EvidenceOutline,
    LegalQuery,
    SourceKind,
    SourceSpan,
    SourceStore,
)


@dataclass(frozen=True, order=True)
class QuoteRange:
    doc_id: str
    version_id: str
    start: int
    end: int

    def overlaps(self, other: "QuoteRange") -> bool:
        return (
            self.doc_id == other.doc_id
            and self.version_id == other.version_id
            and self.start < other.end
            and other.start < self.end
        )

    def within(self, span: SourceSpan) -> bool:
        return (
            self.doc_id == span.doc_id
            and self.version_id == span.version_id
            and span.start_char <= self.start
            and self.end <= span.end_char
        )


def quote_range(citation: Citation) -> QuoteRange:
    """Absolute character range of the quoted words (first occurrence inside the span)."""
    start = citation.span.start_char + citation.span.text.find(citation.quote)
    return QuoteRange(citation.span.doc_id, citation.span.version_id, start, start + len(citation.quote))


@dataclass(frozen=True)
class CitationCheck:
    """Evaluation's own check of one citation against the stores.

    - `resolvable`: the document version exists in the store for its `SourceKind` and the stored text at the
      offsets equals the span text.
    - `quote_matches`: the quote occurs verbatim in the stored text at the offsets.
    - `in_scope`: resolvable, and law is in the query jurisdiction and in force on `as_of`, or a case file
      belongs to the query's case.
    """

    resolvable: bool
    quote_matches: bool
    in_scope: bool


def check_citation(
    citation: Citation, query: LegalQuery, source_store: SourceStore, case_file_store: CaseFileStore
) -> CitationCheck:
    span = citation.span
    try:
        if span.source is SourceKind.LAW:
            law = source_store.get_document(span.doc_id, span.version_id)
            stored = source_store.get_text(span.doc_id, span.version_id, span.start_char, span.end_char)
            scope = law.jurisdiction == query.jurisdiction and law.in_force_on(query.as_of)
        else:
            case_doc = case_file_store.get_document(span.doc_id, span.version_id)
            stored = case_file_store.get_text(span.doc_id, span.version_id, span.start_char, span.end_char)
            scope = case_doc.case_id == query.case_id
    except (LookupError, ValueError):
        # Store contract: unknown documents raise LookupError, bad offsets raise ValueError. Both mean the
        # citation does not resolve; any other exception propagates and stops the run.
        return CitationCheck(resolvable=False, quote_matches=False, in_scope=False)
    resolvable = stored == span.text
    return CitationCheck(
        resolvable=resolvable, quote_matches=citation.quote in stored, in_scope=resolvable and scope
    )


def outline_citations(outline: EvidenceOutline) -> list[Citation]:
    """Every citation an outline relies on: element legal bases, then evidence links."""
    if outline.abstained:
        return []
    return [c for e in outline.elements for c in e.legal_basis] + [link.citation for link in outline.links]


def max_matching(n_left: int, n_right: int, compatible: Callable[[int, int], bool]) -> dict[int, int]:
    """Maximum bipartite matching (Kuhn's algorithm). Returns left index -> right index. Deterministic."""
    edges = [[r for r in range(n_right) if compatible(left, r)] for left in range(n_left)]
    right_to_left: dict[int, int] = {}

    def augment(left: int, seen: set[int]) -> bool:
        for r in edges[left]:
            if r in seen:
                continue
            seen.add(r)
            if r not in right_to_left or augment(right_to_left[r], seen):
                right_to_left[r] = left
                return True
        return False

    for left in range(n_left):
        augment(left, set())
    return {left: r for r, left in right_to_left.items()}


@dataclass(frozen=True)
class OutlineScore:
    """Counts comparing one produced outline with one expected outline."""

    expected_elements: int
    produced_elements: int
    matched_elements: int
    expected_links: int
    produced_links: int
    matched_links: int
    expected_gaps: int
    produced_gaps: int
    matched_gaps: int
    gap_kind_agreements: int


def score_outline(expected: EvidenceOutline, produced: EvidenceOutline | None) -> OutlineScore:
    """Compare a produced outline (None = nothing usable produced) with the expected outline.

    Abstaining outlines contribute no elements, links or gaps on either side.
    """
    exp_elements = () if expected.abstained else expected.elements
    exp_links = () if expected.abstained else expected.links
    exp_gaps = () if expected.abstained else expected.gaps
    usable = produced is not None and not produced.abstained
    prod_elements = produced.elements if usable and produced is not None else ()
    prod_links = produced.links if usable and produced is not None else ()
    prod_gaps = produced.gaps if usable and produced is not None else ()

    exp_ranges = [[quote_range(c) for c in e.legal_basis] for e in exp_elements]
    prod_ranges = [[quote_range(c) for c in e.legal_basis] for e in prod_elements]
    element_match = max_matching(
        len(exp_elements),
        len(prod_elements),
        lambda i, j: any(a.overlaps(b) for a in exp_ranges[i] for b in prod_ranges[j]),
    )
    exp_to_prod_id = {
        exp_elements[i].element_id: prod_elements[j].element_id for i, j in element_match.items()
    }

    link_match = max_matching(
        len(exp_links),
        len(prod_links),
        lambda i, j: (
            exp_to_prod_id.get(exp_links[i].element_id) == prod_links[j].element_id
            and exp_links[i].relation is prod_links[j].relation
            and quote_range(exp_links[i].citation).overlaps(quote_range(prod_links[j].citation))
        ),
    )

    matched_gaps = 0
    kind_agreements = 0
    for exp_id, prod_id in exp_to_prod_id.items():
        e_gaps = [g for g in exp_gaps if g.element_id == exp_id]
        p_gaps = [g for g in prod_gaps if g.element_id == prod_id]
        matched_gaps += min(len(e_gaps), len(p_gaps))
        if e_gaps and p_gaps and any(p.kind is e.kind for p in p_gaps for e in e_gaps):
            kind_agreements += 1

    return OutlineScore(
        expected_elements=len(exp_elements),
        produced_elements=len(prod_elements),
        matched_elements=len(element_match),
        expected_links=len(exp_links),
        produced_links=len(prod_links),
        matched_links=len(link_match),
        expected_gaps=len(exp_gaps),
        produced_gaps=len(prod_gaps),
        matched_gaps=matched_gaps,
        gap_kind_agreements=kind_agreements,
    )


def recall_hits(targets: Iterable[QuoteRange], retrieved: Sequence[SourceSpan]) -> tuple[int, int]:
    """(number of distinct targets, number of them contained in at least one retrieved span)."""
    unique = sorted(set(targets))
    hits = sum(1 for t in unique if any(t.within(span) for span in retrieved))
    return len(unique), hits


def law_targets(expected: EvidenceOutline) -> list[QuoteRange]:
    if expected.abstained:
        return []
    return [quote_range(c) for e in expected.elements for c in e.legal_basis]


def evidence_targets(expected: EvidenceOutline, element_id: str) -> list[QuoteRange]:
    if expected.abstained:
        return []
    return [quote_range(link.citation) for link in expected.links if link.element_id == element_id]
