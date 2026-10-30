---
id: REQ-PMO-0016
title: "Adopt contracts 0.4.0 in interface: render reference dates, gate on verification support"
from: pmo
to: interface
owner: pmo
status: open
priority: P1
created: 2026-10-30
updated: 2026-10-30
depends_on: [ADR-0007, REQ-PMO-0010, REQ-PMO-0012]
---

# REQ-PMO-0016: Adopt contracts 0.4.0 in interface: render reference dates, gate on verification support

## 1. Context
Outlines may now declare reference dates (ADR-0007 §1). Showing them is part of transparency (P4, P8).
Adoption list: REQ-PMO-0010 §8. Design: ADR-0007.

## 2. Requirement
1. Renderings MUST show each reference date (kind, day, period, description, its basis) and mark which legal-basis citations use it.
2. Until REQ-PMO-0012 is verified, the pipeline MUST refuse an outline that carries reference dates, with a clear message; afterwards the gate is lifted by config/version check, not by deleting the test.
3. Show token usage per run in the audit log when present.

## 3. Interface
`legalai_contracts` 0.4.0 (see ADR-0007). No further contract change expected; raise a REQ to architecture if one is needed.

## 4. Acceptance criteria
1. Synthetic end-to-end test with two reference dates renders both and their citations.
2. Test: with the gate on, an outline carrying reference dates is refused.
3. `scripts/check_all.py` passes.

## 5. Out of scope
Changes to contracts.

## 6. Open questions
- None.

## 7. Response
_Pending (interface)._

## 8. Delivery
_Pending (interface)._
