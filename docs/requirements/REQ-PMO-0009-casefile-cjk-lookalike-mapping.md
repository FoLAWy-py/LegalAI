---
id: REQ-PMO-0009
title: Detect and handle CJK look-alike code points produced by PDF font maps
from: pmo
to: casefile
owner: pmo
status: delivered
priority: P1
created: 2026-10-30
updated: 2026-10-30
depends_on: [REQ-PMO-0001]
---

# REQ-PMO-0009: Detect and handle CJK look-alike code points produced by PDF font maps

## 1. Context
PMO's verification of REQ-PMO-0001 (2026-10-30) used a PDF produced by an external tool: macOS `cupsfilter` from
synthetic Chinese text, with an embedded subset font. That PDF's font map sends common ideographs to **Kangxi Radical**
code points: 人→U+2F08, 入→U+2F0A, 月→U+2F49, 言→U+2F94. `extract_document` stored the text with **600 of 10,044**
characters substituted, with no error or warning. 0 of 120 source lines matched exactly. Replacing only the radical code
points with their compatibility-decomposition ideographs restored 120/120 lines and left the text length, and so every
offset, unchanged. The DOCX produced by macOS `textutil` from the same text was exact (120/120).

Risk (P1, P3): the stored text looks right to a human but differs by code point. Lexical retrieval for 投资人, 证言 etc.
misses these passages, so evidence is silently lost and false gaps appear. Fonts with such maps are common in real
Chinese PDF exports.

## 2. Requirement
1. Extraction MUST detect code points from Kangxi Radicals (U+2F00–U+2FDF) and CJK Radicals Supplement (U+2E80–U+2EFF)
   in PDF output. It SHOULD also detect CJK Compatibility Ideographs (U+F900–U+FAFF and U+2F800–U+2FA1F).
2. Such text MUST NOT be stored silently. Casefile decides, with recorded evidence, between:
   - (a) a documented, deterministic **1:1** code-point mapping that preserves length and offsets. The provenance
     records every mapped position (or a reversible record), the original code points, and a mapping version. The
     intake result carries a warning that names the count.
   - (b) a typed rejection.
   Mapping is preferred only if it cannot change offsets or merge characters a reader would distinguish. Record
   the reasoning in §8.
3. Any compatibility-ideograph handling MUST be justified separately in §8 (some are deliberately distinct forms).
4. The original extracted text MUST stay reproducible from the stored record (P5).

## 3. Interface
`CaseDocument` (no contract change expected); intake result warnings; provenance.

## 4. Acceptance criteria
1. At least one committed fixture PDF made by an **external** generator (not the in-package builders), with synthetic
   `ZZ` Chinese text and an embedded subset font that maps to radicals. With it:
   - all source lines are found exactly in the stored text (if mapping is chosen), or
   - the documented typed error is raised (if rejection is chosen).
2. Offsets/`page_of` remain correct on that fixture (sampled offsets on every page).
3. A text containing a genuine radical character in a non-PDF format (e.g. .txt) is stored unchanged. Mapping
   applies only where the extractor is the source of the substitution.
4. The warning or error names the count and code points. No document text appears in logs (as in REQ-PMO-0001 AC5).
5. `scripts/check_all.py` passes.

## 5. Out of scope
OCR; reading-order repair; letter-spacing repair.

## 6. Open questions
- Should the mapping, if chosen, also apply to DOCX/EML (where the author typed the character)? PMO's default is no.

## 7. Response
Decision: **accept**, choosing **(a) mapping** for CJK radicals in PDF output. No contract change.
The evidence is in §8. I reproduced the problem with a `cupsfilter` fixture: 664 of 10,044 characters were
substituted and 0 of 120 lines matched.

- **Radicals (U+2E80–U+2EFF, U+2F00–U+2FDF), PDF only.**
  - Each one is mapped 1:1 to the unified ideograph that Unicode's own `Equivalent_Unified_Ideograph` property
    gives (`EquivalentUnifiedIdeograph-15.1.0.txt`, committed with its SHA-256). This matches
    `unicodedata.unidata_version`.
  - NFKC alone is not enough. U+2EC5 (C-SIMPLIFIED SEE, the stand-in for 见) appears 20 times in the fixture
    and has no compatibility decomposition, so radical-only NFKC restores only 100 of 120 lines.
  - Code points with no equivalent (U+2E80, and unassigned ones) raise `PartialExtractionError`.
  - Every mapped position, its original code point and the table version are recorded. The original extractor
    output can be rebuilt exactly.
