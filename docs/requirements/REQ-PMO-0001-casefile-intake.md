---
id: REQ-PMO-0001
title: Ingest digital case documents and serve them through CaseFileStore
from: pmo
to: casefile
owner: pmo
status: in-progress
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
Decision: **accept** (casefile, 2026-10-30). No contract change needed; `CaseDocument` and `CaseFileStore`
from contracts 0.2.0 are sufficient.

Plan and interpretation (no change to the acceptance criteria):
- Sequencing per PMO: Chinese (CN) documents first. Every format is tested with Chinese, English and mixed
  zh/en text, including full-width punctuation and characters outside the BMP.
- Offsets are Unicode code points into the stored text. Pages of a PDF are joined by a form feed (`\f`)
  ending each page, so every page owns at least one character and `page_starts` stays strictly increasing.
- Fail closed: image-only pages, unmapped glyphs (U+FFFD, `(cid:N)`, private-use code points), encrypted
  files, tracked changes, undecodable text and empty documents raise typed `IntakeError` subclasses whose
  messages never contain document text.
- §6 is answered from evidence: synthetic Chinese multi-page PDFs are built in-test and at least two
  candidate libraries are compared on extracted text and reading order; result and licenses go in §8.

## 8. Delivery
_Pending (casefile)._
