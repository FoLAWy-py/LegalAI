"""Ingestion: manifest -> official raw files -> mechanically extracted text -> stored SourceDocument versions.

For each version: the text source is fetched (approved origins only, cached), extracted by its rule,
structured, and every date-evidence quote is re-found verbatim in the extracted official text of its
source; at least one quote must render the date itself. Any failure stops that version (fail closed).
"""

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from legalai_contracts import SourceDocument
from legalai_corpus.extract import (
    NORMALIZATION_VERSION,
    extract_html,
    extract_pdf,
    map_compat_to_unified,
    scan_compat,
)
from legalai_corpus.fetch import FetchOutcome, FetchResult, PoliteFetcher
from legalai_corpus.manifest import DateEvidence, Manifest, SourceFile, VersionSpec, quotes_render_date
from legalai_corpus.store import FileSourceStore, text_sha256
from legalai_corpus.structure import derive_units


class IngestError(Exception):
    """One or more versions could not be ingested authoritatively. The message lists them all."""


def load_manifest(path: Path) -> Manifest:
    return Manifest.model_validate_json(path.read_text(encoding="utf-8"))


@dataclass
class _Sources:
    manifest: Manifest
    fetcher: PoliteFetcher
    refresh: bool
    fetched: dict[str, FetchResult] = field(default_factory=dict)
    texts: dict[str, str] = field(default_factory=dict)
    compat: dict[str, dict[str, object]] = field(default_factory=dict)

    def fetch(self, key: str) -> FetchResult:
        if key not in self.fetched:
            self.fetched[key] = self.fetcher.fetch(self.manifest.source(key).url, refresh=self.refresh)
        return self.fetched[key]

    def text(self, key: str) -> str:
        if key not in self.texts:
            source = self.manifest.source(key)
            text = extract_source(source, self.raw(key))
            found = scan_compat(text)
            changes: list[dict[str, object]] = []
            if found and source.compat_policy == "reject":
                raise IngestError(
                    f"source {key}: radical/compatibility code points found {found}; "
                    "use an HTML/DOCX rendering or set compat_policy explicitly (normalization.md N6)"
                )
            if found:
                text, changes = map_compat_to_unified(text)
            self.compat[key] = {"policy": source.compat_policy, "found": found, "changes": changes}
            self.texts[key] = text
        return self.texts[key]

    def raw(self, key: str) -> bytes:
        return self.fetcher.raw.read_object(self.fetch(key).record.sha256)


def extract_source(source: SourceFile, raw: bytes) -> str:
    """Apply the source's extraction rule to its raw bytes."""
    if source.format == "html":
        assert source.html is not None
        return extract_html(raw, source.html.rule())
    assert source.pdf is not None
    return extract_pdf(raw, source.pdf.rule())


def _check_evidence(
    sources: _Sources, spec: VersionSpec, label: str, evidence: tuple[DateEvidence, ...], day: date
) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    all_quotes: list[str] = []
    for ev in evidence:
        text = sources.text(ev.source)
        for quote in ev.quotes:
            if quote not in text:
                raise IngestError(f"{label}: quote not found verbatim in source {ev.source}: {quote!r}")
        all_quotes.extend(ev.quotes)
        record = sources.fetch(ev.source).record
        out.append(
            {
                "source_key": ev.source,
                "url": record.final_url,
                "raw_sha256": record.sha256,
                "quotes": list(ev.quotes),
                "note": ev.note,
            }
        )
    if not quotes_render_date(tuple(all_quotes), day, spec.language):
        raise IngestError(f"{label}: no evidence quote states the date {day}")
    return out


def ingest_version(sources: _Sources, spec: VersionSpec, store: FileSourceStore) -> str:
    """Ingest one version; returns 'stored' or 'unchanged'. Raises on any failure."""
    label = f"{spec.doc_id}/{spec.version_id}"
    fetched = sources.fetch(spec.text_source)
    text = sources.text(spec.text_source)
    units = derive_units(text, spec.structure_profile)
    from_ev = _check_evidence(sources, spec, label, spec.effective_from_evidence, spec.effective_from)
    to_ev = (
        _check_evidence(sources, spec, label, spec.effective_to_evidence, spec.effective_to)
        if spec.effective_to is not None
        else []
    )
    record = fetched.record
    document = SourceDocument(
        doc_id=spec.doc_id,
        version_id=spec.version_id,
        title=spec.title,
        jurisdiction=spec.jurisdiction,
        doc_type=spec.doc_type,
        language=spec.language,
        effective_from=spec.effective_from,
        effective_to=spec.effective_to,
        source_uri=record.final_url,
        retrieved_at=record.first_retrieved_at,
        content_sha256=text_sha256(text),
        char_count=len(text),
    )
    source = sources.manifest.source(spec.text_source)
    provenance: dict[str, object] = {
        "manifest_id": sources.manifest.manifest_id,
        "issuer": spec.issuer,
        "document_number": spec.document_number,
        "raw": record.to_json(),
        "format": source.format,
        "extraction_rule": json.loads(source.model_dump_json()),
        "normalization_version": NORMALIZATION_VERSION,
        "compat_codepoints": sources.compat[spec.text_source],
        "structure_profile": spec.structure_profile,
        "effective_from_evidence": from_ev,
        "effective_to_evidence": to_ev,
        "validity_note": spec.validity_note,
    }
    written = store.put(document, text, units, provenance)
    return "stored" if written else "unchanged"


def ingest_manifest(
    manifest: Manifest, fetcher: PoliteFetcher, store: FileSourceStore, refresh: bool = False
) -> dict[str, object]:
    """Ingest every version of `manifest`. Returns a report; raises IngestError listing all failures."""
    sources = _Sources(manifest, fetcher, refresh)
    results: dict[str, str] = {}
    errors: dict[str, str] = {}
    for spec in manifest.versions:
        label = f"{spec.doc_id}/{spec.version_id}"
        try:
            results[label] = ingest_version(sources, spec, store)
        except Exception as err:  # noqa: BLE001 - collected and re-raised below, never swallowed
            errors[label] = f"{type(err).__name__}: {err}"
    changed = [k for k, r in sources.fetched.items() if r.outcome is FetchOutcome.CHANGED]
    report: dict[str, object] = {
        "manifest_id": manifest.manifest_id,
        "versions": results,
        "upstream_changed_sources": changed,
        "fetch_outcomes": {k: r.outcome.value for k, r in sources.fetched.items()},
        "known_gaps": [g.model_dump() for g in manifest.gaps],
    }
    if errors:
        raise IngestError(json.dumps({"errors": errors, **report}, ensure_ascii=False, indent=1))
    return report
