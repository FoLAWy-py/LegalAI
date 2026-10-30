from collections.abc import Iterator
from datetime import date
from enum import StrEnum

from pydantic import Field, model_validator

from legalai_contracts._base import ContractModel
from legalai_contracts.answers import Citation, LegalQuery, ModelTrace, PartyRole, TaskType
from legalai_contracts.sources import SourceKind


class Element(ContractModel):
    """Something that must be proved for the cause of action or the charged offence, grounded in law.

    In a criminal outline, each element is one element of the charged offence (犯罪构成), as
    stated in the cited `legal_basis` (ADR-0006). `burden_on` is set only when that cited law states
    who bears the burden for this element; otherwise it is `None`. It is never filled from a default
    or from memory.

    Each `legal_basis` citation may name the outline reference date its law version was selected for
    (`Citation.reference_date_id`, ADR-0007 §1). Citations of one element may name different dates.
    """

    element_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    legal_basis: tuple[Citation, ...] = Field(min_length=1)
    burden_on: PartyRole | None = None

    @model_validator(mode="after")
    def _law_only(self) -> "Element":
        if any(c.span.source is not SourceKind.LAW for c in self.legal_basis):
            raise ValueError("element legal_basis must cite law sources")
        return self


class ReferenceDateKind(StrEnum):
    """What a reference date is, as a matter of fact. It does not say which date's law governs.

    - `CONDUCT`: a date within, or the date of, the conduct at issue.
    - `ADJUDICATION`: the date of a judgment or decision, actual or as assumed for the outline.
    - `OTHER`: any other date; `ReferenceDate.description` says what it is.
    """

    CONDUCT = "conduct"
    ADJUDICATION = "adjudication"
    OTHER = "other"


class ReferenceDate(ContractModel):
    """A date for which law versions cited in an outline were selected (contracts 0.4.0, ADR-0007 §1).

    The contract carries the date and the cited basis for using it, never the rule on which date
    governs. `basis` cites the law relied on for selecting law as of `day`; `evidence` cites the case-file
    passages that state the date or period, where there are any. Verification checks every law citation
    that names this reference date against `day`.

    `day` is the single date the cited versions were selected for. When the fact is a period (for
    example conduct running over several years), `period_start` / `period_end` record it and `day` lies
    inside it; choosing `day` within the period is itself part of what `basis` must support.
    """

    reference_id: str = Field(min_length=1)
    kind: ReferenceDateKind
    day: date
    period_start: date | None = None
    period_end: date | None = None
    description: str = Field(min_length=1, description="What the date is, stated as fact.")
    basis: tuple[Citation, ...] = Field(
        min_length=1, description="Law relied on for selecting law as of `day` (P1)."
    )
    evidence: tuple[Citation, ...] = Field(
        default=(), description="Case-file passages stating the date or period."
    )

    @model_validator(mode="after")
    def _consistent(self) -> "ReferenceDate":
        if (self.period_start is None) != (self.period_end is None):
            raise ValueError("period_start and period_end must be given together")
        if self.period_start is not None and self.period_end is not None:
            if self.period_end < self.period_start:
                raise ValueError("period_end precedes period_start")
            if not self.period_start <= self.day <= self.period_end:
                raise ValueError("day must lie within the period")
        if any(c.span.source is not SourceKind.LAW for c in self.basis):
            raise ValueError("reference date basis must cite law sources")
        if any(c.span.source is not SourceKind.CASE_FILE for c in self.evidence):
            raise ValueError("reference date evidence must cite case files")
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
    """Proof chart with gaps. Every element is covered by a supporting link or a gap (P3).

    Civil case: elements of the cause of action. Criminal case: elements of the charged offence.
    A defence or justification appears as `CONTRADICTS` links on the element(s) it would negate. It is
    not an element of its own (ADR-0006).

    `reference_dates` (contracts 0.4.0, ADR-0007 §1) declares every date other than `query.as_of` for
    which a cited law version was selected. Each id is unique, every `Citation.reference_date_id` in the
    outline names a declared date, and every declared date is named by at least one citation. Law
    citations that name no reference date stand for `query.as_of`. With no reference dates the outline
    behaves exactly as in 0.3.0.
    """

    query: LegalQuery
    cause_of_action: str = Field(
        description="The civil cause of action or, in a criminal case, the charged offence."
    )
    elements: tuple[Element, ...] = ()
    links: tuple[EvidenceLink, ...] = ()
    gaps: tuple[Gap, ...] = ()
    abstained: bool = False
    abstain_reason: str | None = None
    traces: tuple[ModelTrace, ...] = Field(min_length=1)
    reference_dates: tuple[ReferenceDate, ...] = ()

    def _all_citations(self) -> Iterator[Citation]:
        for element in self.elements:
            yield from element.legal_basis
        for link in self.links:
            yield link.citation
        for ref in self.reference_dates:
            yield from ref.basis
            yield from ref.evidence

    def _check_reference_dates(self) -> None:
        declared = [r.reference_id for r in self.reference_dates]
        if len(declared) != len(set(declared)):
            raise ValueError("duplicate reference_id")
        used = {c.reference_date_id for c in self._all_citations() if c.reference_date_id is not None}
        dangling = used - set(declared)
        if dangling:
            raise ValueError(f"citations name undeclared reference dates {sorted(dangling)}")
        unused = set(declared) - used
        if unused:
            raise ValueError(f"reference dates named by no citation {sorted(unused)}")

    @model_validator(mode="after")
    def _consistent(self) -> "EvidenceOutline":
        if self.query.task_type is not TaskType.EVIDENCE_OUTLINE:
            raise ValueError("query task_type must be evidence_outline")
        self._check_reference_dates()
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
