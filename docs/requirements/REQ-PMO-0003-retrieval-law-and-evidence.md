---
id: REQ-PMO-0003
title: Provide law and case-file retrieval with jurisdiction and temporal filtering
from: pmo
to: retrieval
owner: pmo
status: in-progress
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
Decision: **accept** (retrieval, 2026-10-30). Sequencing per the 2026-10-30 PMO amendment: CN (Chinese text) first,
cross-lingual zh <-> en kept in scope.

How each requirement will be met, and decisions the issuer should review:
1. **Filter before rank.** The candidate set for a law query is fixed first: chunks whose document has
   `jurisdiction == query.jurisdiction` (exact string match) and `in_force_on(query.as_of)`. BM25 statistics
   (document frequency, average length) are computed over that candidate set only, so documents outside it
   cannot affect scores. *Decision for PMO:* matching is exact, so a `US-CA` query does not return `US` federal
   law. Whether a sub-jurisdiction query should include its parent needs a PMO/architecture decision; until then
   it is fail-closed.
2. **Case isolation.** Each case gets its own index directory (`<data_dir>/retrieval/cases/<sha256(case_id)>/`),
   loaded only for that `case_id`. The manifest stores the `case_id` and is checked on load.
3. **Hybrid, cross-lingual, local.** Lexical BM25 (Chinese: CJK character bigrams, no dictionary; English: light
   stemming) plus dense embeddings behind an injected `Embedder` port. A bilingual legal-term glossary (search aid only,
   not an equivalence claim, ADR-0004 §6) expands queries across zh/en. The real embedder loads weights from local
   files only (`local_files_only`), so no network is used at query time. Unit tests use a deterministic fake embedder.
4. **Indexes** are built from the injected `SourceStore` / `CaseFileStore` and written under `<data_dir>/retrieval/`.
   `data_dir` is injected by interface (no env reads). Case indexes can be deleted per case.
5. **No padding.** A span is eligible only if its lexical query coverage or its semantic similarity reaches a
   documented threshold. Ranking among eligible spans uses reciprocal-rank fusion. If nothing is eligible, the
   result is `[]`. An unbuilt index or a jurisdiction that was never indexed raises an error rather than returning
   `[]`, so misconfiguration stays visible.
6. **Span fidelity.** Returned span text is re-read from the store at query time and checked against the indexed
   content hash. A mismatch raises `StaleIndexError` and nothing is returned.

§6 answer: candidates are open-weight multilingual models that can run locally (BAAI/bge-m3, intfloat/multilingual-e5-*,
sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2). The choice and comparison evidence are in §8.
AC4: the evaluation set (REQ-PMO-0005) is not available yet. §8 reports recall on retrieval's own synthetic bilingual
`ZZ` set and marks the evaluation-set numbers as pending.

## 8. Delivery
_Pending (retrieval)._
