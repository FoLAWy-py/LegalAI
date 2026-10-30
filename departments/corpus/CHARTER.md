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
- **Provides** (public API in `legalai_corpus.__all__`):
  - `FileSourceStore(data_dir)` implements the `SourceStore` port. Extras: `full_text`, `get_units`
    (pinpoint offsets), `get_provenance`, `versions`, `verify_all`.
  - The ingestion API: `load_manifest`, `ingest_manifest`, `PoliteFetcher`, `RawStore`, the origin registry
    `ORIGINS`, and the error types.
  - Operator CLI: `python -m legalai_corpus {fetch,ingest,verify,spotcheck} --data-dir D`.

## v1 scope (ADR-0006, which supersedes ADR-0005)
- **CN:** criminal law with a financial-crime focus, exactly as listed in REQ-PMO-0002 §2.2. All versions have
  effective dates taken from official sources.
- **US:** deferred to a later REQ (federal rules, then the D8 state).

## Approved origins
Policy (D3): public sources downloaded locally. An origin becomes **approved** only after corpus records,
in `docs/origins.md`, its terms of use / robots policy, rate limits, update cadence, and how versions and
effective dates are obtained. Downloads must respect terms and rate limits.

The current decision for each origin, with its evidence, is in `docs/origins.md` (mirrored in code by
`legalai_corpus.origins.ORIGINS`). As of 2026-10-30 no origin is approved. The charter candidates below
were all assessed there, together with www.npc.gov.cn, www.csrc.gov.cn, www.spp.gov.cn and www.uscourts.gov.

Charter candidates:

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
Never "clean up" legal wording (no spelling fixes, no paraphrase); normalization rules are documented in `docs/normalization.md`.
