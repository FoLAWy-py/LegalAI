---
id: STD-LEGAL
owner: architecture
status: active
updated: 2026-10-30
---

# Legal Content Standard

## 1. Jurisdictions

- Codes follow ISO 3166-1 alpha-2, optionally with a subdivision: `US`, `US-CA`, `CN`, `GB`, `DE-BY`.
- **`ZZ` is the fictional jurisdiction.** All synthetic test data uses `ZZ` so it can never be
  mistaken for real law. Real jurisdiction codes in test data are allowed only for real, sourced
  documents with full provenance.

## 2. Sources

Each source document MUST have: stable `doc_id`, `version_id`, `jurisdiction`, `doc_type`,
`effective_from` (and `effective_to` if no longer in force), `source_uri`, `retrieved_at`,
`content_sha256`. Only sources from origins approved in `departments/corpus/CHARTER.md`
(official gazettes, court sites, licensed databases) count as authoritative.

## 3. Citations

- Machine form: `SourceSpan` (doc_id + version_id + char offsets + text) and an exact `quote`.
- Human form: the jurisdiction's customary citation style (for example Bluebook for US), produced from
  metadata, never typed by a model from memory.
- A model MUST NOT produce a citation that does not come from a retrieved span.

## 4. Synthetic and fixture data

- Synthetic documents set `jurisdiction: ZZ` and include the marker `SYNTHETIC` in the title.
- Never copy real user or client documents into the repository.
- Real public legal texts may be used as fixtures only with provenance and when licensing allows it.

## 5. Output language to users

- State the jurisdiction, as-of date and scope of every answer.
- Mark each claim's verification status. Unverified claims are not shown by default.
- Do not present output as legal advice. The disclaimer text is owned by `interface`.
- When abstaining, say why (no source, conflicting sources, out of scope, outdated).
