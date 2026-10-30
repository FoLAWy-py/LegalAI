---
id: REQ-PMO-0010
title: Close contract gaps found in Wave 1 (reference dates, traces, store errors, hashing)
from: pmo
to: architecture
owner: pmo
status: delivered
priority: P1
created: 2026-10-30
updated: 2026-10-30
depends_on: [ADR-0006, REQ-PMO-0001, REQ-PMO-0004, REQ-PMO-0005, REQ-PMO-0008]
---

# REQ-PMO-0010: Close contract gaps found in Wave 1

## 1. Context
Wave 1 deliveries (REQ-PMO-0001, 0004, 0005, 0007) each worked around a gap in contracts 0.3.0 and reported it:
- **Reference dates** (ADR-0006 §6.2): one `LegalQuery.as_of` cannot express a criminal case where the conduct
  (pilot SPP 检例第175号: 2014–2018) and the judgment (2021) fall under different law versions. The pilot (REQ-PMO-0008)
  needs this before evaluation builds it.
- **Token cost** (REQ-ARCH-0001 AC2): `ModelTrace` has no token-usage fields.
- **Store "not found"**: the `SourceStore` / `CaseFileStore` ports define no error. Verification maps `LookupError`
  to CITATION_INVALID and anything else to CHECK_ERROR. Casefile raises its own `DocumentNotFoundError`.
- **`content_sha256` semantics**: the contract does not say whether it hashes the stored text or the original file
  bytes. Casefile hashes stored UTF-8 text. Verification does not check it at all.
- **Verification traceability** (P5): `VerificationReport` has no `ModelTrace`. Model id and prompt version are
  packed into `ItemVerification.method` strings.

## 2. Requirement
All changes MUST be additive: a minor bump, no field removed, renamed or tightened, and existing tests unchanged.
1. **Reference dates:** contracts MUST let an outline state, per element legal basis, which reference date that
   citation's law version was selected for. Examples: conduct date or period, adjudication date. Verification can then
   check temporal validity per citation. Which date governs is a legal rule. The contract only carries the dates and
   the cited basis for the choice; it MUST NOT encode the rule. Cases with a single `as_of` keep working unchanged.
2. **ModelTrace:** add optional token-usage fields (input/output tokens) and leave room for cost.
3. **Store errors:** define a contract exception (or exception hierarchy) for "document/version not found", to be
   raised by store implementations. Document how consumers must treat other exceptions (fail closed).
4. **Hash semantics:** specify exactly what `content_sha256` covers for `SourceDocument` and `CaseDocument`. Record it
   in a standard or ADR. Add an optional field for the original-file hash if needed.
5. **Verification traces:** `VerificationReport` (or its items) MUST be able to carry `ModelTrace`s.
6. Record decisions in an ADR or standard. Do not edit department code. Departments adopt the changes through their own REQs.

## 3. Interface
`LegalQuery`, `Citation` / `Element`, `ModelTrace`, `SourceStore`, `CaseFileStore`, `SourceDocument`, `CaseDocument`,
`VerificationReport`.

## 4. Acceptance criteria
1. A contract test builds a valid criminal outline on `ZZ` data whose element citations use two different reference
   dates, each recorded on the outline. The same outline without the new fields still validates.
2. Contract tests cover token fields, the not-found exception, and the verification trace field.
3. Hash semantics are written down and referenced from the `content_sha256` field docstrings.
4. `CONTRACT_VERSION` minor bump. All existing tests in every department pass unchanged. `scripts/check_all.py` passes.

## 5. Out of scope
Jurisdiction applicability between `US` and `US-XX` (US deferred, ADR-0006 §6.3); department adoption.

## 6. Open questions
- Should the reference date live on `Citation` (per citation) or on `Element` (per element)? Architecture decides
  and records why.

## 7. Response
**Accepted** by architecture, 2026-10-30. All changes are additive: contracts 0.3.0 → **0.4.0** (minor). No field,
value or validator is removed, renamed or tightened. Every new field is optional with a default that reproduces
0.3.0 behaviour. Decisions are recorded in ADR-0007.

