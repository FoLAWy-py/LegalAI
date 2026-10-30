---
id: REQ-PMO-0001
title: Ingest digital case documents and serve them through CaseFileStore
from: pmo
to: casefile
owner: pmo
status: delivered
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
- What changed (paths, public API):
  - `departments/casefile/src/legalai_casefile/`: `store.py` (`LocalCaseFileStore`: intake + `CaseFileStore`),
    `extraction.py` (format dispatch), `_pdf.py` (pypdf + fail-closed content-stream checks), `_docx.py`
    (stdlib OOXML), `_eml.py` (stdlib email), `_text.py` (strict decoding), `_common.py`, `errors.py`.
    Test-only builders, no I/O: `_synthetic_pdf.py`, `_synthetic_docs.py`, `_pdf_corpus.py`.
  - Public API (`__all__`, also listed in the charter's Interfaces section): `LocalCaseFileStore(data_dir)` with
    `ingest`, `ingest_file`, `list_documents` (latest version per doc), `get_document`, `get_text`,
    `list_versions`, `get_version`; `IntakeResult` (document, created, warnings); `StoredVersion` (provenance);
    `extract_document`; `Extraction`; `derive_doc_id`; `detect_language`; `PAGE_TERMINATOR`;
    `SUPPORTED_EXTENSIONS`; `DEFAULT_MAX_BYTES`; errors: `IntakeError` (with `reason: IntakeReason`, `pages`)
    → `UnsupportedFormatError`, `FormatMismatchError`, `EncryptedDocumentError`, `ScannedDocumentError`,
    `PartialExtractionError`, `UnsupportedContentError`, `UndecodableTextError`, `EmptyDocumentError`,
    `CorruptDocumentError`, `TooLargeError`; store errors `DocumentNotFoundError`, `InvalidRangeError`,
    `StoreIntegrityError`, `InvalidIdentifierError`.
  - Semantics: offsets are Unicode code points. PDF text is pypdf's output unchanged, with every page ending
    in one `\f` (so blank pages still own a character). Text files lose only a BOM; CRLF is kept. Layout:
    `<data_dir>/casefile/cases/<case_id>/<doc_id>/<version_id>/{original.<ext>, text.txt, meta.json}`,
    written atomically, dirs 0700 / files 0600. `doc_id` = hash of (case_id, NFC filename) unless the caller
    passes one. `version_id` = `v<seq>-<sha256(original)[:12]>`. Identical bytes do not create a new version.
    `content_sha256` = SHA-256 of the stored UTF-8 text, re-checked on every load.
  - Dependency: `pypdf>=6.21,<7` (locked 6.21.4) in `departments/casefile/pyproject.toml`; `uv.lock` updated.
    The same pyproject adds a narrow ruff `allowed-confusables` list (15 full-width code points actually used in
    fixtures), following verification's approach. No contract change.
  - `departments/casefile/tools/compare_pdf_extractors.py`: the §6 comparison harness.
- How to verify (commands):
  - `uv run python scripts/check_all.py`
  - `uv run pytest -q departments/casefile`
  - `uv run --with pypdf --with pdfminer.six --with pypdfium2 --with pymupdf python departments/casefile/tools/compare_pdf_extractors.py`
- Evidence (test output, eval scores):
  - `check_all.py`: ALL CHECKS PASSED on the branch with `main` merged in (pytest 345 passed, 1 deselected;
    casefile 93 passed).
  - AC1: `tests/test_pdf.py`, `test_docx.py`, `test_text_and_eml.py` and `test_store.py` cover every format with
    zh, en and mixed fixtures. Fixtures are built in-test, all titles carry `SYNTHETIC`, and the
    data is jurisdiction ZZ. The fixtures include full-width punctuation, digits and letters, U+3000, and CJK
    Ext-B code points. They also cover CRLF, GB18030 and UTF-16, RFC 2047 subjects, and GBK-only characters
    under a `gb2312` label.
  - AC2: `test_page_of_matches_true_page_on_every_page` covers 4 multi-page PDFs (3, 3, 2 and 9 pages, the
    last with a blank page 4). For every true line on every page it checks `page_of` and the character at its
    first, middle and last offset, plus each page's first offset and its terminator.
  - AC3: `test_get_text_equals_slice_for_random_ranges` (seeded `random.Random(20261030)`, 300 ranges per doc
    × 7 docs, plus edge ranges). Invalid ranges raise `InvalidRangeError`, never clamp.
  - AC4: `test_scanned_pdf_is_rejected_with_documented_error` raises `ScannedDocumentError`
    (`reason=scanned`, `pages=(1, 2)`). Also tested: one scanned page among text pages, invisible OCR text layer.
  - AC5: `test_no_document_text_in_logs_at_info_or_above` uses caplog at DEBUG over every format, refused
    files and reads, and checks INFO+ records from all loggers plus every casefile record. It is self-checked
    by `test_leak_detector_is_not_vacuous`. Error messages are also asserted to contain no document text.
  - REQ §2.5: `test_no_environment_variables_are_read`.
  - **§6 answer: pypdf (BSD-3-Clause), plain mode, content-stream order.** Comparison on 10 synthetic Chinese
    PDF fixtures (Type0/Identity-H font + ToUnicode, as office suites export; Helvetica for Latin runs).
    N = non-whitespace text exact, L = lines exact, P = page count; capital letter = pass:

    | fixture | pypdf 6.21.4 | pdfminer.six 20260107 | pypdfium2 5.14.0 | PyMuPDF 2.0 |
    |---|---|---|---|---|
    | zh_tj_3pages | NLP | NLP | NLP | NLP |
    | zh_glyph_positioned | NLP | NLP | **nlP** (all CJK glyphs silently dropped on pages 2-3) | NLP |
    | zh_kerned_small(-60) | NLP | NLP | NLP | NLP |
    | zh_kerned_wide(-250) | NlP | NlP | NlP | NlP |
    | zh_char_spacing(Tc=3) | NLP | NlP (spaces inserted) | NLP | NlP |
    | mixed_zh_en_fonts | NLP | NLP | NLP | NLP |
    | zh_reverse_stream_order | nlP (stream order) | NLP | nlP | nlP |
    | zh_two_column | NLP | NLP | NLP | NLP |
    | zh_table_rows | NLP | **nlP** (table read column-wise) | NLP | NlP |
    | zh_astral_ext_b | NLP | NLP | NLP | NLP |
    | **all-pass of 10** | **8** | 7 | 7 | 6 |
    | license | BSD-3-Clause | MIT | BSD-3-Clause / Apache-2.0 (+ PDFium deps) | AGPL-3.0 or commercial |

    Every library silently returned control-character garbage for fonts without ToUnicode, `''` for an
    image-only page, and normal text for an RC4-encrypted PDF with an empty user password. So
    `_pdf.py` refuses these itself by walking each content stream (fonts, `Tr` render mode, image area via
    the CTM, paths, nested forms), plus annotations and the catalog.
    pypdf was chosen because it lost no characters except under a reordered stream, kept table rows intact, has
    no native binary, and has a permissive license. pypdf's 8 exact fixtures are pinned by
    `test_page_text_is_exact`, so an upgrade that changes behaviour fails the suite.
- Known limitations:
  - Reading order is content-stream order. In a PDF whose stream order differs from visual order, lines keep
    every character (`test_known_limitations_lose_no_characters`) but appear in stream order. A quote that
    spans such lines would not be contiguous.
  - Wide letter-spacing (TJ gaps of about 0.25 em) makes every candidate insert spaces between Chinese
    characters. The stored text then contains those spaces, and quotes must match it exactly.
  - Fail-closed rules that may refuse legitimate files:
    - Any image covering 25% or more of a page (e.g. full-page letterhead backgrounds).
    - Graphics-only pages.
    - Form fields and FreeText annotations (the user must flatten the PDF first).
    - Hidden optional-content layers, XFA forms, Type0/Type3 fonts without ToUnicode (including predefined
      `Uni*` CMaps), and `strict=True` parse errors.
    - Private-use characters, `w:sym`, tracked changes, OLE objects in .docx.
    - HTML-only and inline forwarded e-mails.
    - Text that is not UTF-8 when no `encoding=` is passed.
  - Not extracted, reported only as warnings:
    - Small images (seals, signatures).
    - .docx comments.
    - E-mail attachments and inline images.
    - Other PDF annotations.
  - .docx stored text order: body, then headers, footers, footnotes, endnotes.
  - `language` is a heuristic (`zh` / `en` / `mul` / `und`) unless the caller passes it.
  - Single writer per data dir, with no locking. Read cache: 16 texts.
  - The fixtures are synthetic and carry no embedded font programs. Behaviour on real Word/WPS exports
    (embedded subset fonts) is not measured, because no real case data may be used. A sampled check against
    the page numbers shown in real files (charter quality bar) needs an approved, non-confidential sample set.
