from enum import StrEnum

from pydantic import Field, model_validator

from legalai_contracts._base import ContractModel


class Verdict(StrEnum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    CONTRADICTED = "contradicted"
    CITATION_INVALID = "citation_invalid"
    NOT_IN_FORCE = "not_in_force"
    WRONG_JURISDICTION = "wrong_jurisdiction"
    CHECK_ERROR = "check_error"


class ReportStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    ABSTAIN = "abstain"


class ItemVerification(ContractModel):
    """Verdict on one verifiable item: a claim, an outline element, or an evidence link."""

    item_id: str = Field(min_length=1)
    verdict: Verdict
    method: str = Field(min_length=1, description="Which check produced the verdict.")
    rationale: str


class VerificationReport(ContractModel):
    """Verification's judgement on one output. PASS only if every item is SUPPORTED (P3)."""

    query_id: str = Field(min_length=1)
    status: ReportStatus
    items: tuple[ItemVerification, ...] = ()
    verifier_version: str = Field(min_length=1)

    @model_validator(mode="after")
    def _fail_closed(self) -> "VerificationReport":
        all_supported = bool(self.items) and all(i.verdict is Verdict.SUPPORTED for i in self.items)
        if self.status is ReportStatus.PASS and not all_supported:
            raise ValueError("PASS requires at least one item and every item SUPPORTED")
        if self.status is ReportStatus.FAIL and all_supported:
            raise ValueError("FAIL with every item SUPPORTED is inconsistent")
        return self
