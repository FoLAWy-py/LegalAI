---
id: REQ-PMO-0001
title: Ingest digital case documents and serve them through CaseFileStore
from: pmo
to: casefile
owner: pmo
status: open
priority: P1
created: 2026-10-30
updated: 2026-10-30
depends_on: [ADR-0005]
---

# REQ-PMO-0001: Ingest digital case documents and serve them through CaseFileStore

## 1. Context
Evidence links must cite exact, page-addressable case text (ADR-0005, P1). Case files are confidential (P9).

## 2. Requirement
1. An intake API MUST accept `.docx`, `.txt`, `.md`, `.eml` and PDFs with a text layer for a given `case_id`
   and produce `CaseDocument`s with correct `page_starts` (non-paginated formats: one page).
2. Image-only / scanned PDFs, encrypted files and unsupported formats MUST be rejected with a typed error
   stating the reason. Partial extraction MUST be an error, not a truncated document.
3. A `CaseFileStore` implementation MUST serve documents and exact text ranges from `<data_dir>/casefile/`.
4. Re-ingesting a changed file MUST create a new `version_id`; the old version stays readable.
5. Data dir is passed in by the caller; the package MUST NOT read environment variables.

## 3. Interface
`CaseDocument`, port `CaseFileStore`. No contract change expected.

## 4. Acceptance criteria
1. Tests (fixtures generated in-test, synthetic, `SYNTHETIC` in titles) cover every format, Chinese, English and mixed text.
2. For each multi-page PDF fixture, `page_of(offset)` equals the true page for sampled offsets on every page.
3. `get_text(doc, v, a, b)` equals the slice of the stored text for random ranges (property test).
4. A scanned/image-only PDF fixture is rejected with the documented error.
5. No document text appears in logs at INFO level or above (test with log capture).
6. `scripts/check_all.py` passes.

## 5. Out of scope
OCR, audio, chat exports, retrieval/indexing.

## 6. Open questions
- Which PDF extraction library gives reliable reading order for Chinese text? Record the choice and evidence in §8.

## 7. Response
_Pending (casefile)._

## 8. Delivery
_Pending (casefile)._
