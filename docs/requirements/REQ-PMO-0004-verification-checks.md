---
id: REQ-PMO-0004
title: Verify evidence outlines — deterministic checks first, model checks second
from: pmo
to: verification
owner: pmo
status: verified
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
Decision: **accept** (verification, 2026-10-30). No amendment to §1–§6.

Approach and interpretation (binding on this delivery; flag disagreement to verification):
- **Exactness (CN first).** Span text, quote and any model-returned quote are compared by exact Unicode
  code-point equality / substring (`str ==`, `in`). **No normalization of any kind** (no NFC/NFKC, no
  width folding, no whitespace or punctuation folding, no simplified/traditional mapping). Offsets are
  Unicode code-point offsets (Python `str` indexing), not bytes or UTF-16 units.
- **Text is always re-read** from the store named by the span's `SourceKind`; text carried in the draft is
  only compared against, never trusted.
- **Verdict mapping (Phase A).** Unresolvable doc/version, wrong `SourceKind`, offsets out of range, stored
  text differs, quote not verbatim, blank quote, evidence outside the query's case, element/legal-rule citing
  a non-law `doc_type` (`secondary`, `other`) → `CITATION_INVALID`; law jurisdiction differs from query →
  `WRONG_JURISDICTION` (strict equality); not in force on `as_of` → `NOT_IN_FORCE`; store misbehaviour or any
  internal error → `CHECK_ERROR`.
- **Phase B** runs only on items that pass Phase A, through an injected OpenAI-compatible client; prompts are
  files in `legalai_verification/prompts/`; temperature 0; strict JSON schema; any model or parse error →
  `CHECK_ERROR`. A `supported`/`contradicted` model answer must carry a quote found verbatim in the re-read
  text, else `CHECK_ERROR`.
- Report status: `PASS` only if every item is `SUPPORTED`; abstained outline/draft → `ABSTAIN` with no items;
  otherwise `FAIL`.
- §6: no open questions.

## 8. Delivery
Delivered by verification, 2026-10-30.

- **What changed (paths, public API):** all under `departments/verification/`.
  - Public API (`legalai_verification.__all__`): `IndependentVerifier(source_store=, case_store=, model=)`
    implements the `Verifier` port (`verify_outline`, `verify`); `JsonChatModel` (model port);
    `OpenAICompatibleChatModel(VerificationModelConfig)` (stdlib HTTP, `/chat/completions`, temperature 0,
    `response_format=json_object`, retries on 408/429/5xx/network, HTTPS only, key held as `SecretStr`);
    `ModelCallError`; `VERIFIER_VERSION`.
  - Internals: `_phase_a.py` (deterministic; imports only `legalai_contracts`, no model access), `_phase_b.py`
    (strict reply schema), `verifier.py`, `_prompts.py`, `prompts/*.md` (4 versioned prompt files, `1.0.0`).
  - Tests: `_testkit.py` (in-package `ZZ` fakes `FakeSourceStore` / `FakeCaseFileStore`, a yes-man
    `ApprovingModel`, an `ExplodingModel`, a `ScriptedModel`) and `tests/test_*.py` (220 tests, plus 1 live).
  - `pyproject.toml`: no new dependencies. Adds a `[tool.ruff]` section that extends the root config and allows
    8 exact CJK code points (`，：（）？`, U+3000, `０`, `１`) for RUF001, because they are the CN fixture content.
  - `CHARTER.md` Interfaces section lists the public API.
- **How to verify (commands):**
  - `uv run python scripts/check_all.py`
  - `uv run pytest -q departments/verification -k adversarial -v` (AC1, AC2)
  - `uv run pytest -q departments/verification/tests/test_phase_b_model_checks.py -v` (AC3)
  - `DEEPINFRA_API_KEY=... LLM_BASE_URL=https://api.deepinfra.com/v1/openai LLM_MODEL=... uv run pytest -m live
    departments/verification/tests/test_live_smoke.py -s` (AC4)
