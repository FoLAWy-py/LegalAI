"""Adversarial citation set: each item is a correct expected outline with exactly one bad citation."""

from collections.abc import Callable, Sequence

from legalai_contracts import Citation, Element, EvidenceLink, EvidenceOutline, SourceSpan

from legalai_evaluation.dataset import AdversarialItem, AdversarialKind, EvalCase
from legalai_evaluation.synthetic._authoring import CaseFile
from legalai_evaluation.synthetic._law import NP_ORDINANCE, LawLibrary

FABRICATED_LAW_DOC_ID = "zz-fabricated-code"
FABRICATED_CASE_DOC_ID = "zz-fabricated-exhibit"


def _with_element(outline: EvidenceOutline, element: Element) -> EvidenceOutline:
    elements = tuple(element if e.element_id == element.element_id else e for e in outline.elements)
    return EvidenceOutline(
        query=outline.query,
        cause_of_action=outline.cause_of_action,
        elements=elements,
        links=outline.links,
        gaps=outline.gaps,
        traces=outline.traces,
    )


def _with_link(outline: EvidenceOutline, link: EvidenceLink) -> EvidenceOutline:
    links = tuple(link if x.link_id == link.link_id else x for x in outline.links)
    return EvidenceOutline(
        query=outline.query,
        cause_of_action=outline.cause_of_action,
        elements=outline.elements,
        links=links,
        gaps=outline.gaps,
        traces=outline.traces,
    )


def _respan(span: SourceSpan, **changes: object) -> SourceSpan:
    return SourceSpan.model_validate({**span.model_dump(), **changes})


def _alter_quote(citation: Citation) -> Citation:
    """Change one character inside the quoted words, in both span text and quote (lengths unchanged)."""
    offset = citation.span.text.find(citation.quote)
    index = offset + len(citation.quote) // 2
    original = citation.span.text[index]
    replacement = "X" if original != "X" else "Y"
    text = citation.span.text[:index] + replacement + citation.span.text[index + 1 :]
    quote = text[offset : offset + len(citation.quote)]
    return Citation(span=_respan(citation.span, text=text), quote=quote)


def _first_element_citation(
    outline: EvidenceOutline, transform: Callable[[Citation], Citation | None]
) -> tuple[Element, Citation] | None:
    for element in outline.elements:
        for i, citation in enumerate(element.legal_basis):
            replaced = transform(citation)
            if replaced is not None:
                basis = element.legal_basis[:i] + (replaced,) + element.legal_basis[i + 1 :]
                return element.model_copy(update={"legal_basis": basis}), citation
    return None


def build_adversarial_set(
    cases: Sequence[EvalCase], law: LawLibrary, files: Sequence[CaseFile]
) -> list[AdversarialItem]:
    """One item per (non-abstaining case, applicable kind), in case order then `AdversarialKind` order."""
    np_article = law.get(NP_ORDINANCE, "2019").cite("Article 2", "intentionally causes a public disturbance")
    items: list[AdversarialItem] = []

    for case in cases:
        outline = case.expected
        if outline.abstained:
            continue
        as_of = case.query.as_of

        def not_in_force(c: Citation, as_of_day: object = as_of) -> Citation | None:
            for other in law.versions(c.span.doc_id):
                if other.document.version_id == c.span.version_id or other.document.in_force_on(as_of):
                    continue
                pinpoint = c.span.pinpoint or ""
                if pinpoint in other.articles and c.quote in other.articles[pinpoint].text:
                    return other.cite(pinpoint, c.quote)
            return None

        element_mutations: list[tuple[AdversarialKind, Callable[[Citation], Citation | None], str]] = [
            (
                AdversarialKind.FABRICATED_LAW_DOCUMENT,
                lambda c: Citation(span=_respan(c.span, doc_id=FABRICATED_LAW_DOC_ID), quote=c.quote),
                "legal basis cites a law document that does not exist",
            ),
            (AdversarialKind.ALTERED_LAW_QUOTE, _alter_quote, "legal-basis quote altered by one character"),
            (
                AdversarialKind.SHIFTED_LAW_OFFSETS,
                lambda c: Citation(
                    span=_respan(c.span, start_char=c.span.start_char + 1, end_char=c.span.end_char + 1),
                    quote=c.quote,
                ),
                "legal-basis offsets shifted by one character, text unchanged",
            ),
            (
                AdversarialKind.VERSION_NOT_IN_FORCE,
                not_in_force,
                "legal basis cites a version of the same provision not in force on as_of",
            ),
            (
                AdversarialKind.WRONG_JURISDICTION,
                lambda c: np_article,
                "legal basis cites a provision of jurisdiction ZZ-NP for a ZZ query",
            ),
        ]
        for kind, transform, description in element_mutations:
            found = _first_element_citation(outline, transform)
            if found is None:
                continue
            element, _ = found
            items.append(
                AdversarialItem(
                    item_id=f"{case.case_id}:{kind.value}",
                    kind=kind,
                    base_case_id=case.case_id,
                    target_item_id=element.element_id,
                    outline=_with_element(outline, element),
                    description=description,
                )
            )

        link = outline.links[0]
        other_file = next(f for f in files if f.document.case_id != case.query.case_id)
        other_passage = other_file.passages[1]
        link_mutations: list[tuple[AdversarialKind, Citation, str]] = [
            (
                AdversarialKind.FABRICATED_CASE_DOCUMENT,
                Citation(span=_respan(link.citation.span, doc_id=FABRICATED_CASE_DOC_ID), quote=link.citation.quote),
                "evidence link cites a case document that does not exist",
            ),
            (AdversarialKind.ALTERED_EVIDENCE_QUOTE, _alter_quote(link.citation), "evidence quote altered by one character"),
            (
                AdversarialKind.EVIDENCE_FROM_OTHER_CASE,
                Citation(span=other_passage, quote=other_passage.text),
                f"evidence link cites a real passage from another case ({other_file.document.case_id})",
            ),
        ]
        for kind, citation, description in link_mutations:
            items.append(
                AdversarialItem(
                    item_id=f"{case.case_id}:{kind.value}",
                    kind=kind,
                    base_case_id=case.case_id,
                    target_item_id=link.link_id,
                    outline=_with_link(outline, link.model_copy(update={"citation": citation})),
                    description=description,
                )
            )
    return items
