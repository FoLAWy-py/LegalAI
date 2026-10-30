from enum import StrEnum

from pydantic import Field, model_validator

from legalai_contracts._base import ContractModel
from legalai_contracts.answers import Citation, LegalQuery, ModelTrace, PartyRole, TaskType
from legalai_contracts.sources import SourceKind


class Element(ContractModel):
    """Something that must be proved for the cause of action, grounded in law (ADR-0005)."""

    element_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    legal_basis: tuple[Citation, ...] = Field(min_length=1)
    burden_on: PartyRole | None = None

    @model_validator(mode="after")
    def _law_only(self) -> "Element":
        if any(c.span.source is not SourceKind.LAW for c in self.legal_basis):
            raise ValueError("element legal_basis must cite law sources")
        return self


class EvidenceRelation(StrEnum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"


class EvidenceLink(ContractModel):
    """A case-file passage mapped to one element, with its purpose (证明目的)."""

    link_id: str = Field(min_length=1)
    element_id: str = Field(min_length=1)
    citation: Citation
    relation: EvidenceRelation
    purpose: str = Field(min_length=1)

    @model_validator(mode="after")
    def _case_file_only(self) -> "EvidenceLink":
        if self.citation.span.source is not SourceKind.CASE_FILE:
            raise ValueError("evidence link must cite a case file")
        return self


class GapKind(StrEnum):
    NO_EVIDENCE = "no_evidence"
    ONLY_CONTRADICTING = "only_contradicting"
    INSUFFICIENT = "insufficient"


class Gap(ContractModel):
    element_id: str = Field(min_length=1)
    kind: GapKind
    description: str = Field(min_length=1)


class EvidenceOutline(ContractModel):
    """Proof chart with gaps. Every element is covered by a supporting link or a gap (P3)."""

    query: LegalQuery
    cause_of_action: str
    elements: tuple[Element, ...] = ()
    links: tuple[EvidenceLink, ...] = ()
    gaps: tuple[Gap, ...] = ()
    abstained: bool = False
    abstain_reason: str | None = None
    traces: tuple[ModelTrace, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _consistent(self) -> "EvidenceOutline":
        if self.query.task_type is not TaskType.EVIDENCE_OUTLINE:
            raise ValueError("query task_type must be evidence_outline")
        if self.abstained:
            if not self.abstain_reason:
                raise ValueError("abstention requires abstain_reason")
            return self
        if not self.elements or not self.cause_of_action:
            raise ValueError("non-abstaining outline needs cause_of_action and elements")
        element_ids = [e.element_id for e in self.elements]
        all_ids = element_ids + [link.link_id for link in self.links]
        if len(all_ids) != len(set(all_ids)):
            raise ValueError("duplicate element_id or link_id")
        known = set(element_ids)
        referenced = {link.element_id for link in self.links} | {gap.element_id for gap in self.gaps}
        dangling = referenced - known
        if dangling:
            raise ValueError(f"links/gaps reference unknown elements {sorted(dangling)}")
        supported = {link.element_id for link in self.links if link.relation is EvidenceRelation.SUPPORTS}
        uncovered = known - supported - {g.element_id for g in self.gaps}
        if uncovered:
            raise ValueError(f"elements without supporting evidence or gap: {sorted(uncovered)}")
        return self
