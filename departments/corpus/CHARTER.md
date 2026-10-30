---
id: CHARTER-CORPUS
owner: corpus
status: active
updated: 2026-10-30
---

# Corpus Charter

## Mission
Provide authoritative, versioned, provenance-complete legal source text.

## Owns
- Acquisition from approved origins (list below), parsing (HTML/PDF/XML) into clean text that keeps
  structure (articles, sections, paragraphs) so pinpoints can be derived.
- Version management: each amendment is a new `version_id` with its own validity interval.
- Storage of document text and metadata; the `SourceStore` implementation.
- Integrity: `content_sha256` of stored text; detection of upstream changes.

## Does not own
Indexing or ranking (retrieval). Deciding what is relevant to a query (retrieval / reasoning).

## Interfaces
- **Consumes:** `SourceDocument`, `SourceSpan`.
- **Provides:** a `SourceStore` implementation; an ingestion API producing `SourceDocument`s.

## v1 scope (ADR-0005)
- **CN:** Civil Code (contract book), Civil Procedure Law, SPC provisions on evidence in civil procedure, related judicial interpretations — all versions with effective dates.
- **US:** Federal Rules of Evidence, Federal Rules of Civil Procedure; the chosen state's (D8) contract statutes, UCC Article 2 enactment and public case law.

## Approved origins
Policy (D3): public sources downloaded locally. An origin becomes **approved** only after corpus records,
in `docs/origins.md`, its terms of use / robots policy, rate limits, update cadence, and how versions and
effective dates are obtained. Downloads must respect terms and rate limits.

Candidates to assess (not yet approved):

| Jurisdiction | Origin | Content |
|---|---|---|
| US | govinfo.gov (GPO) | U.S. Code, CFR, Federal Register, court opinions collection |
| US | ecfr.gov | Current and point-in-time CFR |
| US | uscode.house.gov | U.S. Code with release points |
| US | CourtListener (Free Law Project) | Case law and bulk data |
| CN | flk.npc.gov.cn (国家法律法规数据库) | Laws, administrative regulations, judicial interpretations |
| CN | court.gov.cn (最高人民法院) | Judicial interpretations, guiding cases (指导性案例) |
| CN | wenshu.court.gov.cn (中国裁判文书网) | Judgments — access restrictions and terms MUST be reviewed before any use |

## Quality bars
- 100% of documents have complete provenance fields; ingestion rejects incomplete records.
- `get_text` returns exactly the stored characters for any offset range (byte-for-byte reproducible).
- Parsing fidelity measured on a sampled set against the official rendering (target set by evaluation).

## Reliability duties
P4 (validity intervals), P5 (provenance, hashing), P1 (authoritative text that verification re-reads).
Never "clean up" legal wording (no spelling fixes, no paraphrase); normalization rules are documented in `docs/`.
