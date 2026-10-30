---
id: ADR-0005
title: v1 use case — evidence outline (proof chart with gaps) for civil contract disputes
owner: architecture
status: superseded
deciders: [project owner]
superseded_by: ADR-0006
updated: 2026-10-30
---

# ADR-0005: v1 use case — evidence outline (proof chart with gaps)

## Context
Project owner decisions (2026-10-30): D2 evidence outline as a **proof chart with gap analysis**;
D6 practice area **civil contract disputes**; D7 US scope **federal + one state** (state pending, D8);
D9 inputs are **digital documents only** (Word, text, PDFs with a text layer; no OCR).

## Decision

### What the system produces
Given a case (a set of case files), a jurisdiction, an as-of date, the user's party role and a cause of
action, the system produces an `EvidenceOutline`:

1. **Elements** — what must be proved for the cause of action. Each element cites the **law** that
   establishes it (statute, judicial interpretation, or case law) and, where stated by law, who bears the burden.
2. **Evidence links** — passages from the **case files** mapped to elements, each with an exact citation
   (document, page, quote), whether it supports or contradicts the element, and its purpose (证明目的).
3. **Gaps** — every element without adequate supporting evidence is listed explicitly.
   Coverage is total: each element ends up with a supporting link or a gap — never silently omitted.

A CN-style evidence list (证据目录) and a US-style proof chart are **renderings** of the same outline (interface).

### Two kinds of sources
| Kind | Owner | Store port | Confidential |
|---|---|---|---|
| Law (statutes, interpretations, cases) | corpus | `SourceStore` | no (public) |
| Case files (contracts, emails, invoices, pleadings) | **casefile** (new department) | `CaseFileStore` | **yes** (P9) |

Every `SourceSpan` states which kind it points to. Element legal bases MUST cite law; evidence links MUST cite case files.

### Legal scope for v1
- **CN:** Civil Code (contract book), Civil Procedure Law, and the Supreme People's Court provisions on evidence
  in civil procedure, plus related judicial interpretations, from official public sources.
- **US:** Federal Rules of Evidence and Federal Rules of Civil Procedure; substantive contract law of the state
  chosen in D8 (state statutes incl. its UCC Article 2 enactment, and state case law from public sources).
  Copyrighted secondary sources (e.g. Restatements) are not ingested.

## Consequences
- New department `casefile`; contracts v0.2.0 add `CaseDocument`, `SourceKind`, outline types and ports.
- Verification checks law citations against `SourceStore` and evidence citations against `CaseFileStore`.
- Evaluation builds golden outlines per jurisdiction, reviewed by a qualified person.

## Validation
Vertical slice passes the release gate on golden sets for CN and the chosen US state.