- **Evidence:**
  - AC1: `test_adversarial_citations.py` has 41 cases, each run with a yes-man model that approves anything
    reaching it. The result is **0 false SUPPORTED** (`test_zero_false_supported_over_whole_adversarial_set`).
    Each case is also pinned to the check that must catch it (`test_each_case_fails_at_the_intended_check`).
    - Cases: fabricated doc id or version; altered quote or span (with and without the contract validators);
      offsets shifted ±1, beyond the document end, or counted in UTF-16 after a non-BMP character; outdated
      version; old-version quote cited against the current version; future version; a version expiring
      exactly on `as_of`; wrong jurisdiction (`ZZ-B`); secondary source cited as law; case file cited as legal
      basis; law cited as evidence; blank quote; one bad citation among good ones.
    - Evidence cases: a document from another case (its text is never read), fabricated document or version,
      altered fact, full-width digits changed to ASCII, curly quotes dropped, shifted offsets.
    - CN exactness: half-width comma or full stop; ASCII quotes or `「」` for `“”`; ASCII space for U+3000;
      Kangxi radical U+2F00 (NFKC-equal); compatibility ideograph U+F90A (NFC-equal); traditional for
      simplified; inserted U+200B; BOM prefix; NBSP (English).
  - AC2: every adversarial case is re-run with `ExplodingModel`, and every run records `calls == []`. In a mixed
    outline, only the 4 good items reach the model. `_phase_a.py` imports nothing but `legalai_contracts` and
    stdlib (AST test).
  - AC3: 25 malformed or ungrounded replies all give `CHECK_ERROR`:
    - not JSON; markdown fences; prose around the JSON; an array or a bare string;
    - missing or extra keys; a verdict that is capitalised, unknown, boolean or null; duplicate keys;
    - `supported` with an empty, blank, invented or normalization-variant `basis_quote`.
    Model exceptions (`ModelCallError`, `RuntimeError`, `TimeoutError`, `ValueError`) and non-string replies
    also give `CHECK_ERROR`.
  - AC4: `test_live_smoke.py` is marked `@pytest.mark.live`. **It has not been run**: no API key was available
    in the delivery environment. It skips cleanly without credentials:
    `SKIPPED [1] ... live model not configured (DEEPINFRA_API_KEY, LLM_BASE_URL, LLM_MODEL)`.
  - AC5: `uv run python scripts/check_all.py` reports `ALL CHECKS PASSED` (246 passed, 1 deselected).
  - Not done: the evaluation suite (code standard §4), because evaluation's runner (REQ-PMO-0005) is not delivered.
- **Known limitations:**
  1. The `SourceStore` / `CaseFileStore` ports do not define a "not found" error. Verification maps `LookupError`
     (including `KeyError`) to `CITATION_INVALID` and any other exception to `CHECK_ERROR`, so neither is
     ever SUPPORTED. Architecture may want to standardise a not-found exception.
  2. The jurisdiction check is strict equality. A `US-XX` query citing federal `US` law is `WRONG_JURISDICTION`
     until an ADR defines which jurisdictions apply to which.
  3. `content_sha256` is not checked: the contract does not say whether it hashes the text or the original bytes.
  4. `burden_on` fails only on an explicit contrary statement in the cited law. A law that says nothing about
     the burden does not fail the element.
  5. A link is judged on its own merits. If its element fails, the report is FAIL anyway, but the link item may
     still be SUPPORTED.
  6. Item rationales may contain store exception messages (truncated to 300 characters). Case-file text
     mismatches are reported by position only, never by the characters themselves.
  7. Prompt injection inside case text is mitigated, not eliminated:
     - inputs are sent as data-only JSON;
     - a `supported` or `contradicted` reply must quote the re-read text verbatim.
  8. The model id and prompt version are recorded in `ItemVerification.method`
     (`phase_b:<prompt_id>@<version>:model=<id>`). `VerificationReport` has no `ModelTrace` field (P5);
     adding one is a contract change for architecture.
  9. Law cited in `FACT` claims is also checked as in force on `as_of`. A fact about a repealed version is
     therefore NOT_IN_FORCE. This fails closed.
