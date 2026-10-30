---
id: REQ-PMO-0015
title: "Adopt contracts 0.4.0 in reasoning: token fields and reference dates"
from: pmo
to: reasoning
owner: pmo
status: open
priority: P1
created: 2026-10-30
updated: 2026-10-30
depends_on: [ADR-0007, REQ-PMO-0010, REQ-PMO-0012]
---

# REQ-PMO-0015: Adopt contracts 0.4.0 in reasoning: token fields and reference dates

## 1. Context
Contracts 0.4.0 add token usage to `ModelTrace` and per-citation reference dates (ADR-0007 §1–§2, ADR-0006 §6.2).
Adoption list: REQ-PMO-0010 §8. Design: ADR-0007.

## 2. Requirement
1. Every `ModelTrace` MUST fill `input_tokens` / `output_tokens` when the provider reports them (`None` otherwise, never 0).
2. Builders MAY emit `ReferenceDate`s only when retrieved law supports the choice of date (cited in `basis`); otherwise use `as_of` and, where the conduct period and as-of date may call for different law versions, flag it or abstain (ADR-0006 §6.2). Reference dates are emitted only after REQ-PMO-0012 is verified; until then this capability stays behind a config switch that defaults to off.

## 3. Interface
`legalai_contracts` 0.4.0 (see ADR-0007). No further contract change expected; raise a REQ to architecture if one is needed.

## 4. Acceptance criteria
1. Mocked tests: token fields filled from provider usage; missing usage → `None`.
2. Mocked test: a reference date without a law basis is never emitted; with the switch off, no reference dates appear.
3. `scripts/check_all.py` passes.

## 5. Out of scope
Changes to contracts.

## 6. Open questions
- None.

## 7. Response
_Pending (reasoning)._

## 8. Delivery
_Pending (reasoning)._
