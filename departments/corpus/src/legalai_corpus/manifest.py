"""Ingestion manifests: which official files make which document versions, and the evidence for every date.

A manifest is data written by corpus from official sources. It never contains legal text. Dates are
accepted only with evidence: exact sentences that ingestion re-finds in the extracted official text, at
least one of which renders the date itself (see `date_renderings`).
"""

import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from legalai_contracts import DocType
from legalai_corpus.extract import HtmlRule, PdfRule
from legalai_corpus.structure import PROFILES

SAFE_ID = r"^[a-z0-9][a-z0-9._-]*$"


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class HtmlRuleSpec(_Model):
    container_attr: tuple[str, str]
    encoding: str = "utf-8"
    start_marker: str | None = None
    end_marker: str | None = None

    def rule(self) -> HtmlRule:
        return HtmlRule(self.container_attr, self.encoding, self.start_marker, self.end_marker)


class PdfRuleSpec(_Model):
    drop_line_patterns: tuple[str, ...] = ()
    start_marker: str | None = None
    end_marker: str | None = None
    indent_chars: float = 1.5

    def rule(self) -> PdfRule:
        return PdfRule(self.drop_line_patterns, self.start_marker, self.end_marker, self.indent_chars)


class SourceFile(_Model):
    """One official file (page or PDF) and how to extract its text."""

    key: str = Field(pattern=SAFE_ID)
    url: str = Field(min_length=1)
    format: Literal["html", "pdf"]
    html: HtmlRuleSpec | None = None
    pdf: PdfRuleSpec | None = None
    compat_policy: Literal["reject", "map-to-unified"] = Field(
        default="reject",
        description="Handling of Kangxi/CJK radical or compatibility code points (normalization.md N6).",
    )

    @model_validator(mode="after")
    def _rule_matches_format(self) -> "SourceFile":
        if (self.format == "html") != (self.html is not None) or (self.format == "pdf") != (
            self.pdf is not None
        ):
            raise ValueError(f"source {self.key}: exactly the rule for format {self.format!r} is required")
        return self


class DateEvidence(_Model):
    """Exact sentences from an official source that establish a date."""

    source: str = Field(pattern=SAFE_ID)
    quotes: tuple[str, ...] = Field(min_length=1)
    note: str | None = None


class VersionSpec(_Model):
    doc_id: str = Field(pattern=SAFE_ID)
    version_id: str = Field(pattern=SAFE_ID)
    title: str = Field(min_length=1)
    jurisdiction: str
    doc_type: DocType
    language: str = Field(min_length=2)
    issuer: str = Field(min_length=1)
    document_number: str | None = None
    text_source: str = Field(pattern=SAFE_ID)
    structure_profile: str
    effective_from: date
    effective_from_evidence: tuple[DateEvidence, ...] = Field(min_length=1)
    effective_to: date | None = None
    effective_to_evidence: tuple[DateEvidence, ...] = ()
    validity_note: str = Field(
        min_length=1, description="What was checked to set effective_to (or to leave it open)."
    )

    @model_validator(mode="after")
    def _evidence(self) -> "VersionSpec":
        if self.structure_profile not in PROFILES:
            raise ValueError(f"unknown structure profile {self.structure_profile!r}")
        if self.effective_to is not None and not self.effective_to_evidence:
            raise ValueError(f"{self.doc_id}/{self.version_id}: effective_to needs evidence")
        if self.effective_to is None and self.effective_to_evidence:
            raise ValueError(f"{self.doc_id}/{self.version_id}: effective_to evidence without a date")
        return self


class KnownGap(_Model):
    """Something in scope that corpus could not obtain authoritatively. Reported, never filled in."""

    subject: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class Manifest(_Model):
    manifest_id: str = Field(pattern=SAFE_ID)
    sources: tuple[SourceFile, ...] = ()
    versions: tuple[VersionSpec, ...] = ()
    gaps: tuple[KnownGap, ...] = ()

    @model_validator(mode="after")
    def _references(self) -> "Manifest":
        keys = [s.key for s in self.sources]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate source keys")
        ids = [(v.doc_id, v.version_id) for v in self.versions]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate (doc_id, version_id)")
        for v in self.versions:
            refs = [v.text_source] + [e.source for e in v.effective_from_evidence + v.effective_to_evidence]
            missing = [r for r in refs if r not in keys]
            if missing:
                raise ValueError(f"{v.doc_id}/{v.version_id}: unknown source keys {missing}")
        return self

    def source(self, key: str) -> SourceFile:
        return next(s for s in self.sources if s.key == key)


_CN_DIGITS = "〇一二三四五六七八九"


def _cn_year(y: int) -> str:
    return "".join(_CN_DIGITS[int(d)] for d in str(y))


def _cn_small(n: int) -> str:
    if n < 10:
        return _CN_DIGITS[n]
    tens, ones = divmod(n, 10)
    return ("" if tens == 1 else _CN_DIGITS[tens]) + "十" + ("" if ones == 0 else _CN_DIGITS[ones])


_MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


def date_renderings(day: date, language: str) -> tuple[str, ...]:
    """The textual forms in which an official source may state `day` (used to tie a date to its quote)."""
    if language.lower().startswith("zh"):
        return (
            f"{day.year}年{day.month}月{day.day}日",
            f"{_cn_year(day.year)}年{_cn_small(day.month)}月{_cn_small(day.day)}日",
        )
    return (f"{_MONTHS[day.month - 1]} {day.day}, {day.year}", day.isoformat())


def quotes_render_date(quotes: tuple[str, ...], day: date, language: str) -> bool:
    forms = date_renderings(day, language)
    collapsed = [re.sub(r"\s+", "", q) for q in quotes]
    return any(form in q for form in forms for q in collapsed)
