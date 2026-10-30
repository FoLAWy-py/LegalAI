---
id: ADR-0007
title: Contracts 0.4.0 — reference dates, token usage, store errors, hash semantics, verification traces
owner: architecture
status: accepted
deciders: [architecture]
updated: 2026-10-30
---

# ADR-0007: Contracts 0.4.0 — closing the Wave 1 contract gaps

## Context
Wave 1 deliveries worked around five gaps in contracts 0.3.0 (REQ-PMO-0010 §1):

1. One `LegalQuery.as_of` cannot express a criminal case where the conduct and the judgment fall under different
   law versions (ADR-0006 §6.2). The pilot (REQ-PMO-0008) needs this. REQ-PMO-0008 §1 records that its conduct
   ran from 2014 to 2018 and its judgments came in 2021 [taken from the REQ, not from a law source].
2. `ModelTrace` has no token usage, which REQ-ARCH-0001 AC2 needs for cost comparison.
3. The store ports define no "not found" error. Verification maps `LookupError` to `CITATION_INVALID` and anything
   else to `CHECK_ERROR`; casefile and corpus each raise their own not-found class.
4. `content_sha256` does not say what it hashes.
5. `VerificationReport` has no `ModelTrace`; verification packs model id and prompt version into `method`.

Constraints: the change MUST be additive (minor bump, no field removed, renamed or tightened, existing tests
unchanged). P1 (grounded or silent), P3 (fail closed), P4 (time-bound law) and P5 (provenance) apply. Which date's
law governs an element is a legal rule. It MUST come from cited sources, never from the contract (ADR-0006 §6.2).

## Options considered
Where to record the reference date a law citation's version was selected for:

| Option | Pros | Cons | Reliability impact |
|---|---|---|---|
| A. Several dates on `LegalQuery` | Stays at the query level | Does not say which citation uses which date; the user cannot know the legally relevant dates before analysis | Bad: mixing dates stays silent |
| B. A date per `Element` | Simple; one field | One element can rest on provisions whose versions were selected for different dates (for example an offence article for the conduct and an interpretation applied at adjudication); forces splitting elements or misstates the date of some citations | Bad: a wrong date on a citation is not visible |
| C. An inline date (plus basis) on each `Citation` | Exact per citation | The date's basis and evidence are repeated on every citation that uses it and can drift apart | Medium: duplicated justifications are verified inconsistently |
| **D. Dates declared once on the outline; each law `Citation` names one by id** | Exact per citation; one basis and evidence per date; maps one to one onto verification's per-citation temporal check; absent id = `as_of` keeps 0.3.0 behaviour | Adds a cross-reference that needs a validator | Best: every date is explicit, cited and checkable per citation |

Store "not found": a new exception class vs a sentinel return value (`None`). A sentinel would change port return
types (breaking) and is easy to ignore. An exception that subclasses `LookupError` keeps current verification
behaviour correct while departments adopt it.

Cost on `ModelTrace`: store cost vs store tokens only. Prices change and differ by contract, so a stored cost is not
reproducible without its price table. Tokens are what the provider reports.

Verification traces: on `VerificationReport` vs on `ItemVerification`. Each model call judges one item, so a trace
on the item says exactly which call produced which verdict; the report-wide set is their union.

## Decision
Contracts 0.4.0 (minor bump over 0.3.0). Every new field is optional, with a default that reproduces 0.3.0
behaviour.

### 1. Reference dates (Option D)
1. `ReferenceDate`: `reference_id`, `kind` (`ReferenceDateKind`: `conduct`, `adjudication`, `other`), `day`, optional
   `period_start` / `period_end`, `description`, `basis`, `evidence`.
2. `kind` and `description` state what the date **is**, as a matter of fact. Nothing in the contract states which
   date governs.
3. `day` is the single date the cited versions were selected for. A period, when the fact is a period, is
   recorded in `period_start` / `period_end` (both or neither; `day` lies inside). Choosing `day` within the period is
   part of what `basis` must support.
4. `basis` (at least one, law only) cites the law relied on for selecting law as of `day` (P1). `evidence` (optional,
   case files only) cites where the case files state the date or period.
5. `EvidenceOutline.reference_dates: tuple[ReferenceDate, ...] = ()`.
6. `Citation.reference_date_id: str | None = None`. Only law citations may set it. `None` means `LegalQuery.as_of`.
7. The outline validator checks structure only: unique `reference_id`s, no citation naming an undeclared date, and no
   declared date left unused. Unused dates are rejected because the field is new and starting strict is the
   additive direction: relaxing later is a minor change, tightening is not.
8. `DraftAnswer` declares no reference dates in 0.4.0, so its citations MUST NOT set `reference_date_id`. Revisit if
   research Q&A needs them.
9. Verification checks every law citation against its own reference date: the cited version MUST be in force on the
   named `ReferenceDate.day`, or on `as_of` when no id is named. It also verifies `basis` and `evidence` like any
   other citations.

