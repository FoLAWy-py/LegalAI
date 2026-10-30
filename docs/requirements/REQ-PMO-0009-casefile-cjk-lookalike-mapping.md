---
id: REQ-PMO-0009
title: Detect and handle CJK look-alike code points produced by PDF font maps
from: pmo
to: casefile
owner: pmo
status: open
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
_Pending (casefile)._

## 8. Delivery
_Pending (casefile)._
