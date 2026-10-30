"""Phase A: deterministic citation checks. No model access by construction (this module has none).

Exactness policy (CN first): text is compared by exact Unicode code-point equality and substring
search (`==`, `in`). No normalization of any kind is applied — not NFC/NFKC, not full-/half-width
folding, not whitespace or punctuation folding, not simplified/traditional mapping. Offsets are
Unicode code-point offsets (Python `str` indexing).
"""

from collections.abc import Sequence
from dataclasses import dataclass

from legalai_contracts import (
    CaseDocument,
    CaseFileStore,
    Citation,
    DocType,
    LegalQuery,
    SourceDocument,
    SourceKind,
    SourceSpan,
    SourceStore,
    Verdict,
)

LAW_DOC_TYPES = frozenset(
    {
        DocType.CONSTITUTION,
        DocType.STATUTE,
        DocType.REGULATION,
        DocType.JUDICIAL_INTERPRETATION,
        DocType.CASE,
    }
)
"""Doc types that can establish a legal rule (ADR-0005: statute, judicial interpretation, case law)."""

_FAILURE_PRIORITY = (
    Verdict.CITATION_INVALID,
    Verdict.WRONG_JURISDICTION,
    Verdict.NOT_IN_FORCE,
    Verdict.CHECK_ERROR,
)


@dataclass(frozen=True)
class ResolvedCitation:
    """A citation that passed every Phase A check, carrying text re-read from the store."""

    kind: SourceKind
    doc_id: str
    version_id: str
    start_char: int
    end_char: int
    stored_text: str
    quote: str
    pinpoint: str | None
    title: str | None
    """Law document title (public metadata); None for case files (P9: send the minimum)."""


@dataclass(frozen=True)
class CitationFailure:
    verdict: Verdict
    method: str
    reason: str


CitationOutcome = ResolvedCitation | CitationFailure


def worst_failure(failures: Sequence[CitationFailure]) -> CitationFailure:
    """The failure that decides an item's verdict: definitive invalidity outranks a check error."""
    return min(failures, key=lambda f: _FAILURE_PRIORITY.index(f.verdict))


def _fail(verdict: Verdict, check: str, label: str, reason: str) -> CitationFailure:
    return CitationFailure(verdict=verdict, method=f"phase_a:{check}", reason=f"{label}: {reason}")


def _first_difference(a: str, b: str) -> int:
    for i, (x, y) in enumerate(zip(a, b, strict=False)):
        if x != y:
            return i
    return min(len(a), len(b))


def _span_shape(span: SourceSpan, quote: str, label: str) -> CitationFailure | None:
    """Re-check the span's own invariants: the draft may have been built without contract validation."""
    if not (
        isinstance(span.start_char, int) and isinstance(span.end_char, int) and isinstance(span.text, str)
    ):
        return _fail(Verdict.CITATION_INVALID, "span_shape", label, "span fields have wrong types")
    if span.start_char < 0 or span.end_char <= span.start_char:
        return _fail(Verdict.CITATION_INVALID, "span_shape", label, "offsets are not a non-empty range")
    if len(span.text) != span.end_char - span.start_char:
        return _fail(Verdict.CITATION_INVALID, "span_shape", label, "span text length does not match offsets")
    if not isinstance(quote, str) or not quote.strip():
        return _fail(Verdict.CITATION_INVALID, "quote_empty", label, "quote is empty or whitespace only")
    return None


def _compare_text(
    span: SourceSpan, stored: object, quote: str, label: str, *, show_chars: bool
) -> CitationFailure | None:
    expected_len = span.end_char - span.start_char
    if not isinstance(stored, str) or len(stored) != expected_len:
        return _fail(
            Verdict.CHECK_ERROR, "store_contract", label, "store returned text of the wrong type or length"
        )
    if stored != span.text:
        at = _first_difference(stored, span.text)
        detail = f"span text differs from stored text at code point {at} of the span"
        if show_chars:
            detail += f" (stored U+{ord(stored[at]):04X}, cited U+{ord(span.text[at]):04X})"
        return _fail(Verdict.CITATION_INVALID, "span_text", label, detail)
    if quote not in stored:
        return _fail(
            Verdict.CITATION_INVALID, "quote_verbatim", label, "quote is not verbatim in stored text"
        )
    return None