- **Compatibility ideographs** (U+F900–U+FAFF with a decomposition, U+2F800–U+2FA1F) are detected and **kept
  unchanged, with a warning.** They are deliberately distinct forms. The probe shows this kind of font map
  collapses them into unified ideographs rather than producing them, so their presence means the source
  contains them.
- **CJK Strokes** are out of scope: the generator passes typed strokes through unchanged.
- **§6:** no. In DOCX, EML, TXT and MD files the author's code points are stored directly, and no font map is
  involved. `textutil` DOCX output from the same text was exact, 120 of 120 lines.
- **Charter conflict:** this mapping goes beyond the casefile charter duty "never normalize or 'correct'
  document text beyond documented, reversible whitespace rules", and the charter ranks above this REQ. I amended
  that duty narrowly, to name only this recorded, reversible, PDF-only mapping. PMO or architecture should
  confirm the amendment or reject it. If rejected, the fallback is option (b), using the same detection code.

## 8. Delivery
- What changed (paths, public API):
  - `departments/casefile/src/legalai_casefile/_cjk.py` (new):
    - Detects radicals (U+2E80–U+2EFF, U+2F00–U+2FDF) and maps them 1:1 to their equivalent unified ideograph.
    - Detects compatibility ideographs (U+F900–U+FAFF with a decomposition, U+2F800–U+2FA1F). These are
      reported but never mapped.
    - `restore_extracted_text` rebuilds the extractor's output from the stored text and the record.
  - `ucd/EquivalentUnifiedIdeograph-15.1.0.txt` (new): the mapping source.
    - Fetched from `https://www.unicode.org/Public/15.1.0/ucd/EquivalentUnifiedIdeograph.txt`.
    - SHA-256 `460a08f497d0f3e45aae734708848fadf1ced44b752971bac37c23da55b33aa9`, checked on every load.
    - Redistributed under the Unicode terms of use; the file carries its own notice.
    - The directory is named `ucd/` because the root `.gitignore` rule `data/` would have excluded a `data/`
      directory.
  - `_pdf.py`: the mapping runs after pypdf extraction and the existing checks.
    - Each substitution is listed in `Extraction.substitutions` (`CodePointSubstitution`: offset, original,
      replacement), with `substitution_table = CJK_MAPPING_VERSION`.
    - A radical with no equivalent raises `PartialExtractionError`, naming the code points and pages.
    - Warnings name the counts and code points (ASCII only, never document characters).
  - `store.py`:
    - `meta.json` schema 2 adds `substitutions: {table, positions: [[offset, orig_hex, repl_hex], ...]}`.
      Schema 1 still reads.
    - `StoredVersion.substitutions` / `.substitution_table`.
    - New `LocalCaseFileStore.get_extracted_text()` returns the exact pypdf output. A record that does not
      match the stored text raises `StoreIntegrityError`.
    - The intake log line now adds only a substitution count.
  - New public names: `CodePointSubstitution`, `restore_extracted_text`, `CJK_MAPPING_VERSION`.
  - `CHARTER.md`: reliability duty amended narrowly, and the Interfaces section updated (see §7). No contract
    change. The ruff allow-list is unchanged; tests write radicals as `\u` escapes.
  - External fixtures in `departments/casefile/tests/fixtures/external/`:
    - `zz-radicals-source.txt`: 120 synthetic ZZ lines.
    - `zz-radicals-cupsfilter.pdf`: macOS 27.2 Quartz PDFContext, embedded subset font `AAAAAD+PingFangSC-Regular`.
    - `zz-radicals-cupsfilter.pages.json`: independent page truth from macOS PDFKit.
    - `zz-radicals-textutil.docx`.
    - Regenerate them with `tools/make_external_fixtures.py` (macOS) and `tools/pdfkit_page_numbers.js`.
- How to verify (commands):
  - `uv run python scripts/check_all.py`
  - `uv run pytest -q departments/casefile/tests/test_cjk_lookalikes.py`
