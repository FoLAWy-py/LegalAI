"""Contracts 0.4.0 additions (REQ-PMO-0010, ADR-0007), on synthetic `ZZ` data.

All law and case text here is fictional (jurisdiction `ZZ`, marker SYNTHETIC). It states nothing about real
law, and the temporal-application provision below is invented only to give the reference dates a cited basis.
"""

import hashlib
from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from legalai_contracts import (
    CONTRACT_VERSION,
    CaseDocument,
    CaseFileStore,
    Citation,
    Claim,
    ClaimKind,
    DocType,
    DocumentNotFoundError,
    DraftAnswer,
    Element,
    EvidenceLink,
    EvidenceOutline,
    EvidenceRelation,
    Gap,
    GapKind,
    ItemVerification,
    LegalQuery,
    ModelTrace,
    PartyRole,
    ReferenceDate,
    ReferenceDateKind,
    ReportStatus,
    SourceDocument,
    SourceKind,
    SourceSpan,
    SourceStore,
    TaskType,
    Verdict,
    VerificationReport,
)

PENAL_2015 = (
    "SYNTHETIC ZZ Penal Code (2015 version) art.40: Whoever raises funds from the public without a licence "
    "commits unlicensed fundraising."
)
INTERPRETATION_2021 = (
    "SYNTHETIC ZZ Court Interpretation (2021) art.2: Funds are raised from the public when solicited from "
    "more than thirty persons."
)
TEMPORAL = (
    "SYNTHETIC ZZ Penal Code art.12: An act is judged under the version in force when it was done. "
    "An interpretation applies to cases decided while it is in force."
)
INDICTMENT = "SYNTHETIC indictment: from 2014-03-01 to 2018-06-30 the accused solicited deposits."
JUDGMENT = "SYNTHETIC judgment record: judgment pronounced on 2021-09-15."
LEDGER = "SYNTHETIC ledger: deposits were received from forty-two persons."


def cite(source: SourceKind, doc_id: str, text: str, quote: str, ref: str | None = None) -> Citation:
    span = SourceSpan(
        source=source, doc_id=doc_id, version_id="v1", start_char=0, end_char=len(text), text=text
    )
    if ref is None:
        return Citation(span=span, quote=quote)
    return Citation(span=span, quote=quote, reference_date_id=ref)


def law(doc_id: str, text: str, quote: str, ref: str | None = None) -> Citation:
    return cite(SourceKind.LAW, doc_id, text, quote, ref)


def case_file(doc_id: str, text: str, quote: str) -> Citation:
    return cite(SourceKind.CASE_FILE, doc_id, text, quote)


def query() -> LegalQuery:
    return LegalQuery(
        query_id="q-zz-fund-1",
        text="SYNTHETIC: the accused is charged with unlicensed fundraising.",
        jurisdiction="ZZ",
        as_of=date(2021, 9, 15),
        response_language="en",
        task_type=TaskType.EVIDENCE_OUTLINE,
        case_id="zz-fund-case-1",
        party_role=PartyRole.PROSECUTION,
    )


def conduct_date() -> ReferenceDate:
    return ReferenceDate(
        reference_id="rd-conduct",
        kind=ReferenceDateKind.CONDUCT,
        day=date(2018, 6, 30),
        period_start=date(2014, 3, 1),
        period_end=date(2018, 6, 30),
        description="Last day of the solicitation period stated in the indictment.",
        basis=(law("zz-penal-code", TEMPORAL, "judged under the version in force when it was done"),),
        evidence=(case_file("zz-indictment", INDICTMENT, "from 2014-03-01 to 2018-06-30"),),
    )


def adjudication_date() -> ReferenceDate:
    return ReferenceDate(
        reference_id="rd-adjudication",
        kind=ReferenceDateKind.ADJUDICATION,
        day=date(2021, 9, 15),
        description="Date the judgment was pronounced.",
        basis=(law("zz-penal-code", TEMPORAL, "applies to cases decided while it is in force"),),
        evidence=(case_file("zz-judgment", JUDGMENT, "judgment pronounced on 2021-09-15"),),
    )


