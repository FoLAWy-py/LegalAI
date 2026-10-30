---
id: REQ-PMO-0017
title: "Adopt contracts 0.4.0 in evaluation: traces, tokens and cost in reports"
from: pmo
to: evaluation
owner: pmo
status: open
priority: P1
created: 2026-10-30
updated: 2026-10-30
depends_on: [ADR-0007, REQ-PMO-0010]
---

# REQ-PMO-0017: Adopt contracts 0.4.0 in evaluation: traces, tokens and cost in reports

## 1. Context
REQ-ARCH-0001 AC2 needs token cost; ADR-0007 §2, §5 add token fields and verification traces.
Adoption list: REQ-PMO-0010 §8. Design: ADR-0007.

## 2. Requirement
1. Reports MUST include token usage per builder and verifier from `ModelTrace` / `ItemVerification.traces`, and cost computed from a pinned, dated price table stored in the dataset/report config (never fetched live).
2. Fake stores SHOULD raise `legalai_contracts.DocumentNotFoundError`.
3. Synthetic dataset SHOULD include at least one case with two reference dates, for use once REQ-PMO-0012 is verified.

## 3. Interface
`legalai_contracts` 0.4.0 (see ADR-0007). No further contract change expected; raise a REQ to architecture if one is needed.

## 4. Acceptance criteria
1. Report test with hand-computed token and cost totals.
2. `scripts/check_all.py` passes.

## 5. Out of scope
Changes to contracts.

## 6. Open questions
- None.

## 7. Response
_Pending (evaluation)._

## 8. Delivery
_Pending (evaluation)._
