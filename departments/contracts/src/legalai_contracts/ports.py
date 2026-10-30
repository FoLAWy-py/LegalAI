"""Ports: the behaviour departments provide to each other, wired together by `interface`."""

from typing import Protocol, runtime_checkable

from legalai_contracts.answers import DraftAnswer, LegalQuery
from legalai_contracts.outline import EvidenceOutline
from legalai_contracts.sources import CaseDocument, SourceDocument, SourceSpan
from legalai_contracts.verification import VerificationReport


@runtime_checkable
class SourceStore(Protocol):
    """Implemented by corpus. Authoritative text and metadata of law document versions.

    Error contract (ADR-0007 §3):
    - `get_document` and `get_text` raise `legalai_contracts.DocumentNotFoundError` when the store holds
      no version with that `doc_id` / `version_id`. `list_documents` returns `[]` when nothing matches.
    - `get_text` returns exactly the stored characters `[start_char, end_char)` (code points). A range
      outside `0 <= start_char <= end_char <= char_count` raises `ValueError` and is never clamped; an
      empty range MAY also raise `ValueError`.
    - The store MUST NOT serve text whose stored bytes do not hash to `content_sha256` (ADR-0007 §4);
      it raises an error that is not `DocumentNotFoundError`.
    - Consumers treat `DocumentNotFoundError` as "this version does not exist" (for a citation: invalid)
      and catch it by that class only. Any other exception means the store could not answer: consumers
      MUST fail closed (verification: `CHECK_ERROR`), never treat it as "not found" or as success, and
      never fall back silently to another version.
    """

    def list_documents(self, jurisdiction: str) -> list[SourceDocument]: ...

    def get_document(self, doc_id: str, version_id: str) -> SourceDocument: ...

    def get_text(self, doc_id: str, version_id: str, start_char: int, end_char: int) -> str: ...


@runtime_checkable
class CaseFileStore(Protocol):
    """Implemented by casefile. Confidential case documents, with page mapping.

    Same error contract as `SourceStore` (ADR-0007 §3): `DocumentNotFoundError` for an absent version,
    `[]` from `list_documents` for an unknown case, `ValueError` for an invalid range, never text that
    fails its `content_sha256`, and fail closed on any other exception. Error messages carry ids only,
    never document text (P9).
    """

    def list_documents(self, case_id: str) -> list[CaseDocument]: ...

    def get_document(self, doc_id: str, version_id: str) -> CaseDocument: ...

    def get_text(self, doc_id: str, version_id: str, start_char: int, end_char: int) -> str: ...


@runtime_checkable
class Retriever(Protocol):
    """Implemented by retrieval. Returns law spans relevant to the query, best first."""

    def retrieve(self, query: LegalQuery, limit: int) -> list[SourceSpan]: ...


@runtime_checkable
class EvidenceRetriever(Protocol):
    """Implemented by retrieval. Searches one case's files for passages relevant to `text`."""

    def search_case(self, case_id: str, text: str, limit: int) -> list[SourceSpan]: ...


@runtime_checkable
class Answerer(Protocol):
    """Implemented by reasoning. Produces a cited draft from retrieved spans only."""

    def answer(self, query: LegalQuery) -> DraftAnswer: ...


@runtime_checkable
class OutlineBuilder(Protocol):
    """Implemented by reasoning. Produces an evidence outline from retrieved spans only."""

    def build_outline(self, query: LegalQuery) -> EvidenceOutline: ...


@runtime_checkable
class Verifier(Protocol):
    """Implemented by verification. Independently judges outputs against the stores."""

    def verify(self, draft: DraftAnswer) -> VerificationReport: ...

    def verify_outline(self, outline: EvidenceOutline) -> VerificationReport: ...
