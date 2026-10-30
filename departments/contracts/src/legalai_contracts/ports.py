"""Ports: the behaviour departments provide to each other, wired together by `interface`."""

from typing import Protocol, runtime_checkable

from legalai_contracts.answers import DraftAnswer, LegalQuery
from legalai_contracts.outline import EvidenceOutline
from legalai_contracts.sources import CaseDocument, SourceDocument, SourceSpan
from legalai_contracts.verification import VerificationReport


@runtime_checkable
class SourceStore(Protocol):
    """Implemented by corpus. Authoritative text and metadata of law document versions."""

    def list_documents(self, jurisdiction: str) -> list[SourceDocument]: ...

    def get_document(self, doc_id: str, version_id: str) -> SourceDocument: ...

    def get_text(self, doc_id: str, version_id: str, start_char: int, end_char: int) -> str: ...


@runtime_checkable
class CaseFileStore(Protocol):
    """Implemented by casefile. Confidential case documents, with page mapping."""

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
