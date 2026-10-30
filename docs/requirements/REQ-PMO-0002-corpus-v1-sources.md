---
id: REQ-PMO-0002
title: Assess origins and ingest v1 CN and US federal law with versions
from: pmo
to: corpus
owner: pmo
status: open
priority: P1
created: 2026-10-30
updated: 2026-10-30
depends_on: [ADR-0004, ADR-0005]
---

# REQ-PMO-0002: Assess origins and ingest v1 CN and US federal law with versions

## 1. Context
Elements must be grounded in authoritative, versioned law (P1, P4, P5). Scope per ADR-0005.

## 2. Requirement
1. Corpus MUST write `departments/corpus/docs/origins.md` assessing each candidate origin in the charter:
   terms of use, robots policy, rate limits, formats, how versions/effective dates are obtained. Each origin is
   marked approved / rejected with reasons. Only approved origins may be downloaded.
2. Corpus MUST ingest, from approved origins: **CN** — Civil Code, Civil Procedure Law, SPC provisions on evidence
   in civil procedure; **US** — Federal Rules of Evidence, Federal Rules of Civil Procedure. All versions in force
   from 2021-01-01 onward, with correct `effective_from` / `effective_to`.
3. Text MUST be stored in the original language, structure preserved so article/rule pinpoints can be derived.
4. A `SourceStore` implementation MUST serve documents and exact text ranges.
5. The US state layer is deferred until project decision D8; design MUST allow adding it without contract change.

## 3. Interface
`SourceDocument`, `DocType`, port `SourceStore`.

## 4. Acceptance criteria
1. `origins.md` exists and covers every candidate origin.
2. 100% of ingested documents pass contract validation (complete provenance, hash matches stored text).
3. Spot-check list (≥ 20 articles/rules across documents, chosen by corpus and recorded in §8) matches the official
   rendering character-for-character, including article numbering.
4. For at least one amended document, two versions exist with non-overlapping validity intervals.
5. Downloads honour rate limits; the downloader is re-runnable and detects upstream changes by hash.
6. `scripts/check_all.py` passes (network tests marked `live`).

## 5. Out of scope
Case law, US state law (until D8), judgments from wenshu.court.gov.cn, indexing.

## 6. Open questions
- Which origin provides authoritative historical versions for each document?

## 7. Response
_Pending (corpus)._

## 8. Delivery
_Pending (corpus)._