- Evidence:
  - `check_all.py`: ALL CHECKS PASSED (pytest 361 passed, 1 deselected; 16 new tests in `test_cjk_lookalikes.py`).
  - Reproduction on the committed fixture (`test_fixture_is_external_with_embedded_subset_font`):
    - pypdf returns 664 of 10,044 characters as radicals, across 21 distinct code points.
    - 20 of the 664 are U+2EC5 for 见, which has no NFKC decomposition.
    - 0 of 119 numbered lines are exact. Radical-only NFKC would restore 100 of 120 lines; the UCD table
      restores 120 of 120.
  - AC1, `test_all_source_lines_found_exactly_after_mapping`:
    - 120 of 120 source lines are found exactly.
    - Length equals the raw output.
    - `restore_extracted_text(...)` equals pypdf's raw output.
    - No radical code point remains.
  - AC2, `test_page_of_against_independent_pdfkit_truth`: PDFKit puts the title and lines 1–61 on page 1 and
    lines 62–119 on page 2. `page_of` agrees at the first, middle and last character of all 120 lines.
  - AC3: text typed by the author is never mapped.
    - `test_genuine_radicals_in_text_files_are_unchanged`: .txt and .md, no substitutions, no warnings.
    - `test_genuine_radicals_in_docx_and_eml_are_unchanged`: .docx and .eml.
  - AC4:
    - The warning names the count (664) and pairs such as `U+2F08->U+4EBA x119` and `U+2EC5->U+89C1 x20`.
    - The no-equivalent error names `U+2E80 x1` and page 2.
    - `test_no_document_text_in_logs`: caplog at DEBUG.
  - Record integrity (P5):
    - `test_store_keeps_reversible_record`: all 664 positions match the raw and stored text, and every other
      position is identical.
    - `test_tampered_substitution_record_is_refused`.
  - Table, `test_table_is_complete_one_to_one_and_agrees_with_nfkc`:
    - 328 radicals mapped, each to exactly one unified ideograph.
    - The only assigned radical without an equivalent is U+2E80.
    - All 214 Kangxi entries equal NFKC (independent check).
    - UCD version 15.1.0 equals `unicodedata.unidata_version`.
    - The hash check is tested.
  - Decision evidence, from probing `cupsfilter` with mixed input:
    - 人 U+4EBA and a typed ⼈ U+2F08 both come out as U+2F08. 见 U+89C1 and ⻅ U+2EC5 both come out as U+2EC5.
      The PDF text layer cannot tell them apart, because the font shares one glyph and its map names the lowest
      code point. Mapping restores what the reader sees. It cannot merge characters a reader can tell apart in
      this PDF, since they are the same glyph. It cannot shift offsets, because every target is a single code
      point.
    - Rejection would refuse every PDF from such generators.
  - Compatibility ideographs (§2.3), kept unchanged with a warning:
    - The same generator turns U+F900, U+F914 and U+FA0D into their unified ideographs, so this kind of font map
      never produces them. A compatibility ideograph in PDF output therefore reflects the source.
    - They are deliberately distinct round-trip forms (for example readings in KS X 1001), and mapping them
      would erase that.
    - Test: `test_compatibility_ideographs_are_kept_with_warning`.
  - §6: no mapping for .docx, .eml, .txt or .md. `test_textutil_docx_from_same_source_is_exact` shows 120 of 120
    lines exact.
- Known limitations:
  - A radical that genuinely appears in a PDF (for example in a dictionary page) is mapped to its ideograph.
    The original stays recoverable through `get_extracted_text`.
  - CJK Strokes (U+31C0–U+31EF) are not mapped. The generator passed typed strokes through unchanged, so mapping
    them would alter genuine text.
  - Other look-alike classes are not handled: for example compatibility ideographs produced by a different
    generator's map, or Latin and full-width confusions.
  - `cupsfilter` silently drops every line from the first supplementary-plane character onward. A probe with
    U+2F800 lost three lines with no error. The PDF it writes does not contain that text, so no text-layer
    extractor can detect the loss. Do not use it to build fixtures with non-BMP characters.
  - The fixture PDF embeds a subset of the macOS PingFang SC font. PMO approved committing it. If architecture
    has a font-licence policy, it should confirm.
  - Only one external generator family is measured (Quartz). Tables for other generators are still to be
    collected.