### 2. Token usage
`ModelTrace.input_tokens` and `ModelTrace.output_tokens`: `int >= 0` or `None`. They are totals over every model call
the trace covers, as reported by the provider. `None` means not reported and is never a stand-in for 0. Cost is not
stored. Whoever reports cost derives it from tokens and a pinned, versioned price table. A `cost` field may be added
later as another optional field.

### 3. Store "not found"
1. `legalai_contracts.DocumentNotFoundError(LookupError)`, with optional keyword attributes `doc_id` and
   `version_id`. Messages and attributes carry ids only, never document text (P9).
2. `SourceStore.get_document` / `get_text` and `CaseFileStore.get_document` / `get_text` raise it when the store
   holds no version with that `doc_id` / `version_id`. `list_documents` returns `[]` when nothing matches.
   Implementations MAY subclass it alongside their own error bases.
3. `get_text` returns exactly the stored characters `[start, end)` in code points. A range outside
   `0 <= start <= end <= char_count` raises `ValueError` and is never clamped. An empty range MAY raise `ValueError`.
4. **Fail-closed rule:** consumers catch `DocumentNotFoundError` by that class only. For a citation it means the
   citation does not resolve (verification: `CITATION_INVALID`). Any other exception from a store means the store
   could not answer authoritatively. Consumers MUST treat it as a check error (verification: `CHECK_ERROR`), never
   as "not found", never as success, and never fall back silently to another version.

### 4. Hash semantics
1. `SourceDocument.content_sha256` and `CaseDocument.content_sha256`: the lowercase hex SHA-256 of the UTF-8 encoding
   (no BOM, no newline or Unicode normalization) of exactly the stored text. That is the string of `char_count`
   code points that offsets index and `get_text` slices.
2. A store MUST verify this hash before it serves text. On mismatch it raises an error that is not
   `DocumentNotFoundError`. Consumers that see only slices (verification) rely on that guarantee. They cannot
   re-hash a slice.
3. New optional `original_sha256` on both models: the lowercase hex SHA-256 of the exact bytes of the original file
   the stored text was extracted from, before any extraction or normalization. For law, that is the raw file as
   retrieved from `source_uri`. For case files, it is the file exactly as received at intake. `None` means not
   recorded. Several law versions may share one `original_sha256` when one raw file yields several documents.
   Re-extracting the same case file differently keeps `original_sha256` and changes `content_sha256`.
4. Corpus (`store.text_sha256`, raw hash in `provenance.json`) and casefile (`content_sha256` of the stored UTF-8
   text, `original_sha256` in `meta.json`) already compute exactly these values. Neither needs to change its hashing.

### 5. Verification traces
`ItemVerification.traces: tuple[ModelTrace, ...] = ()` holds one trace per model call that contributed to the item's
verdict. It is empty when deterministic checks alone decided the item. `method` stays a free-text label. Model id and
prompt version MUST be in `traces` for any model-based verdict.

## Consequences
- Contracts 0.4.0 add these public names: `ReferenceDate`, `ReferenceDateKind`, `DocumentNotFoundError`. They add these
  fields: `EvidenceOutline.reference_dates`, `Citation.reference_date_id`, `ModelTrace.input_tokens` /
  `output_tokens`, `SourceDocument.original_sha256`, `CaseDocument.original_sha256`, `ItemVerification.traces`.
  Every 0.3.0 object and every 0.3.0 JSON document validates unchanged.
- `model_dump` output now includes the new keys with their defaults. Serialized forms and hashes over them (for
  example evaluation's dataset fingerprint) change value once, without any change in meaning. JSON written by 0.4.0
  cannot be read by a 0.3.0 reader (`extra="forbid"`). The monorepo runs a single contracts version, so this is
  expected.
- ADR-0006 §6.2 (single reference date) is resolved by §1 here. Until verification adopts §1.9, outlines MUST NOT
  rely on reference dates. A verifier that ignores `reference_date_id` checks every citation against `as_of`, which
  can miss a version that is not in force on its declared date.
- Departments adopt the changes through REQs issued by the Program Office (REQ-PMO-0010 §8 lists them):
  verification (§1.9, §3.4, §5), reasoning (§1, §2), casefile and corpus (§3, §4.3), evaluation (§1 for the
  pilot, §2 for cost), interface (§1 rendering).

## Validation
- Contract tests `departments/contracts/tests/test_wave1_gaps.py` cover every REQ-PMO-0010 acceptance criterion.
- Revisit §1 when the pilot (REQ-PMO-0008) is built and reviewed: if reviewers find the per-citation date or the
  single `day` per date unable to express the pilot's temporal reasoning, a new REQ to architecture changes it.
- Revisit §1.7 (unused dates rejected) and §1.8 (no dates on drafts) if reasoning or evaluation report legitimate
  uses they block.
