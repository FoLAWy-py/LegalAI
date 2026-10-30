---
id: REQ-ARCH-0001
title: Run an agent framework spike to decide ADR-0002
from: architecture
to: reasoning
owner: architecture
status: open
priority: P1
created: 2026-10-30
updated: 2026-10-30
depends_on: [ADR-0002, ADR-0003, ADR-0005, REQ-PMO-0005]
---

# REQ-ARCH-0001: Run an agent framework spike to decide ADR-0002

## 1. Context
ADR-0002 is `proposed`. We need evidence, not opinion, before committing the reasoning
harness to a framework (P6, P7).

## 2. Requirement
1. Reasoning MUST implement the `OutlineBuilder` port (`legalai_contracts.ports`) with at least two
   candidate approaches from ADR-0002 (one MUST be a plain own loop over the `openai` SDK; the other
   Pydantic AI or LangGraph), both against the DeepInfra endpoint configured per ADR-0003.
2. Both MUST route model calls through one adapter that emits a `ModelTrace`.
3. Both MUST produce `EvidenceOutline` objects that pass contract validation, using only spans
   returned by injected `Retriever` / `EvidenceRetriever` (`ZZ` in-memory fakes are acceptable for the spike).
4. Agent loops MUST be bounded (max turns, tool allow-list) and the bounds MUST be configurable.

## 3. Interface
`LegalQuery`, `SourceSpan`, `EvidenceOutline`, `ModelTrace`, ports `Retriever`, `EvidenceRetriever`, `OutlineBuilder`.
No contract changes expected; if any are needed, raise a REQ to architecture.

## 4. Acceptance criteria
1. Both implementations pass the reasoning test suite with mocked model calls (no network).
2. Using the evaluation runner (REQ-PMO-0005 — evaluation imports reasoning's public API; reasoning never imports
   evaluation) on the synthetic `ZZ` case set (≥ 10 cases), a report compares: contract-valid output
   rate, share of citations whose quote exactly matches a retrieved span, element recall vs. the synthetic
   expected outline, gap correctness, behaviour on cases with no applicable law, latency, token cost.
3. The report recommends one option with reasoning, recorded in §8.
4. `scripts/check_all.py` passes.

## 5. Out of scope
Real-jurisdiction corpus, UI, production deployment.

## 6. Open questions
- Does either framework make it hard to enforce "only cite retrieved spans"?
- How reliable is the configured model's JSON / structured output mode, and does it need schema-repair retries?

## 7. Response
_Pending (reasoning)._

## 8. Delivery
_Pending (reasoning)._
