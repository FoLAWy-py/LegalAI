"""Shared contracts between LegalAI departments. Data shapes and ports only — no logic, no I/O."""

from legalai_contracts._base import SYNTHETIC_JURISDICTION
from legalai_contracts.answers import (
    Citation,
    Claim,
    ClaimKind,
    DraftAnswer,
    LegalQuery,
    ModelTrace,
    PartyRole,
    TaskType,
)
from legalai_contracts.errors import DocumentNotFoundError
from legalai_contracts.outline import (
    Element,
    EvidenceLink,
    EvidenceOutline,
    EvidenceRelation,
    Gap,
    GapKind,
    ReferenceDate,
    ReferenceDateKind,
)
from legalai_contracts.ports import (
    Answerer,
    CaseFileStore,
    EvidenceRetriever,
    OutlineBuilder,
    Retriever,
    SourceStore,
    Verifier,
)
from legalai_contracts.sources import CaseDocument, DocType, SourceDocument, SourceKind, SourceSpan
from legalai_contracts.verification import (
    ItemVerification,
    ReportStatus,
    Verdict,
    VerificationReport,
)

CONTRACT_VERSION = "0.4.0"

__all__ = [
    "CONTRACT_VERSION",
    "SYNTHETIC_JURISDICTION",
    "Answerer",
    "CaseDocument",
    "CaseFileStore",
    "Citation",
    "Claim",
    "ClaimKind",
    "DocType",
    "DocumentNotFoundError",
    "DraftAnswer",
    "Element",
    "EvidenceLink",
    "EvidenceOutline",
    "EvidenceRelation",
    "EvidenceRetriever",
    "Gap",
    "GapKind",
    "ItemVerification",
    "LegalQuery",
    "ModelTrace",
    "OutlineBuilder",
    "PartyRole",
    "ReferenceDate",
    "ReferenceDateKind",
    "ReportStatus",
    "Retriever",
    "SourceDocument",
    "SourceKind",
    "SourceSpan",
    "SourceStore",
    "TaskType",
    "Verdict",
    "VerificationReport",
    "Verifier",
]
