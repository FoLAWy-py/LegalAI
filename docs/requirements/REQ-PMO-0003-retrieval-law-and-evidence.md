---
id: REQ-PMO-0003
title: Provide law and case-file retrieval with jurisdiction and temporal filtering
from: pmo
to: retrieval
owner: pmo
status: delivered
priority: P1
created: 2026-10-30
updated: 2026-10-30
depends_on: [ADR-0004, ADR-0005]
---

# REQ-PMO-0003: Provide law and case-file retrieval with jurisdiction and temporal filtering

## 1. Context
Reasoning may cite only retrieved spans; retrieval quality bounds outline quality (P1, P4).
Sequencing (project owner, 2026-10-30): CN first. Chinese-language law and case files are the priority; cross-lingual
retrieval (ADR-0004) is still required.

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

Note added at delivery: the main-branch change to ADR-0006 (CN criminal cases, financial-crime focus) changes no
requirement here. The synthetic set was extended with fictional `ZZ` criminal and financial-crime law and case files.

## 8. Delivery
Delivered by retrieval, 2026-10-30.

- **What changed** (all under `departments/retrieval/`):
  - `src/legalai_retrieval/`: `law.py` (`LawRetriever`, the `Retriever` port), `cases.py` (`CaseEvidenceRetriever`, the
    `EvidenceRetriever` port), `index.py` (per-scope on-disk index, BM25 + coverage + RRF), `chunking.py` (structural
    chunker), `text.py` (CJK bigram / English analyzer, article-reference tokens), `glossary.py` +
    `resources/glossary_zh_en.tsv` (zh<->en search glossary), `embedding.py` (`Embedder` port,
    `SentenceTransformerEmbedder`, `HashingEmbedder`, `KNOWN_MODELS`, `DEFAULT_EMBEDDING_MODEL`), `config.py`, `errors.py`,
    `results.py`. The public API is listed in `CHARTER.md` (Interfaces). The charter now cites ADR-0006 instead of ADR-0005.
  - `pyproject.toml`: adds `numpy>=2.0`, and the optional extra `embeddings = ["sentence-transformers>=5.0"]` (torch is
    not installed by default). `uv.lock` updated.
  - `tests/`: 56 offline tests on in-memory `ZZ` fake stores, plus 5 `@pytest.mark.live` tests (one per model).
    Fixtures are in `tests/fixtures/`. They are fictional `ZZ`/`ZZ-OT` law in zh and en (contract, civil evidence, sale of
    goods, criminal law in 2 versions, criminal evidence, financial offences, a future-dated act, a near-duplicate in
    `ZZ-OT`) and 3 fictional cases (contract dispute, near-duplicate case, illegal deposit-taking case). The set has
    80 labelled law queries, 20 labelled case queries, 10 law negatives and 3 case negatives. Every title is marked
    SYNTHETIC.
- **How it works** (decisions for review):
  - **Filter, then rank.** One index directory per jurisdiction (`<data_dir>/retrieval/law/<J>/`). Candidates are the
    chunks with `jurisdiction == query.jurisdiction` and `in_force_on(as_of)`. BM25 df/avgdl are computed over the
    candidates only. A test shows that deleting every out-of-force version leaves scores identical.
  - **Chinese.** Overlapping CJK bigrams (no dictionary). Query coverage is measured per character, so cross-word
    bigrams do no harm. Stop characters and question fillers (什么时候, 多长…) are excluded from coverage. 第五百七十七条 /
    第577条 / Section 577 map to one token.
  - **Structure and pinpoints.** Law: one span per 条 / Article / Rule / Section (including 第X条之一). An article longer
    than 800 characters is split into 款 (`第X条第N款`). Chapter headings become indexing context only, never part of
    a span. Case files: line units that never cross a page, pinpoint `p. N` from `CaseDocument.page_of`.
  - **Eligibility (no padding).** A chunk is eligible if lexical coverage ≥ 0.6 (`DEFAULT_MIN_LEXICAL_COVERAGE`) or
    cosine ≥ the model's calibrated `min_similarity`. Eligible chunks are ordered by RRF (k=60). Nothing eligible means `[]`.
  - **Fail closed.** At query time each returned span is re-read from the store. Its sha256 and the store's full
    document metadata must equal what was indexed; otherwise `StaleIndexError` is raised. A jurisdiction or case that
    was never indexed raises `IndexNotFoundError`. An embedder or format mismatch raises `StaleIndexError` (rebuild needed).
  - **Case indexes** live in `<data_dir>/retrieval/cases/<sha256(case_id)>/`. `delete_case` removes the directory and
    any interrupted build.
- **How to verify:**
  - `uv run python scripts/check_all.py` runs the offline suite, with no network and no weights.
  - Live (needs local weights in the HF cache):
    `uv run --with 'sentence-transformers>=5.0' pytest -m live -s departments/retrieval/tests/test_live_embeddings.py`
