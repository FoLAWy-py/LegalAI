---
id: REQ-PMO-0003
title: Provide law and case-file retrieval with jurisdiction and temporal filtering
from: pmo
to: retrieval
owner: pmo
status: open
priority: P1
created: 2026-10-30
updated: 2026-10-30
depends_on: [ADR-0004, ADR-0005]
---

# REQ-PMO-0003: Provide law and case-file retrieval with jurisdiction and temporal filtering

## 1. Context
Reasoning may cite only retrieved spans; retrieval quality bounds outline quality (P1, P4).

## 2. Requirement
1. `Retriever` MUST return law spans filtered to the query jurisdiction and to versions in force on `as_of`
   **before** ranking; spans align to legal structure (article/rule/paragraph) and carry a pinpoint.
2. `EvidenceRetriever` MUST search only the given `case_id`'s documents; spans carry page pinpoints.
3. Search MUST work across languages (Chinese query ↔ English source and vice versa) and be hybrid
   (lexical + semantic). Embedding models MUST run locally (ADR-0003: no other remote services).
4. Indexes are built from injected `SourceStore` / `CaseFileStore`; stored under `<data_dir>/retrieval/`;
   case indexes are deletable per case.
5. No results → empty list. Never pad with weakly related spans below a documented score threshold.

## 3. Interface
Ports `Retriever`, `EvidenceRetriever`, `SourceStore`, `CaseFileStore`; `SourceSpan` with correct `source`.

## 4. Acceptance criteria
1. Using in-memory `ZZ` fake stores: 100% of returned spans equal `get_text` for their offsets.
2. Zero returned spans from another jurisdiction, from a version not in force on `as_of`, or from another case.
3. Cross-lingual test: for a synthetic bilingual set, the expected span is in top-5 for ≥ 90% of queries.
4. Recall@k on the evaluation set is reported in §8 (gate thresholds owned by evaluation).
5. `scripts/check_all.py` passes.

## 5. Out of scope
Answer generation, model calls to remote providers.

## 6. Open questions
- Which local multilingual embedding model? Record evaluation evidence for the choice in §8.

## 7. Response
_Pending (retrieval)._

## 8. Delivery
_Pending (retrieval)._
