from bisect import bisect_right
from datetime import date, datetime
from enum import StrEnum
from itertools import pairwise

from pydantic import Field, model_validator

from legalai_contracts._base import JURISDICTION_PATTERN, ContractModel


class DocType(StrEnum):
    CONSTITUTION = "constitution"
    STATUTE = "statute"
    REGULATION = "regulation"
    JUDICIAL_INTERPRETATION = "judicial_interpretation"
    CASE = "case"
    SECONDARY = "secondary"
    OTHER = "other"


class SourceKind(StrEnum):
    """Where a span points: public law (corpus) or confidential case files (casefile)."""

    LAW = "law"
    CASE_FILE = "case_file"


class SourceDocument(ContractModel):
    """One specific version of a legal source, with full provenance (P4, P5)."""

    doc_id: str = Field(min_length=1)
    version_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    jurisdiction: str = Field(pattern=JURISDICTION_PATTERN)
    doc_type: DocType
    language: str = Field(min_length=2, description="BCP 47 tag, e.g. 'en', 'zh-CN'.")
    effective_from: date
    effective_to: date | None = None
    source_uri: str = Field(min_length=1)
    retrieved_at: datetime
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    char_count: int = Field(gt=0)

    @model_validator(mode="after")
    def _validity_interval(self) -> "SourceDocument":
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to precedes effective_from")
        return self

    def in_force_on(self, day: date) -> bool:
        """True if this version was in force on `day` (end date exclusive)."""
        return self.effective_from <= day and (self.effective_to is None or day < self.effective_to)


class CaseDocument(ContractModel):
    """One user-supplied case file (contract, email, invoice, pleading). Confidential (P9)."""

    case_id: str = Field(min_length=1)
    doc_id: str = Field(min_length=1)
    version_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    language: str = Field(min_length=2)
    media_type: str = Field(min_length=1)
    received_at: datetime
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    char_count: int = Field(gt=0)
    page_starts: tuple[int, ...] = Field(
        min_length=1, description="Character offset at which each page begins; first is 0."
    )

    @model_validator(mode="after")
    def _pages(self) -> "CaseDocument":
        starts = self.page_starts
        if starts[0] != 0:
            raise ValueError("page_starts must begin at 0")
        if any(b <= a for a, b in pairwise(starts)) or starts[-1] >= self.char_count:
            raise ValueError("page_starts must be strictly increasing and within char_count")
        return self

    def page_of(self, char_offset: int) -> int:
        """1-based page number containing `char_offset`."""
        if not 0 <= char_offset < self.char_count:
            raise ValueError("offset outside document")
        return bisect_right(self.page_starts, char_offset)


class SourceSpan(ContractModel):
    """An exact character range of one document version, carrying the text it covers."""

    source: SourceKind
    doc_id: str = Field(min_length=1)
    version_id: str = Field(min_length=1)
    start_char: int = Field(ge=0)
    end_char: int = Field(gt=0)
    text: str = Field(min_length=1)
    pinpoint: str | None = Field(
        default=None, description="Human locator such as a section, article or page number."
    )

    @model_validator(mode="after")
    def _offsets_match_text(self) -> "SourceSpan":
        if self.end_char <= self.start_char:
            raise ValueError("end_char must be greater than start_char")
        if len(self.text) != self.end_char - self.start_char:
            raise ValueError("text length does not match offsets")
        return self