1. **Reference dates (answer to §6: on `Citation`, declared on the outline).**
   - `EvidenceOutline.reference_dates: tuple[ReferenceDate, ...] = ()` declares each reference date once. A
     `ReferenceDate` has an id, a descriptive `kind` (`conduct`, `adjudication`, `other`), the `day` the cited law
     versions were selected for, an optional factual period (`period_start`/`period_end`, `day` inside it), a
     factual `description`, a required `basis` (law citations relied on for using this date) and optional
     `evidence` (case-file citations stating the date or period).
   - `Citation.reference_date_id: str | None = None` names the reference date a law citation's version was
     selected for. `None` means `LegalQuery.as_of`, exactly as in 0.3.0. Case-file citations cannot set it.
   - The outline validator checks only structure: unique ids, no dangling id, every declared date used. It never
     decides which date governs. That stays a legal rule, cited in `basis` and checked by verification.
   - **Why `Citation`, not `Element`:** temporal validity is a property of each cited version, and one element can
     rest on several provisions whose versions were selected for different dates (for example a Criminal Law
     article for the conduct and a judicial interpretation applied at adjudication). A per-element date would
     force splitting elements or would misstate the date for some citations. Verification already checks
     temporal validity per citation, so a per-citation reference maps one to one onto its check. Declaring the
     dates once on the outline, rather than inline on each citation, keeps one place for each date's basis and
     evidence.
   - `DraftAnswer` has no registry in 0.4.0, so its claims' citations must not set `reference_date_id`.
2. **ModelTrace:** optional `input_tokens` and `output_tokens` (`int >= 0`, `None` = not reported, never 0 by
   default), totals over every model call the trace covers. Cost is not stored: prices change, so cost is computed
   downstream from tokens and a pinned price table. A `cost` field can be added later as another optional field.
3. **Store errors:** new `DocumentNotFoundError(LookupError)` with optional `doc_id` / `version_id`. Both port
   docstrings state: `get_document` / `get_text` raise it when the version does not exist; `list_documents`
   returns `[]`; every other exception means the store could not answer and consumers MUST treat it as a check
   error (fail closed), never as "not found" and never as success. Subclassing `LookupError` keeps today's
   verification behaviour; adopting departments subclass it from their own not-found errors.
4. **Hash semantics:** corpus and casefile already agree. `content_sha256` = lowercase hex SHA-256 of the UTF-8
   encoding (no BOM, no normalization) of exactly the stored text that offsets index and `get_text` slices. New
   optional `original_sha256` on `SourceDocument` and `CaseDocument` = SHA-256 of the original file bytes before
   extraction. Both fields' descriptions cite ADR-0007 §4.
5. **Verification traces:** `ItemVerification.traces: tuple[ModelTrace, ...] = ()`, one per model call that
   contributed to the item's verdict. On items, not the report, because each model call judges one item; the
   report-wide set is the union.
6. Department adoption is listed in §8 for the Program Office to issue; architecture edits no department code.

## 8. Delivery
- **What changed (paths, public API):**
  - `departments/contracts/src/legalai_contracts/__init__.py`: `CONTRACT_VERSION` 0.3.0 → **0.4.0**. New exports:
    `DocumentNotFoundError`, `ReferenceDate`, `ReferenceDateKind`.
  - `outline.py`: `ReferenceDateKind` (`conduct`, `adjudication`, `other`); `ReferenceDate` (`reference_id`, `kind`,
    `day`, optional `period_start`/`period_end`, `description`, `basis` ≥ 1 law citation, `evidence` case-file
    citations); `EvidenceOutline.reference_dates = ()` with a validator for unique ids, no dangling id and no
    unused date. Docstrings of `Element` and `EvidenceOutline` updated.
  - `answers.py`: `Citation.reference_date_id = None` (law citations only); `ModelTrace.input_tokens` /
    `output_tokens = None` (`>= 0`); `DraftAnswer` rejects `reference_date_id` on its citations (it has no
    registry); `LegalQuery` docstring states that `as_of` is the default reference date.
  - `errors.py` (new): `DocumentNotFoundError(LookupError)`, with optional keyword `doc_id` / `version_id`.
  - `ports.py`: `SourceStore` and `CaseFileStore` docstrings state the error contract and the fail-closed rule.
  - `sources.py`: `content_sha256` descriptions state the exact rule and cite ADR-0007 §4. New optional
    `original_sha256` on `SourceDocument` and `CaseDocument`.
  - `verification.py`: `ItemVerification.traces = ()`.
  - `departments/contracts/tests/test_wave1_gaps.py` (new, 30 tests). No existing test in any department was
    modified.
  - `docs/adr/ADR-0007-contract-additions-wave1-gaps.md` (new, accepted): all decisions, the options considered,
    and the consumer rules.
  - **Hash semantics: no conflict.** Corpus (`FileSourceStore`, `text_sha256`) and casefile (`LocalCaseFileStore`)
    both hash the UTF-8 bytes of exactly the stored text. Both verify the hash on every read. Both already keep an
    original-bytes hash internally: corpus in `provenance.json` `raw.sha256`, casefile in `meta.json`
    `original_sha256`. ADR-0007 §4 adopts that rule unchanged.
