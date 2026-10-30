---
id: REQ-<FROM>-<NNNN>
title: <imperative, one line>
from: <issuing department>
to: <receiving department>
owner: <issuing department>
status: draft
priority: P2
created: YYYY-MM-DD
updated: YYYY-MM-DD
depends_on: []
---

# REQ-<FROM>-<NNNN>: <title>

<!-- Sections 1–6: written by the ISSUER. Frozen once status = accepted. -->

## 1. Context
Why this is needed. Link to the principle, ADR or upstream REQ that motivates it.

## 2. Requirement
What must be delivered, stated as MUST / SHOULD rules. Describe the *what*, not the *how*.

## 3. Interface
Contract types and ports involved (`legalai_contracts.*`). If a new or changed contract is needed,
link the REQ to architecture that covers it.

## 4. Acceptance criteria
Numbered, testable, binary. Include evaluation metrics and thresholds when legal-output quality is affected.
1. ...

## 5. Out of scope
What this REQ explicitly does not ask for.

## 6. Open questions
Questions for the receiver. Answered in §7.

<!-- Sections 7–8: written by the RECEIVER. -->

## 7. Response
Decision: accept | reject | counter-proposal. Reasoning, estimate, answers to §6.

## 8. Delivery
- What changed (paths, public API):
- How to verify (commands):
- Evidence (test output, eval scores):
- Known limitations:

<!-- Verification is done by the ISSUER, who then sets status: verified. -->