- **Evidence:**
  - `check_all.py`: ALL CHECKS PASSED (308 passed, 6 deselected; retrieval 56 passed, 5 live deselected) after
    merging main (contracts 0.3.0).
  - **AC1** (`test_ac1_every_span_equals_store_text`, `test_ac1_fidelity_and_page_pinpoints`): every span returned for
    every set query equals `get_text`, carries the right `SourceKind`, and has a pinpoint. Case spans are checked
    against `page_of`.
  - **AC2** (`test_ac2_*`, `test_other_jurisdiction_near_duplicate_is_never_returned`, `test_temporal_versions`,
    `test_future_document_only_after_it_takes_effect`, `test_text_unique_to_another_case_is_not_found`): every query
    was run for 2 jurisdictions × 5 as-of dates and across 3 cases, with zero violations. Verbatim `ZZ-OT` text is
    never returned for `ZZ`. 2023 returns the 2020 version (二年). 第一百零三条之一 is never returned before 2024-03-01.
  - **AC3** (live, default model `Qwen/Qwen3-Embedding-0.6B`, hybrid + glossary, calibrated thresholds): cross-lingual
    expected span in top-5 for **37/39 = 0.95** (needs ≥ 0.90). zh-zh 35/35. All 10 law negatives and all 3 case
    negatives return `[]`. Case queries R@5 19/20.
  - **§6 model comparison** (same set, R@5; "sem" = semantic only, no glossary, no threshold; "hyb" = shipped config):

    | Model | License | Weights | zh-zh sem | x-lingual sem | x-lingual hyb | cases hyb | negatives `[]` | Gap: min positive / max negative sim |
    |---|---|---|---|---|---|---|---|---|
    | **Qwen/Qwen3-Embedding-0.6B** (default) | Apache-2.0 | 1.19 GB safetensors | 35/35 | 38/39 | 37/39 | 19/20 | 10/10 | 0.487 / 0.390, threshold 0.45 |
    | BAAI/bge-m3 | MIT | 2.27 GB pickle `.bin` | 35/35 | 37/39 | 38/39 | 20/20 | 9/10 | 0.477 / 0.549 (overlap), threshold 0.50 |
    | paraphrase-multilingual-MiniLM-L12-v2 | Apache-2.0 | 0.47 GB | 35/35 | 36/39 | 37/39 | 18/20 | 9/10 | 0.341 / 0.605 (overlap) |
    | multilingual-e5-base | MIT | 1.11 GB | 35/35 | 14/39 | 17/39 | 16/20 | 10/10 | not separable (0.759 / 0.840) |
    | multilingual-e5-small | MIT | 0.47 GB | 35/35 | 3/39 | 13/39 | 13/20 | 8/10 | not separable (0.733 / 0.861) |

    Qwen3-Embedding-0.6B was chosen for the best zh<->en semantic recall, the only clean similarity gap between
    positives and negatives, a permissive license and safetensors weights (no pickle). The e5 models are marked
    `recommended=False`.
  - **Offline floors** (`HashingEmbedder`, non-semantic, so this is not AC3): law zh-zh R@5 33/35, cross-lingual 23/39,
    case R@5 7/20. Asserted as regression floors.
  - **AC4: pending REQ-PMO-0005.** The evaluation set is not available yet. The only numbers so far are on
    retrieval's own synthetic set (above).
- **Known limitations:**
  1. **Calibration is not independent.** Thresholds (0.6 lexical, 0.45 Qwen3) and the glossary were tuned on the same
     small synthetic set that reports the results, all written by one author. The glossary was written before the
     queries, and its criminal additions before the criminal queries, but bias remains. Thresholds MUST be
     re-calibrated on the REQ-PMO-0005 golden set before release.
  2. **Hybrid R@1 is lower than semantic-only R@1** for strong models: Qwen3 overall 0.78 vs 0.88, en-en 3/6 vs 6/6.
     R@5 is unaffected. The fusion weights were not tuned, to avoid overfitting; this should be revisited with
     evaluation data.
  3. Long outline queries (cause of action plus facts) will rarely reach lexical coverage ≥ 0.6, so they depend on the
     semantic path. Reasoning should issue focused sub-queries per element.
  4. With `HashingEmbedder` (no real model), short paraphrased case queries return little or nothing. This fails
     closed by design, so production MUST wire a real local embedder.
  5. `SourceStore.list_documents(jurisdiction)` is assumed to return **all versions**. If corpus returns only
     current versions, past `as_of` queries will miss old law. To be confirmed with corpus (REQ-PMO-0002).
  6. Jurisdiction matching is exact (see §7.1). Traditional/Simplified Chinese is not normalized. Weights are loaded
     from the local HF cache or a path. Downloading them is a separate, explicit operator step.
  7. Interface must call `delete_case` when a case is deleted (P9). Deletion is an ordinary file removal, not secure erasure.
