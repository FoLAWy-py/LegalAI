from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from legalai_contracts import (
    CaseDocument,
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

LAW = "SYNTHETIC Contract Act art.1: A party who fails to perform shall be liable."
EVIDENCE = "SYNTHETIC email: We will not deliver the goods."


def cite(source: SourceKind, text: str, quote: str) -> Citation:
    span = SourceSpan(source=source, doc_id="d", version_id="v", start_char=0, end_char=len(text), text=text)
    return Citation(span=span, quote=quote)


def query() -> LegalQuery:
    return LegalQuery(
        query_id="q1",
        text="Seller refused delivery.",
        jurisdiction="ZZ",
        as_of=date(2026, 1, 1),
        response_language="zh-CN",
        task_type=TaskType.EVIDENCE_OUTLINE,
        case_id="case-1",
        party_role=PartyRole.PLAINTIFF,
    )


def element(element_id: str) -> Element:
    return Element(
        element_id=element_id,
        description="Defendant failed to perform.",
        legal_basis=(cite(SourceKind.LAW, LAW, "fails to perform"),),
        burden_on=PartyRole.PLAINTIFF,
    )


def link(element_id: str = "e1") -> EvidenceLink:
    return EvidenceLink(
        link_id="l1",
        element_id=element_id,
        citation=cite(SourceKind.CASE_FILE, EVIDENCE, "will not deliver"),
        relation=EvidenceRelation.SUPPORTS,
        purpose="Shows refusal to perform.",
    )


def outline(**kw: object) -> EvidenceOutline:
    args: dict[str, object] = {
        "query": query(),
        "cause_of_action": "breach of contract",
        "elements": (element("e1"), element("e2")),
        "links": (link(),),
        "gaps": (Gap(element_id="e2", kind=GapKind.NO_EVIDENCE, description="No proof of loss."),),
        "traces": (ModelTrace(model="t", prompt_id="p", prompt_version="1", temperature=0),),
    }
    args.update(kw)
    return EvidenceOutline.model_validate(args)


def test_outline_query_needs_case_and_role() -> None:
    with pytest.raises(ValidationError, match="case_id"):
        LegalQuery(
            query_id="q",
            text="t",
            jurisdiction="ZZ",
            as_of=date(2026, 1, 1),
            response_language="en",
            task_type=TaskType.EVIDENCE_OUTLINE,
        )


def test_element_must_cite_law() -> None:
    with pytest.raises(ValidationError, match="law"):
        Element(element_id="e", description="x", legal_basis=(cite(SourceKind.CASE_FILE, EVIDENCE, "goods"),))


def test_link_must_cite_case_file() -> None:
    with pytest.raises(ValidationError, match="case file"):
        EvidenceLink(
            link_id="l",
            element_id="e1",
            citation=cite(SourceKind.LAW, LAW, "liable"),
            relation=EvidenceRelation.SUPPORTS,
            purpose="x",
        )


def test_valid_outline() -> None:
    assert len(outline().elements) == 2


def test_every_element_needs_evidence_or_gap() -> None:
    with pytest.raises(ValidationError, match="without supporting evidence or gap"):
        outline(gaps=())


def test_contradicting_link_alone_does_not_cover_element() -> None:
    contra = link().model_copy(update={"relation": EvidenceRelation.CONTRADICTS})
    with pytest.raises(ValidationError, match="e1"):
        outline(links=(contra,))


def test_link_to_unknown_element_rejected() -> None:
    with pytest.raises(ValidationError, match="unknown elements"):
        outline(links=(link("e9"),))


def test_case_document_pages() -> None:
    doc = CaseDocument(
        case_id="c",
        doc_id="d",
        version_id="v",
        title="SYNTHETIC contract",
        language="zh-CN",
        media_type="application/pdf",
        received_at=datetime(2026, 1, 1, tzinfo=UTC),
        content_sha256="0" * 64,
        char_count=300,
        page_starts=(0, 100, 200),
    )
    assert (doc.page_of(0), doc.page_of(150), doc.page_of(299)) == (1, 2, 3)


def test_case_document_rejects_bad_pages() -> None:
    with pytest.raises(ValidationError):
        CaseDocument(
            case_id="c",
            doc_id="d",
            version_id="v",
            title="t",
            language="en",
            media_type="text/plain",
            received_at=datetime(2026, 1, 1, tzinfo=UTC),
            content_sha256="0" * 64,
            char_count=50,
            page_starts=(0, 60),
        )
