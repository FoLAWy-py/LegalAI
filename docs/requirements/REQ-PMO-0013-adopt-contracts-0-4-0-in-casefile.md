---
id: REQ-PMO-0013
title: "Adopt contracts 0.4.0 in casefile: contract not-found error and original_sha256"
from: pmo
to: casefile
owner: pmo
status: open
priority: P2
created: 2026-10-30
updated: 2026-10-30
depends_on: [ADR-0007, REQ-PMO-0010]
---

# REQ-PMO-0013: Adopt contracts 0.4.0 in casefile: contract not-found error and original_sha256

## 1. Context
ADR-0007 §3–§4 define a contract not-found error and an optional original-file hash.
Adoption list: REQ-PMO-0010 §8. Design: ADR-0007.

## 2. Requirement
1. casefile's `DocumentNotFoundError` MUST subclass `legalai_contracts.DocumentNotFoundError` (import the contract class under an alias); public behaviour otherwise unchanged.
2. `CaseDocument.original_sha256` MUST be set from the original-file hash casefile already keeps.

## 3. Interface
`legalai_contracts` 0.4.0 (see ADR-0007). No further contract change expected; raise a REQ to architecture if one is needed.

## 4. Acceptance criteria
1. A test catches a missing document as `legalai_contracts.DocumentNotFoundError`.
2. Every ingested test document has `original_sha256` equal to the sha256 of the original bytes.
3. `scripts/check_all.py` passes.

## 5. Out of scope
Changes to contracts.

## 6. Open questions
- None.

## 7. Response
_Pending (casefile)._

## 8. Delivery
_Pending (casefile)._