def elements(with_refs: bool = True) -> tuple[Element, ...]:
    conduct = "rd-conduct" if with_refs else None
    adjudication = "rd-adjudication" if with_refs else None
    return (
        Element(
            element_id="e-unlicensed",
            description="The accused raised funds without a licence.",
            legal_basis=(law("zz-penal-code-2015", PENAL_2015, "without a licence", conduct),),
        ),
        Element(
            element_id="e-public",
            description="The funds were raised from the public.",
            # One element, two citations selected for two different reference dates.
            legal_basis=(
                law("zz-penal-code-2015", PENAL_2015, "raises funds from the public", conduct),
                law("zz-interpretation-2021", INTERPRETATION_2021, "more than thirty persons", adjudication),
            ),
        ),
    )


def outline(with_refs: bool = True, **kw: object) -> EvidenceOutline:
    args: dict[str, object] = {
        "query": query(),
        "cause_of_action": "SYNTHETIC ZZ Penal Code art.40 unlicensed fundraising",
        "elements": elements(with_refs),
        "links": (
            EvidenceLink(
                link_id="l-ledger",
                element_id="e-public",
                citation=case_file("zz-ledger", LEDGER, "forty-two persons"),
                relation=EvidenceRelation.SUPPORTS,
                purpose="Shows deposits came from forty-two persons.",
            ),
        ),
        "gaps": (Gap(element_id="e-unlicensed", kind=GapKind.NO_EVIDENCE, description="No licence record."),),
        "traces": (ModelTrace(model="t", prompt_id="p", prompt_version="1", temperature=0),),
    }
    if with_refs:
        args["reference_dates"] = (conduct_date(), adjudication_date())
    args.update(kw)
    return EvidenceOutline.model_validate(args)


# ---- AC1: reference dates -------------------------------------------------------------------------


def test_criminal_outline_with_two_reference_dates() -> None:
    result = outline()
    declared = {r.reference_id: r for r in result.reference_dates}
    assert set(declared) == {"rd-conduct", "rd-adjudication"}
    assert declared["rd-conduct"].kind is ReferenceDateKind.CONDUCT
    assert declared["rd-adjudication"].kind is ReferenceDateKind.ADJUDICATION
    assert declared["rd-conduct"].day != declared["rd-adjudication"].day
    used = {c.reference_date_id for e in result.elements for c in e.legal_basis}
    assert used == set(declared)
    mixed = result.elements[1]
    assert {c.reference_date_id for c in mixed.legal_basis} == {"rd-conduct", "rd-adjudication"}


def test_reference_dates_round_trip_through_json() -> None:
    original = outline()
    assert EvidenceOutline.model_validate_json(original.model_dump_json()) == original


def test_same_outline_without_new_fields_still_validates() -> None:
    plain = outline(with_refs=False)
    assert plain.reference_dates == ()
    assert all(c.reference_date_id is None for e in plain.elements for c in e.legal_basis)


def test_contracts_0_3_json_without_new_keys_validates() -> None:
    data = outline(with_refs=False).model_dump(mode="json")
    del data["reference_dates"]
    for element in data["elements"]:
        for citation in element["legal_basis"]:
            del citation["reference_date_id"]
    for link in data["links"]:
        del link["citation"]["reference_date_id"]
    for trace in data["traces"]:
        del trace["input_tokens"], trace["output_tokens"]
    assert EvidenceOutline.model_validate(data) == outline(with_refs=False)


def test_citation_naming_undeclared_reference_date_is_rejected() -> None:
    with pytest.raises(ValidationError, match="undeclared reference dates"):
        outline(reference_dates=(conduct_date(),))


