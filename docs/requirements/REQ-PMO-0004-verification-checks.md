---
id: REQ-PMO-0004
title: Verify evidence outlines — deterministic checks first, model checks second
from: pmo
to: verification
owner: pmo
status: open
priority: P1
created: 2026-10-30
updated: 2026-10-30
depends_on: [ADR-0003, ADR-0005]
---

# REQ-PMO-0004: Verify evidence outlines — deterministic checks first, model checks second

## 1. Context
Generation and verification are independent (P2); nothing unverified reaches the user (P3).

## 2. Requirement
1. Phase A (deterministic) MUST check every element citation and evidence-link citation: span resolves in the
   right store (`SourceKind`); stored text equals span text; quote is verbatim; law version in force on `as_of`;
   law jurisdiction matches; evidence document belongs to the query `case_id`. Any failure decides the item's verdict.
2. Phase B (model-based) runs only on items passing Phase A: does the cited law establish the element; does the
   cited evidence bear on the element as `purpose` claims. Prompts are verification's own; model from injected config.
3. Report items cover every element and every link (`item_id` = `element_id` / `link_id`). Errors → `CHECK_ERROR`.
4. `verify_outline` and `verify` (DraftAnswer) both implemented; package MUST NOT read env vars.

## 3. Interface
Ports `Verifier`, `SourceStore`, `CaseFileStore`; `EvidenceOutline`, `VerificationReport`.

## 4. Acceptance criteria
1. Adversarial suite (built in-package with `ZZ` fakes): fabricated doc id, altered quote, shifted offsets,
   outdated version, wrong jurisdiction, evidence from another case — **0 false SUPPORTED**.
2. Phase A runs without any model call (tested with a model client that fails if called).
3. Phase B tested with mocked model responses, including malformed JSON → `CHECK_ERROR`, not SUPPORTED.
4. A live smoke test (`@pytest.mark.live`) runs Phase B against the configured DeepInfra model.
5. `scripts/check_all.py` passes.

## 5. Out of scope
Repairing outlines; judging whether gaps are real (evaluation measures that).

## 6. Open questions
- None.

## 7. Response
_Pending (verification)._

## 8. Delivery
_Pending (verification)._