- **How to verify (commands):**
  - `uv run python scripts/check_all.py`
  - `uv run pytest -q departments/contracts/tests/test_wave1_gaps.py`. Mapping to the acceptance criteria:
    - AC1: `test_criminal_outline_with_two_reference_dates`, `test_same_outline_without_new_fields_still_validates`,
      `test_contracts_0_3_json_without_new_keys_validates`, plus negative cases.
    - AC2: `test_model_trace_*`, `test_not_found_*`, `test_store_raises_contract_not_found_for_absent_version`,
      `test_other_store_errors_are_not_not_found`, `test_port_docstrings_state_the_error_contract`,
      `test_item_verification_*`, `test_traces_do_not_relax_fail_closed_report`.
    - AC3: `test_content_sha256_descriptions_reference_adr`, `test_content_sha256_rule_on_non_ascii_text`,
      `test_original_sha256_is_optional_and_well_formed`.
    - AC4: `test_contract_version_is_minor_bump`, plus the full suite.
- **Evidence (test output):** `uv run python scripts/check_all.py`, 2026-10-30:
  ```
  boundaries: OK (0 violation(s))
  docs: OK (0 problem(s))
  $ ruff check .            All checks passed!
  $ ruff format --check .   178 files already formatted
  $ mypy -p=legalai_contracts ... -p=legalai_interface   Success: no issues found in 68 source files
  $ mypy scripts            Success: no issues found in 3 source files
  $ pytest -q               531 passed, 7 deselected
  ALL CHECKS PASSED
  ```
  Contracts alone: 57 passed (27 existing, unchanged, plus 30 new).
- **Adoption needed (for PMO to issue as REQs; architecture issues none):**
  1. **verification:**
     - Check each law citation against its own reference date: `ReferenceDate.day` when `reference_date_id` is
       set, otherwise `as_of` (ADR-0007 §1.9).
     - Verify each reference date's `basis` (law) and `evidence` (case-file) citations.
     - Catch `DocumentNotFoundError`, not `LookupError` (§3.4).
     - Put a `ModelTrace` with token counts on every Phase B item in `ItemVerification.traces` (§5).
     - This adoption is a **prerequisite** for any outline that uses reference dates (see limitations).
  2. **reasoning:**
     - Emit `reference_dates` and `Citation.reference_date_id` only when cited law supports the choice of date.
       Otherwise abstain or flag, as ADR-0006 §6.2 requires.
     - Fill `input_tokens` / `output_tokens` on every `ModelTrace`.
  3. **casefile:**
     - Make `DocumentNotFoundError` subclass the contract `DocumentNotFoundError`. Today it subclasses only
       `LookupError`; same name, so import the contract class under an alias.
     - Set `CaseDocument.original_sha256` from the existing `original_sha256`.
  4. **corpus:**
     - Make `store.DocumentNotFound` subclass the contract `DocumentNotFoundError`.
     - Set `SourceDocument.original_sha256` to the raw file hash already recorded in provenance.
  5. **evaluation:**
     - Build the pilot (REQ-PMO-0008) with `reference_dates` where the annotation gives two dates.
     - Report token usage and cost from `ModelTrace` tokens and a pinned price table (REQ-ARCH-0001 AC2).
     - Use `ItemVerification.traces` in reports.
     - Optionally migrate its in-memory fake stores to raise the contract error.
  6. **interface:**
     - Render each reference date (kind, day, period, basis) and show which citations use which date.
     - Do not accept outlines with `reference_dates` until verification adoption (1) is delivered.
- **Known limitations:**
  - Until verification adopts §1.9, a verifier that ignores `reference_date_id` checks every citation against
    `as_of`. It can then pass a citation whose version is in force on `as_of` but not on its declared reference
    date. Producers MUST NOT emit reference dates before verification adoption, and PMO should sequence the REQs
    that way. The contract cannot enforce this.
  - `model_dump` now includes the new keys, with defaults `null` / `[]`. Hashes over serialized contracts change
    value once, without any change in meaning; for example evaluation's `EvalDataset.fingerprint()`. No test pins
    a fingerprint value. JSON written by 0.4.0 is not readable by a 0.3.0 reader (`extra="forbid"`).
  - `ReferenceDate.day` is a single date. Reasoning that needs a citation checked "throughout a period" is not
    expressible. ADR-0007 Validation names the pilot review as the trigger to revisit.
  - `DraftAnswer` (research Q&A) gets no reference dates in 0.4.0. Its citations must not set `reference_date_id`.
  - Out of scope, as REQ §5 states: jurisdiction applicability between `US` and `US-XX`, and department adoption.
