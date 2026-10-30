---
id: CHARTER-CASEFILE
owner: casefile
status: active
updated: 2026-10-30
---

# Casefile Charter

## Mission
Turn the user's case documents into exact, page-addressable text that can be cited and re-checked — and keep it confidential.

## Owns
- Intake of digital documents (ADR-0005, D9): `.docx`, `.txt`, `.md`, `.eml`, PDFs **with a text layer**.
  Scanned / image-only PDFs are **rejected with a clear reason** (no OCR in v1).
- Text extraction preserving reading order, with `page_starts` so every offset maps to a page.
- Local storage under `<LEGALAI_DATA_DIR>/casefile/`, grouped by `case_id`; content hashing; versioning
  when a user replaces a file.
- The `CaseFileStore` implementation.

## Does not own
Public law (corpus). Searching case files (retrieval). Deciding what evidence proves (reasoning / verification).

## Interfaces
- **Consumes:** `CaseDocument`.
- **Provides:** an intake API producing `CaseDocument`s; a `CaseFileStore` implementation.
  Public API (`legalai_casefile.__all__`): `LocalCaseFileStore(data_dir)` (`ingest`, `ingest_file`,
  `list_documents`, `get_document`, `get_text`, `list_versions`, `get_version`), `IntakeResult`,
  `StoredVersion`, `extract_document`, `Extraction`, `derive_doc_id`, `detect_language`,
  `PAGE_TERMINATOR`, `SUPPORTED_EXTENSIONS`, `DEFAULT_MAX_BYTES`, and the typed errors
  (`IntakeError` subclasses with `IntakeReason`; store errors). Offsets are Unicode code points;
  each PDF page ends with `PAGE_TERMINATOR` (form feed).

## Quality bars
- `get_text` returns exactly the stored characters for any offset range; `page_of` matches the page shown
  in the original file on a sampled check set.
- Extraction failures and partial extractions are reported, never silently truncated.
- Mixed Chinese/English documents extract without character loss (measured on a test set).

## Reliability duties
P1 (exact, re-readable evidence text), P5 (hash, received time, original filename), P9 (owner of the most
sensitive data: no plaintext logging, no copies outside the data dir, never used as fixtures).
Never normalize or "correct" document text beyond documented, reversible whitespace rules.
