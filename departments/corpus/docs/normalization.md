---
id: CORPUS-NORMALIZATION
owner: corpus
status: active
updated: 2026-10-30
---

# Text normalization rules (`corpus-norm-1`)

Stored text is derived mechanically from the raw official file, which is kept byte-for-byte at
`<data>/corpus/raw/objects/<sha256>`. Only the rules below are applied. Wording, punctuation, numerals and
characters are never edited. Spelling is never fixed. Whole-text Unicode normalization (NFC/NFKC) is not applied.
Each stored version records the rule set it used in `provenance.json` (`normalization_version`,
`extraction_rule`).

## 1. HTML (`extract.extract_html`)
- **N0, selection:** only the first element whose configured attribute matches is used (`id` must equal the
  value; `class` must contain the class token). Text inside `script`, `style`, `noscript` and `template` is
  dropped, and so are comments. Entities are decoded. The page must decode strictly in the configured
  encoding, or extraction fails.
- **N1, whitespace:** inside a paragraph, each run of ASCII whitespace (space, tab, CR, LF, FF) becomes one
  space. This is how a browser renders `white-space: normal`. Ideographic spaces (U+3000) and no-break spaces
  (U+00A0) inside a line are kept.
- **N2, trimming:** leading and trailing whitespace of each paragraph is removed. Python `str.strip`
  semantics are used, so this includes U+3000 indentation and U+00A0.
- **N3, paragraphs:** these block elements start and end a paragraph: `p div br li ul ol tr td th table tbody
  thead tfoot h1–h6 section article center blockquote pre dd dt dl hr header footer caption`. Empty paragraphs
  are dropped. Paragraphs are joined with a single `\n`, with no trailing newline.
- **N4, markers:** if a source sets `start_marker` or `end_marker`, each must occur exactly once. The text is
  cut to begin at the start marker and to end after the end marker. This removes page furniture such as
  "来源：" or editor lines without editing content.

## 2. Structure
Units (编, 分编, 章, 节, 条, 款, 项, and 一、二、 items of amendment acts) are offsets into the stored text, stored
in `units.json`. They never change the text. If an article number repeats, the text fails to parse and
ingestion stops.

## 3. PDF (`extract.extract_pdf`)
- Lines come from pdfminer.six in reading order. Lines that fully match a source's `drop_line_patterns`
  (running headers, page numbers) are removed, and the patterns are recorded.
- **N5, line joining:** a line indented by `indent_chars` (default 1.5) median character widths or more,
  measured from the page's left margin, starts a new paragraph. Every other line is appended to the previous
  one **without a separator**. That is correct for CJK text and **wrong for space-separated languages**, so
  US PDFs need a separate rule before use. N1 and N2 apply per paragraph.
- PDF output has not yet been validated against a real official PDF. Before PDF-derived text is relied on, a
  spot check against the independent pypdf path must pass for the document.

## 4. Look-alike code points (N6)
PDF font maps can emit Kangxi Radicals (U+2F00–U+2FDF), CJK Radicals Supplement (U+2E80–U+2EFF) or CJK
Compatibility Ideographs (U+F900–U+FAFF, U+2F800–U+2FA1F) in place of ordinary ideographs; for example
U+2F08 can appear in place of 人. Every extracted text, from any format, is scanned for these code points.
- Default policy `reject`: ingestion of that source fails. Use an HTML or DOCX rendering instead.
- Policy `map-to-unified` must be set explicitly per source. Only the flagged code points are replaced, one
  for one, by their NFKC image. The image must be a single CJK Unified Ideograph, or ingestion fails. Every
  replacement (offset, from, to) is recorded under `compat_codepoints` in `provenance.json`.

## 5. Offsets
Offsets are Python `str` indices, which are Unicode code points. `get_text(d, v, a, b)` returns exactly
`text[a:b]` of the stored UTF-8 file, whose SHA-256 is `content_sha256`.