def check_law_citation(
    citation: Citation,
    *,
    label: str,
    query: LegalQuery,
    store: SourceStore,
    require_law_doc_type: bool,
) -> CitationOutcome:
    """Resolve a law citation in `store` and check text, quote, jurisdiction and temporal validity."""
    if not isinstance(citation, Citation) or not isinstance(citation.span, SourceSpan):
        return _fail(Verdict.CHECK_ERROR, "input_type", label, "citation is not a contract Citation")
    span, quote = citation.span, citation.quote
    if span.source is not SourceKind.LAW:
        return _fail(
            Verdict.CITATION_INVALID, "source_kind", label, f"expected a law span, got {span.source}"
        )
    shape = _span_shape(span, quote, label)
    if shape is not None:
        return shape
    try:
        doc = store.get_document(span.doc_id, span.version_id)
    except LookupError:
        return _fail(
            Verdict.CITATION_INVALID,
            "resolve",
            label,
            f"{span.doc_id}@{span.version_id} does not resolve in the source store",
        )
    if not isinstance(doc, SourceDocument) or (doc.doc_id, doc.version_id) != (span.doc_id, span.version_id):
        return _fail(
            Verdict.CHECK_ERROR, "store_contract", label, "source store returned a different document"
        )
    if span.end_char > doc.char_count:
        return _fail(Verdict.CITATION_INVALID, "offsets", label, "span ends beyond the end of the document")
    stored = store.get_text(span.doc_id, span.version_id, span.start_char, span.end_char)
    text_problem = _compare_text(span, stored, quote, label, show_chars=True)
    if text_problem is not None:
        return text_problem
    if require_law_doc_type and doc.doc_type not in LAW_DOC_TYPES:
        return _fail(
            Verdict.CITATION_INVALID, "doc_type", label, f"doc_type {doc.doc_type} cannot establish law"
        )
    if doc.jurisdiction != query.jurisdiction:
        return _fail(
            Verdict.WRONG_JURISDICTION,
            "jurisdiction",
            label,
            f"source jurisdiction {doc.jurisdiction} != query jurisdiction {query.jurisdiction}",
        )
    if not doc.in_force_on(query.as_of):
        return _fail(
            Verdict.NOT_IN_FORCE,
            "in_force",
            label,
            f"version in force [{doc.effective_from}, {doc.effective_to or 'open'}) "
            f"excludes as_of {query.as_of}",
        )
    return ResolvedCitation(
        kind=SourceKind.LAW,
        doc_id=span.doc_id,
        version_id=span.version_id,
        start_char=span.start_char,
        end_char=span.end_char,
        stored_text=str(stored),
        quote=quote,
        pinpoint=span.pinpoint,
        title=doc.title,
    )


def check_case_citation(
    citation: Citation,
    *,
    label: str,
    query: LegalQuery,
    store: CaseFileStore,
) -> CitationOutcome:
    """Resolve a case-file citation, confirm it belongs to the query's case, then check text and quote.

    Case membership is checked before any text is read, so text of another case is never fetched (P9).
    """
    if not isinstance(citation, Citation) or not isinstance(citation.span, SourceSpan):
        return _fail(Verdict.CHECK_ERROR, "input_type", label, "citation is not a contract Citation")
    span, quote = citation.span, citation.quote
    if span.source is not SourceKind.CASE_FILE:
        return _fail(
            Verdict.CITATION_INVALID, "source_kind", label, f"expected a case-file span, got {span.source}"
        )
    shape = _span_shape(span, quote, label)
    if shape is not None:
        return shape
    case_id = query.case_id
    if not case_id:
        return _fail(Verdict.CITATION_INVALID, "case_membership", label, "query has no case_id")
    try:
        doc = store.get_document(span.doc_id, span.version_id)
    except LookupError:
        return _fail(
            Verdict.CITATION_INVALID,
            "resolve",
            label,
            f"{span.doc_id}@{span.version_id} does not resolve in the case-file store",
        )
    if not isinstance(doc, CaseDocument) or (doc.doc_id, doc.version_id) != (span.doc_id, span.version_id):
        return _fail(
            Verdict.CHECK_ERROR, "store_contract", label, "case-file store returned a different document"
        )
    if doc.case_id != case_id:
        return _fail(
            Verdict.CITATION_INVALID, "case_membership", label, "document belongs to a different case"
        )
    listed = {(d.doc_id, d.version_id) for d in store.list_documents(case_id)}
    if (doc.doc_id, doc.version_id) not in listed:
        return _fail(
            Verdict.CITATION_INVALID,
            "case_membership",
            label,
            "document version is not listed for the query's case",
        )
    if span.end_char > doc.char_count:
        return _fail(Verdict.CITATION_INVALID, "offsets", label, "span ends beyond the end of the document")
    stored = store.get_text(span.doc_id, span.version_id, span.start_char, span.end_char)
    # Case text is confidential: report the position of a mismatch, never the characters.
    text_problem = _compare_text(span, stored, quote, label, show_chars=False)
    if text_problem is not None:
        return text_problem
    return ResolvedCitation(
        kind=SourceKind.CASE_FILE,
        doc_id=span.doc_id,
        version_id=span.version_id,
        start_char=span.start_char,
        end_char=span.end_char,
        stored_text=str(stored),
        quote=quote,
        pinpoint=span.pinpoint,
        title=None,
    )
