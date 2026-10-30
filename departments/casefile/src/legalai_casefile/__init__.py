"""LegalAI casefile department. Public API: only names in __all__ may be imported by other departments.

Intake of confidential case documents (.docx, .txt, .md, .eml, text-layer PDF) into exact,
page-addressable text, and the `CaseFileStore` implementation `LocalCaseFileStore`.
"""

from legalai_casefile._common import detect_language
from legalai_casefile.errors import (
    CasefileError,
    CorruptDocumentError,
    DocumentNotFoundError,
    EmptyDocumentError,
    EncryptedDocumentError,
    FormatMismatchError,
    IntakeError,
    IntakeReason,
    InvalidIdentifierError,
    InvalidRangeError,
    PartialExtractionError,
    ScannedDocumentError,
    StoreIntegrityError,
    TooLargeError,
    UndecodableTextError,
    UnsupportedContentError,
    UnsupportedFormatError,
)
from legalai_casefile.extraction import (
    DEFAULT_MAX_BYTES,
    PAGE_TERMINATOR,
    SUPPORTED_EXTENSIONS,
    Extraction,
    extract_document,
)
from legalai_casefile.store import IntakeResult, LocalCaseFileStore, StoredVersion, derive_doc_id

__all__ = [
    "DEFAULT_MAX_BYTES",
    "PAGE_TERMINATOR",
    "SUPPORTED_EXTENSIONS",
    "CasefileError",
    "CorruptDocumentError",
    "DocumentNotFoundError",
    "EmptyDocumentError",
    "EncryptedDocumentError",
    "Extraction",
    "FormatMismatchError",
    "IntakeError",
    "IntakeReason",
    "IntakeResult",
    "InvalidIdentifierError",
    "InvalidRangeError",
    "LocalCaseFileStore",
    "PartialExtractionError",
    "ScannedDocumentError",
    "StoreIntegrityError",
    "StoredVersion",
    "TooLargeError",
    "UndecodableTextError",
    "UnsupportedContentError",
    "UnsupportedFormatError",
    "derive_doc_id",
    "detect_language",
    "extract_document",
]
