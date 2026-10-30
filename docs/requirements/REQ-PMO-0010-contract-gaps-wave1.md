---
id: REQ-PMO-0010
title: Close contract gaps found in Wave 1 (reference dates, traces, store errors, hashing)
from: pmo
to: architecture
owner: pmo
status: open
priority: P1
created: 2026-10-30
updated: 2026-10-30
depends_on: [ADR-0006, REQ-PMO-0001, REQ-PMO-0004, REQ-PMO-0005, REQ-PMO-0008]
---

# REQ-PMO-0010: Close contract gaps found in Wave 1

## 1. Context
Wave 1 deliveries (REQ-PMO-0001, 0004, 0005, 0007) each worked around a gap in contracts 0.3.0 and reported it:
- **Reference dates** (ADR-0006 §6.2): one `LegalQuery.as_of` cannot express a criminal case where the conduct
  (pilot SPP 检例第175号: 2014–2018) and the judgment (2021) fall under different law versions. The pilot (REQ-PMO-0008)
  needs this before evaluation builds it.
- **Token cost** (REQ-ARCH-0001 AC2): `ModelTrace` has no token-usage fields.
- **Store "not found"**: the `SourceStore` / `CaseFileStore` ports define no error. Verification maps `LookupError`
  to CITATION_INVALID and anything else to CHECK_ERROR. Casefile raises its own `DocumentNotFoundError`.
- **`content_sha256` semantics**: the contract does not say whether it hashes the stored text or the original file
  bytes. Casefile hashes stored UTF-8 text. Verification does not check it at all.
- **Verification traceability** (P5): `VerificationReport` has no `ModelTrace`. Model id and prompt version are
  packed into `ItemVerification.method` strings.

## 2. Requirement
All changes MUST be additive: a minor bump, no field removed, renamed or tightened, and existing tests unchanged.
1. **Reference dates:** contracts MUST let an outline state, per element legal basis, which reference date that
   citation's law version was selected for. Examples: conduct date or period, adjudication date. Verification can then
   check temporal validity per citation. Which date governs is a legal rule. The contract only carries the dates and
   the cited basis for the choice; it MUST NOT encode the rule. Cases with a single `as_of` keep working unchanged.
2. **ModelTrace:** add optional token-usage fields (input/output tokens) and leave room for cost.
3. **Store errors:** define a contract exception (or exception hierarchy) for "document/version not found", to be
   raised by store implementations. Document how consumers must treat other exceptions (fail closed).
4. **Hash semantics:** specify exactly what `content_sha256` covers for `SourceDocument` and `CaseDocument`. Record it
   in a standard or ADR. Add an optional field for the original-file hash if needed.
5. **Verification traces:** `VerificationReport` (or its items) MUST be able to carry `ModelTrace`s.
6. Record decisions in an ADR or standard. Do not edit department code. Departments adopt the changes through their own REQs.

## 3. Interface
`LegalQuery`, `Citation` / `Element`, `ModelTrace`, `SourceStore`, `CaseFileStore`, `SourceDocument`, `CaseDocument`,
`VerificationReport`.

## 4. Acceptance criteria
1. A contract test builds a valid criminal outline on `ZZ` data whose element citations use two different reference
   dates, each recorded on the outline. The same outline without the new fields still validates.
2. Contract tests cover token fields, the not-found exception, and the verification trace field.
3. Hash semantics are written down and referenced from the `content_sha256` field docstrings.
4. `CONTRACT_VERSION` minor bump. All existing tests in every department pass unchanged. `scripts/check_all.py` passes.

## 5. Out of scope
Jurisdiction applicability between `US` and `US-XX` (US deferred, ADR-0006 §6.3); department adoption.

## 6. Open questions
- Should the reference date live on `Citation` (per citation) or on `Element` (per element)? Architecture decides
  and records why.

## 7. Response
_Pending (architecture)._

## 8. Delivery
_Pending (architecture)._
