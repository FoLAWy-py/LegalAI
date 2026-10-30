---
id: REQ-PMO-0002
title: Assess origins and ingest v1 CN criminal law with versions
from: pmo
to: corpus
owner: pmo
status: open
priority: P1
created: 2026-10-30
updated: 2026-10-30
depends_on: [ADR-0004, ADR-0005]
---

# REQ-PMO-0002: Assess origins and ingest v1 CN criminal law with versions

## 1. Context
Elements must be grounded in authoritative, versioned law (P1, P4, P5). Scope per ADR-0005.

**Sequencing (project owner, 2026-10-30):** CN first; US law follows in a separate REQ once the CN
vertical slice is confirmed end to end. **Practice area (project owner, 2026-10-30, revises D6):** CN **criminal**
cases replace civil contract disputes; ADR-0005 is being amended accordingly. **Origin approval** is delegated by the project owner to the
Program Office and is decided by the rule in §2.1 below.

Lesson from the Yu Huan pilot (PMO check, 2026-10-30): a local "public text extract" labelled as an official
SPC capture differed from the official page (sentences missing, holdings reworded). Captures MUST therefore be
byte-faithful to the official rendering, never re-typed, summarised or copied from mirrors.

## 2. Requirement
1. Corpus MUST write `departments/corpus/docs/origins.md` assessing each candidate origin in the charter:
   terms of use, robots policy, rate limits, formats, how versions/effective dates are obtained. Each origin is
   marked approved / rejected with reasons. Only approved origins may be downloaded.
   **Approval rule (PMO):** an origin is approved only if it is the official publication of the issuing body
   (e.g. the NPC national laws database for laws, the SPC website for judicial interpretations, the SPP website for
   SPP-issued documents), its terms and
   robots policy permit automated retrieval at a polite rate, and it states or allows deriving effective dates.
   Mirrors, commercial databases and aggregators are rejected. wenshu.court.gov.cn is rejected for v1.
   When an origin's terms are ambiguous, mark it `pending-pmo` and do not download.
2. Corpus MUST ingest, from approved origins, **CN criminal law**: the Criminal Law (刑法) as amended — every
   consolidated version in force from 2021-01-01 onward, and the amendment acts (修正案) that produced them; the
   Criminal Procedure Law (刑事诉讼法); the SPC interpretation on applying the Criminal Procedure Law; and the
   official provisions on examining and judging evidence and on excluding illegal evidence in criminal cases
   (identify the exact official titles, issuers and versions from the official sources). Corpus SHOULD also ingest
   the SPP rules of criminal procedure for procuratorates if its origin is approved. For the v1 pilot case
   (SPC Guiding Case 270, REQ-PMO-0008), corpus MUST also ingest the joint opinions on handling drunk-driving criminal
   cases: the version cited by that case (高检发办字〔2023〕187号) and the version it replaced, if any, as in force in
   2022. Identify both from official sources. All versions with correct
   `effective_from` / `effective_to` taken from the official source (never from memory). Where only an amendment
   act and no official consolidated text exists for some version, record that and do not construct a consolidated
   text yourself. `origins.md` also assesses the US candidates so the US REQ can start quickly, but
   no US text is downloaded under this REQ.
3. Text MUST be stored in the original language, structure preserved so article/rule pinpoints can be derived.
4. A `SourceStore` implementation MUST serve documents and exact text ranges.
5. US federal and state layers are deferred to a later REQ; design MUST allow adding them without contract change.

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
Civil law (no longer v1 scope), case law incl. guiding cases (later REQ), all US law (later REQ), judgments from wenshu.court.gov.cn, indexing.

## 6. Open questions
- Which origin provides authoritative historical versions for each document?

## 7. Response
_Pending (corpus)._

## 8. Delivery
_Pending (corpus)._
