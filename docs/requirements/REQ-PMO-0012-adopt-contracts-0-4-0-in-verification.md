---
id: REQ-PMO-0012
title: "Adopt contracts 0.4.0 in verification: per-citation reference dates, contract not-found error, traces"
from: pmo
to: verification
owner: pmo
status: open
priority: P0
created: 2026-10-30
updated: 2026-10-30
depends_on: [ADR-0007, REQ-PMO-0010]
---

# REQ-PMO-0012: Adopt contracts 0.4.0 in verification: per-citation reference dates, contract not-found error, traces

## 1. Context
Until verification checks each law citation against its own reference date, it checks every citation against
`as_of` and could pass a law version that was not in force on the date the outline declares (ADR-0007, limitation 1).
No producer may emit reference dates before this REQ is verified.
Adoption list: REQ-PMO-0010 §8. Design: ADR-0007.

## 2. Requirement
1. Each law citation MUST be checked for temporal validity against the `ReferenceDate.day` it names, or `query.as_of` when it names none.
2. Every `ReferenceDate.basis` and `.evidence` citation MUST be verified like any other citation (store resolves, text equals, quote verbatim, evidence belongs to the query's case). Each reference date gets its own report item (`item_id` = `reference_id`).
3. Stores' not-found MUST be caught as `legalai_contracts.DocumentNotFoundError` only; every other exception → `CHECK_ERROR` (ADR-0007 §3).
4. Every model-checked item MUST carry its `ModelTrace`s in `ItemVerification.traces`, with token counts when the provider reports them; the model id no longer needs to be packed into `method`.

## 3. Interface
`legalai_contracts` 0.4.0 (see ADR-0007). No further contract change expected; raise a REQ to architecture if one is needed.

## 4. Acceptance criteria
1. Adversarial tests on `ZZ` data: a citation in force on `as_of` but not on its declared reference date → `NOT_IN_FORCE`; a reference date whose basis quote is altered → not SUPPORTED; 0 false SUPPORTED overall.
2. A store raising a non-`DocumentNotFoundError` exception yields `CHECK_ERROR`; raising `DocumentNotFoundError` yields `CITATION_INVALID`.
3. Every model-checked item in tests has ≥ 1 trace; deterministically decided items have none.
4. All existing verification tests still pass; `scripts/check_all.py` passes.

## 5. Out of scope
Changes to contracts.

## 6. Open questions
- None.

## 7. Response
_Pending (verification)._

## 8. Delivery
_Pending (verification)._
