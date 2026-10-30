---
id: PRINCIPLES
owner: architecture
status: active
updated: 2026-10-30
---

# Reliability & Accuracy Principles

These principles override convenience, performance and feature scope. Each one names the
department that enforces it and how. A change that weakens any principle requires an ADR
accepted by the project owner.

## P1. Grounded or silent

Every legal assertion (rule, holding, obligation, deadline, definition) MUST cite at least one
`SourceSpan`: a specific document **version** with character offsets, and an **exact quote** that
appears verbatim in that span. A claim without a valid citation MUST NOT reach the user.

- Enforced by: `contracts` (validators reject a quote that is not a substring of the span),
  `verification` (re-resolves every span against the source store), `interface` (renders only verified claims).

## P2. Generation and verification are independent

The component that writes an answer never certifies it. `verification` is a separate department
with its own prompts, its own model-call code and, where practical, a different model or method
(deterministic checks first, model-based checks second). Reasoning cannot import verification and vice versa.

- Enforced by: `scripts/check_boundaries.py`, department charters.

## P3. Fail closed

When evidence is missing, conflicting, out of jurisdiction, out of date, or a check errors, the
system MUST abstain or flag — never guess. An abstention with a reason is a correct output;
a confident wrong answer is the worst possible output.

- Enforced by: `VerificationReport` (status is `PASS` only if every claim is `SUPPORTED`), `interface`.

## P4. Law is jurisdiction- and time-bound

Every query carries an explicit `jurisdiction` and `as_of` date. Every source carries its
jurisdiction and validity interval (`effective_from` / `effective_to`). Citing a provision not in
force on `as_of`, or from another jurisdiction without saying so, is a verification failure.

- Enforced by: `contracts` (required fields), `corpus` (versioned ingestion), `verification` (temporal check).

## P5. Provenance for every byte

Each source document records where it came from (`source_uri`), when it was fetched, and a
content hash. Each answer records the model id, prompt version, parameters and retrieved
document versions (`ModelTrace`). Any answer must be reproducible and auditable after the fact.

- Enforced by: `contracts`, `corpus`, `reasoning`.

## P6. Measured, not assumed

No change to prompts, models, retrieval or verification ships without running the evaluation
suite. `evaluation` owns the release gate and its thresholds; other departments cannot lower them.
Hard gates (must be 100%): citation resolvability, exact-quote match. Soft gates are set per use
case in `departments/evaluation/CHARTER.md`.

## P7. Deterministic where possible, bounded where not

Prefer deterministic code over a model call. Where a model is needed, prefer a fixed pipeline
with bounded agent steps over an open-ended autonomous loop. Use structured (schema-validated)
outputs for every model response that feeds downstream code. Temperature 0 unless an ADR says otherwise.

## P8. Human in the loop for consequential output

The system assists legal professionals; it does not replace them. Output states its scope,
jurisdiction, as-of date and confidence, and is never presented as legal advice. Actions with
external effect (filing, sending, signing) are out of scope unless an ADR adds them with human approval steps.

## P9. Confidentiality

User documents and queries may be privileged. They MUST NOT be logged in plaintext outside the
designated trace store, sent to services not approved in an ADR, or used as test fixtures.
