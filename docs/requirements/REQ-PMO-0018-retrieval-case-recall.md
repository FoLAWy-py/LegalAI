---
id: REQ-PMO-0018
title: Raise case-file evidence recall without padding
from: pmo
to: retrieval
owner: pmo
status: open
priority: P1
created: 2026-10-31
updated: 2026-10-31
depends_on: [REQ-PMO-0003, REQ-PMO-0005]
---

# REQ-PMO-0018: Raise case-file evidence recall without padding

## 1. Context
PMO verification of REQ-PMO-0003 (2026-10-30, commit bcfa68a) ran `LawRetriever` / `CaseEvidenceRetriever` with
`Qwen/Qwen3-Embedding-0.6B` through the evaluation runner on `ZZ-SYNTH-CRIM-OUTLINE` (REQ-PMO-0005), using the
oracle builder:

| metric | k=5 | k=10 |
|---|---|---|
| law recall@k | 32/36 (0.89) | 32/36 |
| case-file recall@k | **25/62 (0.40)** | 25/62 |

Recall does not change from k=5 to k=10, so the eligibility thresholds (anti-padding rule) cut it, not k. At 0.40,
an outline builder never sees most of the evidence, and the outline then reports **false gaps** (P1, P3). Retrieval's
own thresholds were calibrated on its own synthetic set (REQ-PMO-0003 §8 says so).

## 2. Requirement
1. Diagnose the 37 missed case-file targets: threshold, chunking/line granularity, query formulation by the runner,
   tokenization of Chinese, or the glossary. Record the breakdown.
2. Improve case-file recall while keeping the no-padding rule (REQ-PMO-0003 §2.5): no span below a documented
   threshold is ever returned.
3. Calibrate on a split that is **disjoint** from the split you report on. Do not tune on the reported numbers.
4. If the cause is in the runner's query formulation (evaluation-owned), file a REQ to evaluation; don't work around it.

## 3. Interface
`EvidenceRetriever`, `Retriever` (no contract change expected).

## 4. Acceptance criteria
1. On the held-out split of the evaluation set, case-file recall@10 ≥ 0.80 and law recall@10 ≥ 0.89, with the real
   local embedder.
2. Precision does not collapse: on the same split, the share of returned case spans that are expected links is reported,
   and negatives still return `[]`.
3. Every REQ-PMO-0003 acceptance criterion still holds (AC1/AC2 zero violations).
4. `scripts/check_all.py` passes.

## 5. Out of scope
Answer generation; contract changes.

## 6. Open questions
- If ≥ 0.80 is unreachable without padding, report the best achievable value and the reason. PMO will then decide
  whether the gate or the design changes.

## 7. Response
_Pending (retrieval)._

## 8. Delivery
_Pending (retrieval)._
