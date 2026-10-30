"""Criminal evidence outlines on synthetic `ZZ` data (ADR-0006, REQ-PMO-0007).

All law and case text here is fictional (jurisdiction `ZZ`, marker SYNTHETIC).
It states nothing about real law.
"""

from datetime import date

import pytest
from pydantic import ValidationError

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

PENAL = (
    "SYNTHETIC ZZ Penal Code art.7: Whoever takes the movable property of another without consent, "
    "intending to keep it, commits taking. The prosecutor bears the burden of proving each element."
)
DEFENCE_LAW = "SYNTHETIC ZZ Penal Code art.9: An act done with the owner's consent is not taking."
INSPECTION = "SYNTHETIC inspection record: the bicycle was found in the accused's shed."
WITNESS = "SYNTHETIC witness statement: the owner said the accused could borrow the bicycle."


def cite(source: SourceKind, doc_id: str, text: str, quote: str) -> Citation:
    span = SourceSpan(
        source=source, doc_id=doc_id, version_id="v1", start_char=0, end_char=len(text), text=text
    )
    return Citation(span=span, quote=quote)


def criminal_query(role: PartyRole = PartyRole.PROSECUTION) -> LegalQuery:
    return LegalQuery(
        query_id="q-crim-1",
        text="SYNTHETIC: the accused is charged with taking a bicycle.",
        jurisdiction="ZZ",
        as_of=date(2026, 1, 1),
        response_language="en",
        task_type=TaskType.EVIDENCE_OUTLINE,
        case_id="zz-crim-case-1",
        party_role=role,
    )


def offence_element(element_id: str, description: str, quote: str) -> Element:
    return Element(
        element_id=element_id,
        description=description,
        legal_basis=(cite(SourceKind.LAW, "zz-penal-code", PENAL, quote),),
        # Set only because the cited synthetic provision itself states who bears the burden.
        burden_on=PartyRole.PROSECUTION,
    )


def elements() -> tuple[Element, ...]:
    return (
        offence_element(
            "e-taking", "The accused took movable property of another.", "takes the movable property"
        ),
        offence_element("e-consent", "The taking was without the owner's consent.", "without consent"),
        offence_element("e-intent", "The accused intended to keep the property.", "intending to keep it"),
    )


def supports_taking() -> EvidenceLink:
    return EvidenceLink(
        link_id="l-inspection",
        element_id="e-taking",
        citation=cite(SourceKind.CASE_FILE, "zz-case-inspection", INSPECTION, "found in the accused's shed"),
        relation=EvidenceRelation.SUPPORTS,
        purpose="Shows the property was in the accused's possession.",
    )


def defence_link() -> EvidenceLink:
    """A defence is a CONTRADICTS link on the element it would negate (ADR-0006)."""
    return EvidenceLink(
        link_id="l-witness-consent",
        element_id="e-consent",
        citation=cite(
            SourceKind.CASE_FILE, "zz-case-witness", WITNESS, "the accused could borrow the bicycle"
        ),
        relation=EvidenceRelation.CONTRADICTS,
        purpose="Witness reports the owner allowed the accused to borrow the bicycle.",
    )


def criminal_outline(**kw: object) -> EvidenceOutline:
    args: dict[str, object] = {
        "query": criminal_query(),
        "cause_of_action": "SYNTHETIC ZZ Penal Code art.7 taking",
        "elements": elements(),
        "links": (supports_taking(), defence_link()),
        "gaps": (
            Gap(
                element_id="e-consent",
                kind=GapKind.ONLY_CONTRADICTING,
                description="Only evidence on consent contradicts the element.",
            ),
            Gap(
                element_id="e-intent", kind=GapKind.NO_EVIDENCE, description="No evidence of intent to keep."
            ),
        ),
        "traces": (ModelTrace(model="t", prompt_id="p", prompt_version="1", temperature=0),),
    }
    args.update(kw)
    return EvidenceOutline.model_validate(args)


def test_existing_party_role_values_unchanged() -> None:
    assert PartyRole.PLAINTIFF.value == "plaintiff"
    assert PartyRole.DEFENDANT.value == "defendant"
    assert PartyRole.PROSECUTION.value == "prosecution"


def test_valid_criminal_outline_with_prosecution_role() -> None:
    result = criminal_outline()
    assert result.query.party_role is PartyRole.PROSECUTION
    assert {e.burden_on for e in result.elements} == {PartyRole.PROSECUTION}
    assert [link.relation for link in result.links] == [
        EvidenceRelation.SUPPORTS,
        EvidenceRelation.CONTRADICTS,
    ]


def test_criminal_outline_for_the_defence() -> None:
    assert criminal_outline(query=criminal_query(PartyRole.DEFENDANT)).query.party_role is PartyRole.DEFENDANT


def test_prosecution_role_round_trips_through_json() -> None:
    original = criminal_outline()
    restored = EvidenceOutline.model_validate_json(original.model_dump_json())
    assert restored == original
    assert '"party_role":"prosecution"' in original.model_dump_json()


def test_defence_evidence_alone_does_not_cover_element() -> None:
    gaps_without_consent = tuple(g for g in criminal_outline().gaps if g.element_id != "e-consent")
    with pytest.raises(ValidationError, match="e-consent"):
        criminal_outline(gaps=gaps_without_consent)


def test_defence_cannot_cite_its_legal_basis_through_a_link() -> None:
    with pytest.raises(ValidationError, match="case file"):
        EvidenceLink(
            link_id="l-law",
            element_id="e-consent",
            citation=cite(SourceKind.LAW, "zz-penal-code", DEFENCE_LAW, "not taking"),
            relation=EvidenceRelation.CONTRADICTS,
            purpose="x",
        )


def test_criminal_outline_query_still_needs_party_role() -> None:
    with pytest.raises(ValidationError, match="party_role"):
        LegalQuery(
            query_id="q",
            text="t",
            jurisdiction="ZZ",
            as_of=date(2026, 1, 1),
            response_language="en",
            task_type=TaskType.EVIDENCE_OUTLINE,
            case_id="zz-crim-case-1",
        )
