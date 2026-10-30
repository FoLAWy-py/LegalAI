from datetime import date

import pytest
from pydantic import ValidationError

from legalai_contracts import (
    Citation,
    Claim,
    ClaimKind,
    DraftAnswer,
    ItemVerification,
    LegalQuery,
    ModelTrace,
    ReportStatus,
    SourceKind,
    SourceSpan,
    Verdict,
    VerificationReport,
)

TEXT = "SYNTHETIC Act s.1: A lease of land must be in writing."


def span(source: SourceKind = SourceKind.LAW, text: str = TEXT) -> SourceSpan:
    return SourceSpan(
        source=source, doc_id="zz-act", version_id="v1", start_char=0, end_char=len(text), text=text
    )


def query() -> LegalQuery:
    return LegalQuery(
        query_id="q1",
        text="Must a lease be written?",
        jurisdiction="ZZ",
        as_of=date(2026, 1, 1),
        response_language="en",
    )


def trace() -> ModelTrace:
    return ModelTrace(model="test", prompt_id="p", prompt_version="1", temperature=0)


def rule(claim_id: str = "c1") -> Claim:
    return Claim(
        claim_id=claim_id,
        text="Leases of land must be written.",
        kind=ClaimKind.LEGAL_RULE,
        citations=(Citation(span=span(), quote="must be in writing"),),
    )


def test_span_offsets_must_match_text() -> None:
    with pytest.raises(ValidationError):
        SourceSpan(source=SourceKind.LAW, doc_id="d", version_id="v", start_char=0, end_char=5, text="abc")


def test_quote_must_be_verbatim() -> None:
    with pytest.raises(ValidationError, match="verbatim"):
        Citation(span=span(), quote="shall be written")


def test_legal_rule_requires_citation() -> None:
    with pytest.raises(ValidationError):
        Claim(claim_id="c1", text="x", kind=ClaimKind.LEGAL_RULE)


def test_inference_requires_premises() -> None:
    with pytest.raises(ValidationError):
        Claim(claim_id="c2", text="x", kind=ClaimKind.INFERENCE)


def test_draft_rejects_unknown_premise() -> None:
    inference = Claim(claim_id="c2", text="So...", kind=ClaimKind.INFERENCE, derived_from=("missing",))
    with pytest.raises(ValidationError, match="unknown ids"):
        DraftAnswer(query=query(), claims=(rule(), inference), answer_text="...", traces=(trace(),))


def test_draft_abstention_requires_reason() -> None:
    with pytest.raises(ValidationError):
        DraftAnswer(query=query(), answer_text="", abstained=True, traces=(trace(),))


def test_valid_draft() -> None:
    draft = DraftAnswer(query=query(), claims=(rule(),), answer_text="Yes.", traces=(trace(),))
    assert draft.claims[0].citations[0].quote == "must be in writing"


def test_jurisdiction_required_format() -> None:
    with pytest.raises(ValidationError):
        LegalQuery(query_id="q", text="t", jurisdiction="usa", as_of=date(2026, 1, 1), response_language="en")


def test_report_pass_requires_all_supported() -> None:
    bad = ItemVerification(item_id="c1", verdict=Verdict.UNSUPPORTED, method="m", rationale="")
    with pytest.raises(ValidationError, match="PASS"):
        VerificationReport(query_id="q1", status=ReportStatus.PASS, items=(bad,), verifier_version="0")


def test_report_pass_requires_items() -> None:
    with pytest.raises(ValidationError):
        VerificationReport(query_id="q1", status=ReportStatus.PASS, verifier_version="0")


def test_models_are_frozen() -> None:
    q = query()
    with pytest.raises(ValidationError):
        q.text = "changed"  # type: ignore[misc]
