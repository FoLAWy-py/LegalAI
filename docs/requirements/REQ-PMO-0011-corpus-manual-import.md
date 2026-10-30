---
id: REQ-PMO-0011
title: Add a manual-import path for official documents that refuse automated retrieval
from: pmo
to: corpus
owner: pmo
status: open
priority: P1
created: 2026-10-30
updated: 2026-10-30
depends_on: [REQ-PMO-0002]
---

# REQ-PMO-0011: Add a manual-import path for official documents that refuse automated retrieval

## 1. Context
Under the amended origin rule (REQ-PMO-0002 §7, PMO decisions 2026-10-30), `www.npc.gov.cn` may refuse our honest
crawler. The access-control rule forbids getting past a refusal. Laws published only there (the Criminal Law, its
amendment acts, the Criminal Procedure Law, the Commercial Banking Law, the Securities Investment Fund Law) must
still enter the corpus with full provenance (P1, P5).

## 2. Requirement
1. Corpus MUST support importing an official document that a **person** saved from an official origin in a normal
   browser session: a raw file (HTML as saved, or the official PDF) placed in an inbox under
   `<data_dir>/corpus/inbox/`, plus a sidecar record of the official URL, the time saved, and who saved it.
2. Manual imports go through the same pipeline as fetched files: content-addressed raw store, mechanical extraction,
   look-alike code point policy, manifest evidence quotes re-found verbatim, spot check. They MUST NOT skip any check.
3. Provenance MUST record `acquisition: manual` together with the sidecar fields, so verification and evaluation can
   tell fetched documents from manually imported ones. `source_uri` is the official URL, never a local path.
4. Imports are allowed only for origins marked `approved` or `manual-only` in the registry. Add the status
   `manual-only`, use it for `www.npc.gov.cn` when the honest crawler is refused, and record the refusal evidence.
   `flk.npc.gov.cn` stays `rejected`; no import from it.
5. Corpus MUST write `departments/corpus/docs/manual-import.md`: a step-by-step guide for the person saving the
   files (which pages, how to save, how to fill the sidecar), plus the list of documents needed for REQ-PMO-0002 §2.2
   that require manual import.
6. The access-control rule applies: the fetcher MUST NOT alter its UA or retry around a refusal. Any code that did
   this MUST be removed, and a test MUST pin that a 403 is final.

## 3. Interface
`SourceDocument` (`source_uri`, provenance), `SourceStore`. No contract change expected; raise a REQ to architecture
if one is needed.

## 4. Acceptance criteria
1. An end-to-end test imports a synthetic `ZZ` HTML file with a sidecar and produces a valid stored version whose
   provenance says `acquisition: manual`.
2. A test proves the import is refused without a sidecar, for a `rejected` origin, and when an evidence quote is not
   found verbatim.
3. A test proves the fetcher makes no further request to a host after a 403, and that its UA is constant.
4. The 9 raw NPC files are deleted, and the deletion is logged (REQ-PMO-0002 §7, decision 3).
5. `manual-import.md` exists and lists the concrete documents needed.
6. `scripts/check_all.py` passes.

## 5. Out of scope
Any automated access to sites that refused or forbid it.

## 6. Open questions
- None.

## 7. Response
_Pending (corpus)._

## 8. Delivery
_Pending (corpus)._
