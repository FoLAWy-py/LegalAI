---
id: CHARTER-RETRIEVAL
owner: retrieval
status: active
updated: 2026-10-30
---

# Retrieval Charter

## Mission
Given a query, return the smallest set of exact source spans that contains what is needed to answer it.

## Owns
- Indexing `SourceDocument`s (lexical and semantic; hybrid by default), chunking along legal structure.
- Query understanding for search (expansion, legal-term synonyms), reranking.
- Filtering by jurisdiction and by validity on `as_of` **before** ranking.
- The `Retriever` implementation (law) and the `EvidenceRetriever` implementation (case files, ADR-0005).
- Case-file indexes are per `case_id`, stored under `<LEGALAI_DATA_DIR>/retrieval/`, and deleted with the case (P9).
- Cross-lingual search: Chinese queries find English sources and vice versa (ADR-0004).

## Does not own
Source acquisition and storage (corpus). Answer generation (reasoning). Judging correctness (verification).

## Interfaces
- **Consumes:** `LegalQuery`, `SourceDocument`, `CaseDocument`, ports `SourceStore`, `CaseFileStore` (injected, for indexing).
- **Provides:** `Retriever` and `EvidenceRetriever` implementations returning `SourceSpan`s whose offsets match the corpus text exactly.

## Quality bars
- Span fidelity: 100% of returned spans match `SourceStore.get_text` for their offsets.
- Zero spans outside the query jurisdiction or not in force on `as_of` unless explicitly requested.
- Recall@k and nDCG@k on the golden set (thresholds set by evaluation per use case).

## Reliability duties
P1 (spans are exact), P4 (jurisdiction and temporal filtering).
A search inside one case never returns spans from another case.
Missing results must be reported as empty, never padded with weakly related spans.
