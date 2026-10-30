---
id: REQ-PMO-0013
title: "Adopt contracts 0.4.0 in casefile: contract not-found error and original_sha256"
from: pmo
to: casefile
owner: pmo
status: verified
priority: P2
created: 2026-10-30
updated: 2026-10-30
depends_on: [ADR-0007, REQ-PMO-0010]
---

# REQ-PMO-0013: Adopt contracts 0.4.0 in casefile: contract not-found error and original_sha256

## 1. Context
ADR-0007 §3–§4 define a contract not-found error and an optional original-file hash.
Adoption list: REQ-PMO-0010 §8. Design: ADR-0007.

## 2. Requirement
1. casefile's `DocumentNotFoundError` MUST subclass `legalai_contracts.DocumentNotFoundError` (import the contract class under an alias); public behaviour otherwise unchanged.
2. `CaseDocument.original_sha256` MUST be set from the original-file hash casefile already keeps.

## 3. Interface
`legalai_contracts` 0.4.0 (see ADR-0007). No further contract change expected; raise a REQ to architecture if one is needed.

## 4. Acceptance criteria
1. A test catches a missing document as `legalai_contracts.DocumentNotFoundError`.
2. Every ingested test document has `original_sha256` equal to the sha256 of the original bytes.
3. `scripts/check_all.py` passes.

## 5. Out of scope
Changes to contracts.

## 6. Open questions
- None.

## 7. Response
Decision: **accept**. Both items need no change to contracts and no change to how casefile hashes. §6 has no
open questions. One design decision was needed: what to report for records already stored before this
change. Those records keep `original_sha256` in the `meta.json` provenance field but not inside the stored
`CaseDocument`. The decision is recorded in §8 under "Already-stored documents".

## 8. Delivery
- **What changed** (all in `departments/casefile/`):
  - `src/legalai_casefile/errors.py`: `DocumentNotFoundError` is now
    `class DocumentNotFoundError(CasefileError, ContractDocumentNotFoundError)`, where the contract class is
    imported as `from legalai_contracts import DocumentNotFoundError as ContractDocumentNotFoundError`. It is still a
    `LookupError` (through the contract class) and still a `CasefileError`. The public name and `__all__` are
    unchanged.
  - `src/legalai_casefile/store.py`:
    - At intake, `CaseDocument.original_sha256` is set to `hashlib.sha256(data).hexdigest()`, where `data` is
      the bytes as received. This is the same value that was already stored in `meta.json["original_sha256"]` and
      used in `version_id`. Hashing is unchanged. `content_sha256` is still the SHA-256 of the UTF-8 stored text
      (ADR-0007 §4.1, §4.3).
    - Not-found errors now carry `doc_id=` and, when known, `version_id=` (ids only, P9).
    - The `meta.json` schema is now 3 and the store reads schemas 1, 2 and 3. A schema-3 record whose
      `CaseDocument` has no `original_sha256` raises `StoreIntegrityError`. So does any record, of any schema,
      whose `CaseDocument.original_sha256` differs from the provenance `original_sha256`. Neither case is reported
      as not found.
  - `tests/test_contracts_0_4_0.py` (new, 11 tests). `tests/test_cjk_lookalikes.py`: the expected schema number
    changes from 2 to 3. Nothing else in that test changed.
- **Already-stored documents (decision):** records written before this change (schema 1 and 2) are
  **filled on read, not left `None`, and never rewritten**. When such a record is loaded, its `original_sha256` is
  taken from the `meta.json` provenance field `original_sha256`. Casefile computed that field at intake from the
  exact received bytes (the same `hashlib.sha256(data)` call), so it is the "original-file hash casefile already
  keeps" (ADR-0007 §4.4), not a reconstruction. The filled value is validated like any contract value: a malformed
  hash raises `StoreIntegrityError`. No stored file is modified: version directories stay write-once, and stored
  text is never touched. The note recording which records were filled is the schema number itself: schema 1 or 2
  means the value came from the provenance field. Tests:
  `test_legacy_record_reports_hash_recorded_at_intake_without_rewriting[1|2]` (byte-for-byte check that nothing on
  disk changed, and that legacy reads equal the current intake result) and
  `test_legacy_record_with_malformed_provenance_hash_is_refused`.
- **Acceptance criteria:**

  | AC | Evidence |
  |---|---|
  | 1. A missing document is caught as `legalai_contracts.DocumentNotFoundError` | `test_missing_document_is_caught_as_contract_error`: unknown doc and unknown version, through both `get_document` and `get_text`; checks the `doc_id` / `version_id` attributes and that the message contains no text. `test_casefile_not_found_subclasses_contract_error`. `test_integrity_failure_is_not_a_not_found` checks that a tampered store is not reported as not found (ADR-0007 §3.4). The existing `test_unknown_documents` still passes. |
  | 2. Every ingested test document has `original_sha256` equal to the SHA-256 of the original bytes | `test_every_ingested_document_has_original_sha256` covers 8 files: 3 PDFs (including the external CJK-radical fixture), .docx, UTF-8 .txt, GB18030 .txt, .md and .eml. It checks the intake result, `get_version`, the stored `original*` file, and a fresh reload through `list_documents` / `get_document`, and checks that `content_sha256` is still the hash of the stored text. `test_reingest_keeps_hash_per_version` and the legacy tests above cover the remaining paths. |
  | 3. `scripts/check_all.py` passes | `ALL CHECKS PASSED` (see below). |
- **How to verify:**
  `uv run pytest departments/casefile -q` (120 passed) and `uv run python scripts/check_all.py`.
- **Evidence:** `uv run pytest departments/casefile/tests/test_contracts_0_4_0.py -q` gives `11 passed`.
  `scripts/check_all.py` passes all steps: ruff check, ruff format, mypy (all packages and scripts), and pytest
  (`542 passed, 7 deselected`). It ends with `ALL CHECKS PASSED`.
- **Known limitations:**
  - On read, the store does not re-hash the stored original file against `original_sha256`. Doing so would hash
    every original on every `list_documents` call. `original_sha256` is provenance only. The text that offsets
    index is still checked against `content_sha256` before it is served.
  - A malformed `doc_id` / `version_id` (for example `../x`) still raises `InvalidIdentifierError` (a
    `ValueError`), not `DocumentNotFoundError`. This is unchanged public behaviour, as §2.1 requires. Under the
    rule in ADR-0007 §3.4, consumers treat it as a check error, which fails closed.
  - Moving to schema 3 is one-way: an older casefile build refuses schema-3 records with "unknown metadata
    schema" (fails closed).
  - No real data directory was inspected (P9). Legacy handling was tested on synthetic records that were
    rewritten to the exact schema-1 and schema-2 layout.

### PMO verification (2026-10-30)
Verified by the issuer. AC1–AC3 checked against the diff and tests: changes are confined to `departments/casefile/`;
the only edit to an existing test is the expected metadata schema (2 → 3), a direct consequence of storing
`original_sha256`. Back-filling old records from the intake-time hash in `meta.json` (no re-hash, no rewrite) is accepted:
it is the hash casefile already kept (ADR-0007 §4). Merged to `main`; `scripts/check_all.py`: 542 passed, ALL CHECKS PASSED.

