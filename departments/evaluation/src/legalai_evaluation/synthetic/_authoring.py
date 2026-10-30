"""Authoring helpers for synthetic `ZZ` data: offsets, hashes and page maps are computed, never typed."""

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from legalai_contracts import (
    CaseDocument,
    Citation,
    DocType,
    SourceDocument,
    SourceKind,
    SourceSpan,
)
from legalai_evaluation.fakes import IndexedSpan

SYNTHETIC_MARKER = "SYNTHETIC"
AUTHORED_AT = datetime(2026, 10, 30, tzinfo=UTC)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _unique_offset(haystack: str, needle: str, where: str) -> int:
    first = haystack.find(needle)
    if first < 0:
        raise ValueError(f"quote {needle!r} not found in {where}")
    if haystack.find(needle, first + 1) >= 0:
        raise ValueError(f"quote {needle!r} is ambiguous in {where}")
    return first


@dataclass(frozen=True)
class Article:
    """One provision of a fictional statute: a pinpoint, its full text, and search keywords."""

    pinpoint: str
    text: str
    keywords: tuple[str, ...] = ()


@dataclass(frozen=True)
class LawDoc:
    """A built fictional law document version with one span per article."""

    document: SourceDocument
    text: str
    articles: dict[str, SourceSpan] = field(default_factory=dict)
    keywords: dict[str, tuple[str, ...]] = field(default_factory=dict)

    @property
    def key(self) -> str:
        return f"{self.document.doc_id}@{self.document.version_id}"

    def cite(self, pinpoint: str, quote: str) -> Citation:
        span = self.articles[pinpoint]
        _unique_offset(span.text, quote, f"{self.key} {pinpoint}")
        return Citation(span=span, quote=quote)

    def indexed(self) -> list[IndexedSpan]:
        return [IndexedSpan(span, self.keywords[p]) for p, span in self.articles.items()]


def make_law_doc(
    *,
    doc_id: str,
    version_id: str,
    title: str,
    jurisdiction: str,
    doc_type: DocType,
    language: str,
    effective_from: date,
    effective_to: date | None,
    articles: Sequence[Article],
) -> LawDoc:
    if SYNTHETIC_MARKER not in title:
        raise ValueError("synthetic law titles must contain SYNTHETIC")
    if not jurisdiction.startswith("ZZ"):
        raise ValueError("synthetic law must use the fictional jurisdiction ZZ")
    parts = [title + "\n"]
    offset = len(parts[0])
    spans: dict[str, SourceSpan] = {}
    keywords: dict[str, tuple[str, ...]] = {}
    for art in articles:
        if art.pinpoint in spans:
            raise ValueError(f"duplicate pinpoint {art.pinpoint}")
        spans[art.pinpoint] = SourceSpan(
            source=SourceKind.LAW,
            doc_id=doc_id,
            version_id=version_id,
            start_char=offset,
            end_char=offset + len(art.text),
            text=art.text,
            pinpoint=art.pinpoint,
        )
        keywords[art.pinpoint] = art.keywords
        parts.append(art.text + "\n")
        offset += len(art.text) + 1
    text = "".join(parts)
    document = SourceDocument(
        doc_id=doc_id,
        version_id=version_id,
        title=title,
        jurisdiction=jurisdiction,
        doc_type=doc_type,
        language=language,
        effective_from=effective_from,
        effective_to=effective_to,
        source_uri=f"synthetic://zz/law/{doc_id}/{version_id}",
        retrieved_at=AUTHORED_AT,
        content_sha256=sha256_text(text),
        char_count=len(text),
    )
    return LawDoc(document=document, text=text, articles=spans, keywords=keywords)


@dataclass(frozen=True)
class CaseFile:
    """A built fictional case file with one span per non-empty line."""

    document: CaseDocument
    text: str
    passages: tuple[SourceSpan, ...]

    def cite(self, quote: str) -> Citation:
        start = _unique_offset(self.text, quote, self.document.doc_id)
        for span in self.passages:
            if span.start_char <= start and start + len(quote) <= span.end_char:
                return Citation(span=span, quote=quote)
        raise ValueError(f"quote {quote!r} crosses a line boundary in {self.document.doc_id}")

    def indexed(self) -> list[IndexedSpan]:
        return [IndexedSpan(span) for span in self.passages]


def make_case_file(
    *, case_id: str, doc_id: str, title: str, language: str, pages: Sequence[Sequence[str]]
) -> CaseFile:
    """Build a case file whose pages are lists of lines; each line becomes a citable passage."""
    if SYNTHETIC_MARKER not in title:
        raise ValueError("synthetic case-file titles must contain SYNTHETIC")
    text = ""
    page_starts: list[int] = []
    passages: list[SourceSpan] = []
    for page_number, lines in enumerate(pages, start=1):
        page_starts.append(len(text))
        for line in lines:
            if not line or "\n" in line:
                raise ValueError("each line must be non-empty and single-line")
            passages.append(
                SourceSpan(
                    source=SourceKind.CASE_FILE,
                    doc_id=doc_id,
                    version_id="v1",
                    start_char=len(text),
                    end_char=len(text) + len(line),
                    text=line,
                    pinpoint=f"p. {page_number}",
                )
            )
            text += line + "\n"
    document = CaseDocument(
        case_id=case_id,
        doc_id=doc_id,
        version_id="v1",
        title=title,
        language=language,
        media_type="text/plain",
        received_at=AUTHORED_AT,
        content_sha256=sha256_text(text),
        char_count=len(text),
        page_starts=tuple(page_starts),
    )
    return CaseFile(document=document, text=text, passages=tuple(passages))
