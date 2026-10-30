---
id: CHARTER-VERIFICATION
owner: verification
status: active
updated: 2026-10-30
---

# Verification Charter

## Mission
Independently decide, item by item, whether an `EvidenceOutline` or `DraftAnswer` is supported by the sources it cites.

## Owns
- Deterministic checks (run first): span resolves in `SourceStore`; span text and quote match byte-for-byte;
  law document in force on `as_of`; jurisdiction matches; inference premises exist; evidence spans belong to the
  query's `case_id`.
- Model-based checks (run second): does the cited law establish the element; does the cited evidence bear on the
  element as the stated purpose claims; contradiction detection;
  using prompts and model choices independent from reasoning.
- The `Verifier` implementation and `VerificationReport`.

## Does not own
Writing or repairing answers (reasoning). Deciding what the user sees (interface — but it must obey the report).

## Interfaces
- **Consumes:** `EvidenceOutline`, `DraftAnswer`, ports `SourceStore`, `CaseFileStore` (injected).
- **Provides:** a `Verifier` implementation producing `VerificationReport`.

## Quality bars
- Deterministic checks: zero false PASS on the adversarial citation set (fabricated, altered, outdated quotes).
- Entailment check precision/recall on labelled claims (thresholds set by evaluation; precision prioritized).
- Any internal error yields `CHECK_ERROR` for the affected claim, never `SUPPORTED`.

## Reliability duties
P1, P2 (independence is this department's reason to exist), P3, P4.
Never trust text carried inside the draft: always re-read from `SourceStore`.
