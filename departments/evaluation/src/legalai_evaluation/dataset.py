"""Evaluation dataset shapes: cases with expected outlines, adversarial items, and a pinned dataset."""

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from legalai_contracts import CaseFileStore, EvidenceOutline, LegalQuery, SourceStore


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class CaseTag(StrEnum):
    """Why a case is in the set. Used for coverage checks and breakdowns."""

    FINANCIAL_OFFENCE = "financial_offence"
    CROSS_LINGUAL = "cross_lingual"
    MISSING_EVIDENCE = "missing_evidence"
    DEFECTIVE_EVIDENCE = "defective_evidence"
    DEFENCE_WITH_CONTRADICTING_EVIDENCE = "defence_with_contradicting_evidence"
    NO_APPLICABLE_LAW = "no_applicable_law"
    SUPERSEDED_VERSION_IN_FORCE = "superseded_version_in_force"


class EvalCase(_Frozen):
    """One evaluation item: a query and the expected outline (or expected abstention) for it.

    Guarantees: `expected.query == query`; `query_language` is the language of `query.text`.
    """

    case_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    query: LegalQuery
    query_language: str = Field(min_length=2, description="BCP 47 tag of the query text.")
    expected: EvidenceOutline
    tags: tuple[CaseTag, ...] = ()
    notes: str = ""

    @model_validator(mode="after")
    def _expected_matches_query(self) -> "EvalCase":
        if self.expected.query != self.query:
            raise ValueError("expected outline must carry the case query")
        if not self.expected.abstained:
            per_element: dict[str, int] = {}
            for gap in self.expected.gaps:
                per_element[gap.element_id] = per_element.get(gap.element_id, 0) + 1
            if any(n > 1 for n in per_element.values()):
                raise ValueError("expected outline may declare at most one gap per element")
        return self

    @property
    def expects_abstention(self) -> bool:
        return self.expected.abstained


class AdversarialKind(StrEnum):
    """The single corruption applied to an otherwise correct expected outline."""

    FABRICATED_LAW_DOCUMENT = "fabricated_law_document"
    ALTERED_LAW_QUOTE = "altered_law_quote"
    SHIFTED_LAW_OFFSETS = "shifted_law_offsets"
    VERSION_NOT_IN_FORCE = "version_not_in_force"
    WRONG_JURISDICTION = "wrong_jurisdiction"
    FABRICATED_CASE_DOCUMENT = "fabricated_case_document"
    ALTERED_EVIDENCE_QUOTE = "altered_evidence_quote"
    EVIDENCE_FROM_OTHER_CASE = "evidence_from_other_case"


class AdversarialItem(_Frozen):
    """A contract-valid outline with exactly one bad citation. A correct verifier never PASSes it."""

    item_id: str = Field(min_length=1)
    kind: AdversarialKind
    base_case_id: str = Field(min_length=1)
    target_item_id: str = Field(
        min_length=1, description="element_id or link_id that carries the bad citation"
    )
    outline: EvidenceOutline
    description: str = Field(min_length=1)


@dataclass(frozen=True)
class EvalDataset:
    """A pinned evaluation dataset: cases, adversarial items, and the stores their citations point into.

    `document_manifest` lists every stored document version as `kind:doc_id@version_id:sha256`, so the
    fingerprint changes whenever any case, expected outline, adversarial item or source text changes.
    """

    dataset_id: str
    version: str
    cases: tuple[EvalCase, ...]
    adversarial: tuple[AdversarialItem, ...]
    source_store: SourceStore
    case_file_store: CaseFileStore
    document_manifest: tuple[str, ...]

    def __post_init__(self) -> None:
        ids = [c.case_id for c in self.cases]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate case_id")
        query_ids = [c.query.query_id for c in self.cases]
        if len(query_ids) != len(set(query_ids)):
            raise ValueError("duplicate query_id")
        adv_ids = [a.item_id for a in self.adversarial]
        if len(adv_ids) != len(set(adv_ids)):
            raise ValueError("duplicate adversarial item_id")

    def fingerprint(self) -> str:
        """SHA-256 over a canonical JSON rendering of the whole dataset (pins the dataset in reports)."""
        payload = {
            "dataset_id": self.dataset_id,
            "version": self.version,
            "cases": [c.model_dump(mode="json") for c in self.cases],
            "adversarial": [a.model_dump(mode="json") for a in self.adversarial],
            "documents": list(self.document_manifest),
        }
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def case(self, case_id: str) -> EvalCase:
        for c in self.cases:
            if c.case_id == case_id:
                return c
        raise KeyError(case_id)
