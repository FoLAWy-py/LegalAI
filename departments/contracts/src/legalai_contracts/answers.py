from datetime import date
from enum import StrEnum

from pydantic import Field, model_validator

from legalai_contracts._base import JURISDICTION_PATTERN, ContractModel
from legalai_contracts.sources import SourceKind, SourceSpan


class TaskType(StrEnum):
    RESEARCH_QA = "research_qa"
    EVIDENCE_OUTLINE = "evidence_outline"


class PartyRole(StrEnum):
    """The side of a case a user acts for, or that bears a burden stated by law.

    These are procedural labels, not legal conclusions. Which party bears what burden is never
    inferred from the role; it comes only from cited law (ADR-0006).

    - `PLAINTIFF`: the party bringing a civil claim.
    - `DEFENDANT`: the party a civil claim is brought against, or the accused in a criminal case.
    - `PROSECUTION`: the party bringing the criminal charge (added in contracts 0.3.0, ADR-0006).
    """

    PLAINTIFF = "plaintiff"
    DEFENDANT = "defendant"
    PROSECUTION = "prosecution"


class LegalQuery(ContractModel):
    """A user request. Jurisdiction and as-of date are mandatory (P4).

    For EVIDENCE_OUTLINE, `text` states the cause of action or the charged offence and the facts
    in the user's words, and `case_id` / `party_role` are required. In a criminal case,
    `party_role` is `PROSECUTION` or `DEFENDANT` (ADR-0006).

    `as_of` is the reference date of every law citation that names no other one. An evidence outline may
    declare further reference dates (`EvidenceOutline.reference_dates`, ADR-0007 §1); which date governs
    is a legal question answered from cited law, never by this contract.
    """

    query_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    jurisdiction: str = Field(pattern=JURISDICTION_PATTERN)
    as_of: date
    response_language: str = Field(min_length=2, description="BCP 47 tag for the output (ADR-0004).")
    task_type: TaskType = TaskType.RESEARCH_QA
    case_id: str | None = None
    party_role: PartyRole | None = None

    @model_validator(mode="after")
    def _outline_needs_case(self) -> "LegalQuery":
        if self.task_type is TaskType.EVIDENCE_OUTLINE and (not self.case_id or self.party_role is None):
            raise ValueError("evidence_outline query requires case_id and party_role")
        return self


class Citation(ContractModel):
    """A span plus the exact words relied on. The quote must occur verbatim in the span (P1).

    `reference_date_id` (contracts 0.4.0, ADR-0007 §1) names the `ReferenceDate` of the enclosing
    `EvidenceOutline` for which this law citation's version was selected. `None` means the query's
    `as_of`, exactly as before 0.4.0. Only law citations may set it, and only inside an outline that
    declares that reference date. It records which date the version was chosen for; it does not say
    that this date is the legally correct one. That is cited in the reference date's `basis`.
    """

    span: SourceSpan
    quote: str = Field(min_length=1)
    reference_date_id: str | None = Field(
        default=None,
        min_length=1,
        description="Id of the outline's ReferenceDate this law version was selected for; None = as_of.",
    )

    @model_validator(mode="after")
    def _quote_in_span(self) -> "Citation":
        if self.quote not in self.span.text:
            raise ValueError("quote does not appear verbatim in span text")
        if self.reference_date_id is not None and self.span.source is not SourceKind.LAW:
            raise ValueError("only law citations may carry a reference_date_id")
        return self


class ClaimKind(StrEnum):
    LEGAL_RULE = "legal_rule"
    FACT = "fact"
    INFERENCE = "inference"


class Claim(ContractModel):
    """One atomic assertion. Rules and facts need citations; inferences name their premises."""

    claim_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    kind: ClaimKind
    citations: tuple[Citation, ...] = ()
    derived_from: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _grounded(self) -> "Claim":
        if self.kind is ClaimKind.INFERENCE:
            if not self.derived_from:
                raise ValueError("inference claim must list derived_from claim ids")
        elif not self.citations:
            raise ValueError(f"{self.kind.value} claim must have at least one citation")
        return self


class ModelTrace(ContractModel):
    """What produced an output, so it can be reproduced and audited (P5).

    Token counts (contracts 0.4.0, ADR-0007 §2) are totals over every model call this trace covers, as
    reported by the provider. `None` means not reported; it is never a stand-in for 0. Cost is not
    stored: it is derived from the token counts and a pinned price table by whoever reports it.
    """

    model: str = Field(min_length=1)
    prompt_id: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    temperature: float = Field(ge=0)
    source_versions: tuple[str, ...] = Field(
        default=(), description="'doc_id@version_id' for every document consulted."
    )
    input_tokens: int | None = Field(
        default=None, ge=0, description="Prompt/input tokens reported by the provider; None = not reported."
    )
    output_tokens: int | None = Field(
        default=None,
        ge=0,
        description="Completion/output tokens reported by the provider; None = not reported.",
    )


class DraftAnswer(ContractModel):
    """Reasoning's output. Unverified by definition until a VerificationReport passes."""

    query: LegalQuery
    claims: tuple[Claim, ...] = ()
    answer_text: str
    abstained: bool = False
    abstain_reason: str | None = None
    traces: tuple[ModelTrace, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _consistent(self) -> "DraftAnswer":
        if any(c.reference_date_id is not None for claim in self.claims for c in claim.citations):
            # A draft declares no reference dates (contracts 0.4.0), so any id would dangle.
            raise ValueError("draft answer citations cannot carry reference_date_id")
        if self.abstained:
            if not self.abstain_reason:
                raise ValueError("abstention requires abstain_reason")
            return self
        if not self.claims:
            raise ValueError("non-abstaining answer must contain claims")
        ids = [c.claim_id for c in self.claims]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate claim_id")
        known = set(ids)
        for claim in self.claims:
            missing = set(claim.derived_from) - known
            if missing:
                raise ValueError(f"claim {claim.claim_id} derives from unknown ids {sorted(missing)}")
        return self