def test_declared_reference_date_must_be_used() -> None:
    extra = ReferenceDate(
        reference_id="rd-unused",
        kind=ReferenceDateKind.OTHER,
        day=date(2020, 1, 1),
        description="A date nothing relies on.",
        basis=(law("zz-penal-code", TEMPORAL, "version in force"),),
    )
    with pytest.raises(ValidationError, match="named by no citation"):
        outline(reference_dates=(conduct_date(), adjudication_date(), extra))


def test_reference_ids_are_unique() -> None:
    with pytest.raises(ValidationError, match="duplicate reference_id"):
        outline(reference_dates=(conduct_date(), adjudication_date(), conduct_date()))


def test_abstained_outline_cannot_name_undeclared_reference_date() -> None:
    with pytest.raises(ValidationError, match="undeclared"):
        outline(abstained=True, abstain_reason="x", reference_dates=())


def test_case_file_citation_cannot_carry_reference_date() -> None:
    with pytest.raises(ValidationError, match="only law citations"):
        cite(SourceKind.CASE_FILE, "zz-ledger", LEDGER, "forty-two persons", "rd-conduct")


def test_reference_date_needs_law_basis() -> None:
    with pytest.raises(ValidationError):
        ReferenceDate(
            reference_id="r", kind=ReferenceDateKind.CONDUCT, day=date(2018, 1, 1), description="d", basis=()
        )
    with pytest.raises(ValidationError, match="basis must cite law"):
        ReferenceDate(
            reference_id="r",
            kind=ReferenceDateKind.CONDUCT,
            day=date(2018, 1, 1),
            description="d",
            basis=(case_file("zz-indictment", INDICTMENT, "solicited deposits"),),
        )


def test_reference_date_evidence_must_cite_case_files() -> None:
    with pytest.raises(ValidationError, match="evidence must cite case files"):
        ReferenceDate.model_validate(
            {**conduct_date().model_dump(), "evidence": (law("zz-penal-code", TEMPORAL, "version in force"),)}
        )


