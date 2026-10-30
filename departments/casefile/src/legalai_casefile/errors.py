"""Typed errors of the casefile department.

Messages and attributes never contain document text (P9): only reasons, page numbers, counts and ids.
Callers may therefore log them, but must still not log the documents themselves.
"""

from enum import StrEnum

from legalai_contracts import DocumentNotFoundError as ContractDocumentNotFoundError


class IntakeReason(StrEnum):
    """Machine-readable reason an intake was refused."""

    UNSUPPORTED_FORMAT = "unsupported_format"
    FORMAT_MISMATCH = "format_mismatch"
    ENCRYPTED = "encrypted"
    SCANNED = "scanned"
    PARTIAL_EXTRACTION = "partial_extraction"
    UNSUPPORTED_CONTENT = "unsupported_content"
    UNDECODABLE_TEXT = "undecodable_text"
    EMPTY = "empty"
    CORRUPT = "corrupt"
    TOO_LARGE = "too_large"


class CasefileError(Exception):
    """Base class of every error raised by `legalai_casefile`."""


class IntakeError(CasefileError):
    """A file was refused at intake. Nothing was stored.

    `reason` says why; `pages` lists the affected 1-based pages when the cause is page-specific.
    """

    reason: IntakeReason = IntakeReason.CORRUPT

    def __init__(self, detail: str, *, pages: tuple[int, ...] = ()) -> None:
        self.detail = detail
        self.pages = pages
        where = f" (page(s) {', '.join(map(str, pages))})" if pages else ""
        super().__init__(f"{self.reason.value}: {detail}{where}")


class UnsupportedFormatError(IntakeError):
    """The file type is not one of .docx, .txt, .md, .eml, .pdf (e.g. legacy .doc, images)."""

    reason = IntakeReason.UNSUPPORTED_FORMAT


class FormatMismatchError(IntakeError):
    """The file content does not match its extension (e.g. a PDF renamed to .txt)."""

    reason = IntakeReason.FORMAT_MISMATCH


class EncryptedDocumentError(IntakeError):
    """The file is encrypted or password-protected, even if it opens with an empty password."""

    reason = IntakeReason.ENCRYPTED


class ScannedDocumentError(IntakeError):
    """One or more PDF pages are images without a text layer, or carry an invisible (OCR) text layer.

    OCR is out of scope in v1 (ADR-0005, D9); `pages` lists the offending pages.
    """

    reason = IntakeReason.SCANNED


class PartialExtractionError(IntakeError):
    """Some content could not be turned into exact text (unmapped glyphs, large images, missing text).

    Raised instead of returning a truncated or garbled document.
    """

    reason = IntakeReason.PARTIAL_EXTRACTION


class UnsupportedContentError(IntakeError):
    """The file contains a construct whose text is ambiguous or not extracted in v1
    (tracked changes, form fields, hidden layers, HTML-only e-mail, embedded objects, symbol fonts)."""

    reason = IntakeReason.UNSUPPORTED_CONTENT


class UndecodableTextError(IntakeError):
    """Text bytes are not valid in the declared or assumed encoding. Pass `encoding=` explicitly."""

    reason = IntakeReason.UNDECODABLE_TEXT


class EmptyDocumentError(IntakeError):
    """The file contains no text (only whitespace or nothing)."""

    reason = IntakeReason.EMPTY


class CorruptDocumentError(IntakeError):
    """The file is malformed and cannot be parsed reliably."""

    reason = IntakeReason.CORRUPT


class TooLargeError(IntakeError):
    """The file (or an archive member) exceeds the configured size limit."""

    reason = IntakeReason.TOO_LARGE


class DocumentNotFoundError(CasefileError, ContractDocumentNotFoundError):
    """No stored document has the requested `doc_id` / `version_id`.

    Subclasses `legalai_contracts.DocumentNotFoundError` (ADR-0007 §3, REQ-PMO-0013), so consumers catch it
    by the contract class; it is still a `LookupError`. The `doc_id` / `version_id` attributes are set when
    known; message and attributes carry ids only (P9).
    """


class InvalidRangeError(CasefileError, ValueError):
    """A requested character range is not within `0 <= start <= end <= char_count`. Never clamped."""


class StoreIntegrityError(CasefileError):
    """Stored data does not match its recorded hash or metadata. The store refuses to serve it."""


class InvalidIdentifierError(CasefileError, ValueError):
    """A `case_id` / `doc_id` is not a safe identifier (`[A-Za-z0-9][A-Za-z0-9._-]{0,127}`, no `..`)."""
