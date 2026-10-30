---
id: REQ-PMO-0014
title: "Adopt contracts 0.4.0 in corpus: contract not-found error and original_sha256"
from: pmo
to: corpus
owner: pmo
status: open
priority: P2
created: 2026-10-30
updated: 2026-10-30
depends_on: [ADR-0007, REQ-PMO-0010]
---

# REQ-PMO-0014: Adopt contracts 0.4.0 in corpus: contract not-found error and original_sha256

## 1. Context
ADR-0007 §3–§4 define a contract not-found error and an optional original-file hash.
Adoption list: REQ-PMO-0010 §8. Design: ADR-0007.

## 2. Requirement
1. `store.DocumentNotFound` MUST subclass `legalai_contracts.DocumentNotFoundError`.
2. `SourceDocument.original_sha256` MUST be set from the raw-file hash already in provenance.

## 3. Interface
`legalai_contracts` 0.4.0 (see ADR-0007). No further contract change expected; raise a REQ to architecture if one is needed.

## 4. Acceptance criteria
1. A test catches a missing version as `legalai_contracts.DocumentNotFoundError`.
2. Every stored version's `original_sha256` equals its raw file's hash (including manual imports).
3. `scripts/check_all.py` passes.

## 5. Out of scope
Changes to contracts.

## 6. Open questions
- None.

## 7. Response
_Pending (corpus)._

## 8. Delivery
_Pending (corpus)._