@pytest.mark.parametrize(
    ("start", "end", "day", "message"),
    [
        (date(2014, 3, 1), None, date(2015, 1, 1), "together"),
        (date(2018, 6, 30), date(2014, 3, 1), date(2015, 1, 1), "precedes"),
        (date(2014, 3, 1), date(2018, 6, 30), date(2019, 1, 1), "within the period"),
    ],
)
def test_reference_date_period_is_consistent(start: date, end: date | None, day: date, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        ReferenceDate(
            reference_id="r",
            kind=ReferenceDateKind.CONDUCT,
            day=day,
            period_start=start,
            period_end=end,
            description="d",
            basis=(law("zz-penal-code", TEMPORAL, "version in force"),),
        )


def test_draft_answer_cannot_carry_reference_dates() -> None:
    claim = Claim(
        claim_id="c1",
        text="SYNTHETIC rule.",
        kind=ClaimKind.LEGAL_RULE,
        citations=(law("zz-penal-code-2015", PENAL_2015, "without a licence", "rd-conduct"),),
    )
    research = query().model_copy(update={"task_type": TaskType.RESEARCH_QA})
    with pytest.raises(ValidationError, match="reference_date_id"):
        DraftAnswer(
            query=research,
            claims=(claim,),
            answer_text="x",
            traces=(ModelTrace(model="t", prompt_id="p", prompt_version="1", temperature=0),),
        )


# ---- AC2: token usage, not-found exception, verification traces ------------------------------------


def test_model_trace_token_fields_default_to_not_reported() -> None:
    trace = ModelTrace(model="t", prompt_id="p", prompt_version="1", temperature=0)
    assert trace.input_tokens is None
    assert trace.output_tokens is None


def test_model_trace_records_token_usage() -> None:
    trace = ModelTrace(
        model="t", prompt_id="p", prompt_version="1", temperature=0, input_tokens=1200, output_tokens=0
    )
    assert (trace.input_tokens, trace.output_tokens) == (1200, 0)
    assert ModelTrace.model_validate_json(trace.model_dump_json()) == trace


@pytest.mark.parametrize("field", ["input_tokens", "output_tokens"])
def test_model_trace_rejects_negative_tokens(field: str) -> None:
    with pytest.raises(ValidationError):
        ModelTrace.model_validate(
            {"model": "t", "prompt_id": "p", "prompt_version": "1", "temperature": 0, field: -1}
        )


def test_not_found_is_a_lookup_error_with_ids() -> None:
    err = DocumentNotFoundError("zz-act/v9", doc_id="zz-act", version_id="v9")
    assert isinstance(err, LookupError)
    assert (err.doc_id, err.version_id) == ("zz-act", "v9")
    assert str(err) == "zz-act/v9"
    assert DocumentNotFoundError("message only").doc_id is None


class _IntegrityError(Exception):
    """Stand-in for a store's own integrity error: deliberately not a DocumentNotFoundError."""


class _StoreNotFound(DocumentNotFoundError, KeyError):
    """An implementation may subclass the contract error together with its own bases."""


class _FakeLawStore:
    def __init__(self, doc: SourceDocument, text: str) -> None:
        self._doc, self._text = doc, text

    def list_documents(self, jurisdiction: str) -> list[SourceDocument]:
        return [self._doc] if jurisdiction == self._doc.jurisdiction else []

    def get_document(self, doc_id: str, version_id: str) -> SourceDocument:
        if (doc_id, version_id) != (self._doc.doc_id, self._doc.version_id):
            raise _StoreNotFound(f"{doc_id}/{version_id}", doc_id=doc_id, version_id=version_id)
        return self._doc

    def get_text(self, doc_id: str, version_id: str, start_char: int, end_char: int) -> str:
        doc = self.get_document(doc_id, version_id)
        if hashlib.sha256(self._text.encode("utf-8")).hexdigest() != doc.content_sha256:
            raise _IntegrityError("stored text does not match content_sha256")
        if not 0 <= start_char <= end_char <= doc.char_count:
            raise ValueError("range outside document")
        return self._text[start_char:end_char]


def source_document(text: str) -> SourceDocument:
    return SourceDocument(
        doc_id="zz-penal-code-2015",
        version_id="v1",
        title="SYNTHETIC ZZ Penal Code (2015 version)",
        jurisdiction="ZZ",
        doc_type=DocType.STATUTE,
        language="en",
        effective_from=date(2015, 1, 1),
        effective_to=date(2020, 1, 1),
        source_uri="https://example.invalid/zz/penal-code-2015",
        retrieved_at=datetime(2026, 10, 30, tzinfo=UTC),
        content_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        char_count=len(text),
    )


def test_store_raises_contract_not_found_for_absent_version() -> None:
    store = _FakeLawStore(source_document(PENAL_2015), PENAL_2015)
    assert isinstance(store, SourceStore)
    assert store.list_documents("ZZ-B") == []
    with pytest.raises(DocumentNotFoundError) as caught:
        store.get_document("zz-penal-code-2015", "v2")
    assert caught.value.version_id == "v2"
    with pytest.raises(DocumentNotFoundError):
        store.get_text("zz-missing", "v1", 0, 1)


def test_other_store_errors_are_not_not_found() -> None:
    """The consumer rule: only DocumentNotFoundError means "absent"; anything else fails closed."""
    store = _FakeLawStore(source_document(PENAL_2015), PENAL_2015 + " tampered")
    with pytest.raises(_IntegrityError) as caught:
        store.get_text("zz-penal-code-2015", "v1", 0, 5)
    assert not isinstance(caught.value, DocumentNotFoundError)
    with pytest.raises(ValueError) as bad_range:
        _FakeLawStore(source_document(PENAL_2015), PENAL_2015).get_text("zz-penal-code-2015", "v1", 0, 10**6)
    assert not isinstance(bad_range.value, DocumentNotFoundError)


def test_port_docstrings_state_the_error_contract() -> None:
    for port in (SourceStore, CaseFileStore):
        doc = port.__doc__ or ""
        assert "DocumentNotFoundError" in doc
        assert "ADR-0007 §3" in doc
        assert "fail closed" in doc


def verifier_trace() -> ModelTrace:
    return ModelTrace(
        model="zz-judge",
        prompt_id="verification.law_establishes_element",
        prompt_version="1",
        temperature=0,
        source_versions=("zz-penal-code-2015@v1",),
        input_tokens=900,
        output_tokens=60,
    )


def test_item_verification_carries_model_traces() -> None:
    item = ItemVerification(
        item_id="e-unlicensed",
        verdict=Verdict.SUPPORTED,
        method="phase_b",
        rationale="SYNTHETIC rationale.",
        traces=(verifier_trace(),),
    )
    report = VerificationReport(
        query_id="q-zz-fund-1", status=ReportStatus.PASS, items=(item,), verifier_version="0"
    )
    assert report.items[0].traces[0].prompt_id == "verification.law_establishes_element"
    assert VerificationReport.model_validate_json(report.model_dump_json()) == report


def test_item_verification_traces_default_empty_for_deterministic_checks() -> None:
    item = ItemVerification(item_id="l1", verdict=Verdict.CITATION_INVALID, method="phase_a", rationale="")
    assert item.traces == ()


def test_traces_do_not_relax_fail_closed_report() -> None:
    bad = ItemVerification(
        item_id="e1", verdict=Verdict.UNSUPPORTED, method="m", rationale="", traces=(verifier_trace(),)
    )
    with pytest.raises(ValidationError, match="PASS"):
        VerificationReport(query_id="q", status=ReportStatus.PASS, items=(bad,), verifier_version="0")


# ---- AC3: hash semantics -----------------------------------------------------------------------------


def test_content_sha256_descriptions_reference_adr() -> None:
    for model in (SourceDocument, CaseDocument):
        description = model.model_fields["content_sha256"].description or ""
        assert "ADR-0007 §4" in description
        assert "UTF-8" in description
        assert "ADR-0007 §4" in (model.model_fields["original_sha256"].description or "")


def test_content_sha256_rule_on_non_ascii_text() -> None:
    text = "SYNTHETIC ZZ 刑事证据条款 第一条。\n第二条。"
    doc = source_document(text)
    assert doc.content_sha256 == hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert doc.char_count == len(text)  # code points, not bytes


def test_original_sha256_is_optional_and_well_formed() -> None:
    doc = source_document(PENAL_2015)
    assert doc.original_sha256 is None
    raw = b"<html>SYNTHETIC raw page</html>"
    with_original = doc.model_copy(update={"original_sha256": hashlib.sha256(raw).hexdigest()})
    assert SourceDocument.model_validate(with_original.model_dump()) == with_original
    with pytest.raises(ValidationError):
        SourceDocument.model_validate({**doc.model_dump(), "original_sha256": "ABC"})
    case_doc = CaseDocument(
        case_id="zz-fund-case-1",
        doc_id="zz-ledger",
        version_id="v1",
        title="SYNTHETIC ledger",
        language="en",
        media_type="text/plain",
        received_at=datetime(2026, 10, 30, tzinfo=UTC),
        content_sha256=hashlib.sha256(LEDGER.encode("utf-8")).hexdigest(),
        char_count=len(LEDGER),
        page_starts=(0,),
        original_sha256=hashlib.sha256(LEDGER.encode("utf-8") + b"\r\n").hexdigest(),
    )
    assert case_doc.original_sha256 != case_doc.content_sha256
    with pytest.raises(ValidationError):
        CaseDocument.model_validate({**case_doc.model_dump(), "original_sha256": "0" * 63})


# ---- AC4: version --------------------------------------------------------------------------------------


def test_contract_version_is_minor_bump() -> None:
    assert CONTRACT_VERSION == "0.4.0"
