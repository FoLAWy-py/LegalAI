---
id: REQ-PMO-0005
title: Build synthetic outline set, golden-set spec and eval runner
from: pmo
to: evaluation
owner: pmo
status: verified
priority: P1
created: 2026-10-30
updated: 2026-10-30
depends_on: [ADR-0004, ADR-0005]
---

# REQ-PMO-0005: Build synthetic outline set, golden-set spec and eval runner

## 1. Context
Nothing ships unmeasured (P6). The framework spike (REQ-ARCH-0001) needs a synthetic set now; the real golden
sets need qualified human review. Sequencing (project owner, 2026-10-30): CN first, US later.
**Practice area (project owner, 2026-10-30, revises D6):** CN **criminal** cases replace civil contract disputes, with
**financial crimes** as the v1 focus.

PMO check of the owner-supplied pilot `<data_dir>/evaluation/yu-huan-pilot/` (2026-10-30): hashes and offsets are
internally consistent, but document 01 is not verbatim to its official source page, and three documents are secondary
mirrors. The pilot is therefore **not** golden data in its current form.

## 2. Requirement
1. A synthetic `ZZ` dataset of ≥ 10 **criminal** cases, at least 7 of them fictional **financial** offences (e.g. modelled
   on the structure — not the text — of illegal fundraising, fund fraud, money laundering, card fraud): fictional penal and criminal-procedure provisions, fictional
   case files (e.g. indictment, witness statements, forensic and inspection records), the charged offence, expected
   elements of the offence, expected evidence links and expected gaps; at least 3 cases in Chinese, 3 in English,
   2 cross-lingual, 2 with deliberately missing evidence for an element, 1 with a justification or defence supported
   by contradicting evidence, 1 where no offence provision applies (expected abstention). Exposed as fake stores.
2. A golden-set specification for real CN and US outlines: item format, sourcing rules, reviewer qualification,
   review workflow, versioning. Real items are created only by/with a qualified reviewer — never from model output alone.
   The spec MUST require: source text captured byte-faithfully from the official rendering (with URL, retrieval time and
   hash); an authority tier per document (official / secondary), where secondary sources cannot support a SUPPORTED label;
   and a check that every annotation quote occurs verbatim in the captured text. CN spec first; US section may be a stub.
3. An eval runner computing every metric in the evaluation charter's release gate for any `OutlineBuilder` +
   `Verifier` pair, with per-jurisdiction and per-language breakdown, producing a versioned report.

## 3. Interface
Contract types and ports only; pipeline via `legalai_interface` once available.

## 4. Acceptance criteria
1. Synthetic dataset loads and every expected outline passes contract validation.
2. Runner produces a report for a trivial baseline builder (e.g. always abstains) with correct metric values
   verified by hand-computed tests.
3. Golden-set spec is in `departments/evaluation/docs/golden-set-spec.md`.
4. `scripts/check_all.py` passes.

## 5. Out of scope
Producing real golden items (needs the reviewer and D8).

## 6. Open questions
- Who is the qualified reviewer for CN items and for US items? (Project owner.)

## 7. Response
Decision: **accept** (evaluation, 2026-10-30), against the revised §1–§2 of commit `dc7ab2d` (CN criminal practice
area, CN first, the yu-huan pilot is not golden data; the golden-set spec MUST require byte-faithful capture of the
official rendering with URL, retrieval time and hash, an authority tier per document where secondary sources cannot
support a SUPPORTED label, and a verbatim check of every annotation quote; the US section may be a stub).

Plan:
1. Synthetic set `ZZ-SYNTH-CRIM-OUTLINE`: ≥ 10 fictional `ZZ` criminal cases built in memory from a fictional penal
   code and criminal-procedure code (titles marked SYNTHETIC) and fictional case files (indictment, witness
   statements, forensic and inspection records). Mix: ≥ 3 zh, ≥ 3 en, 2 cross-lingual, 2 with missing evidence for an
   element, 1 where a justification is supported by contradicting evidence, 1 where no offence provision is in force
   (expected abstention). Exposed as in-memory `SourceStore`, `CaseFileStore`, `Retriever`, `EvidenceRetriever` fakes
   plus expected `EvidenceOutline`s and a derived adversarial citation set, via `legalai_evaluation.__all__`.
   `party_role` is `DEFENDANT` for every case until architecture adds a prosecution role (REQ-PMO-0007); cases that
   should switch are listed in §8. No enum value is invented.
2. Golden-set spec at `departments/evaluation/docs/golden-set-spec.md`: CN criminal outlines in full (including
   public judgments as proxy case files and how their evidence recital is cited), US as a stub.
3. Runner `run_evaluation(dataset, builder, verifier, ...)` computing every release-gate metric with
   per-jurisdiction and per-language breakdowns and a versioned, dataset-pinned `EvalReport`; tested with trivial
   baselines (always-abstain, oracle, abstaining and rubber-stamp verifiers) against hand-computed values.

Answer to §6: the qualified reviewer is a project-owner decision. The spec records reviewer identity and
qualification per item and leaves the named CN and US reviewers as TBD; no real golden item can be admitted until
they are named.

## 8. Delivery
Delivered by evaluation, 2026-10-30, against §1–§2 as revised up to commit `87ab123` (criminal, ≥ 7 financial
offences), with contracts 0.3.0 (`PartyRole.PROSECUTION`) and ADR-0006.

- **What changed (paths, public API):**
  - `departments/evaluation/src/legalai_evaluation/`: `fakes.py` (in-memory `SourceStore`, `CaseFileStore`,
    `Retriever`, `EvidenceRetriever`); `dataset.py` (`EvalCase`, `EvalDataset` with `fingerprint()`,
    `AdversarialItem`, `CaseTag`); `synthetic/` (fictional ZZ law, 11 cases, adversarial set, loader);
    `metrics.py` (independent citation checks, one-to-one element/link/gap matching, recall@k); `report.py`
    (`EvalReport` schema 1.0.0, breakdowns, release gate, `render_markdown`); `runner.py` (`run_evaluation`);
    `baselines.py`.
  - Public API (`legalai_evaluation.__all__`): `load_synthetic_dataset`, `SyntheticDataset`, `run_evaluation`,
    `EvalReport`, `render_markdown`, `AlwaysAbstainBuilder`, `OracleBuilder`, `AbstainingVerifier`,
    `RubberStampVerifier`, the four `InMemory*` fakes, `check_citation`, and the report and dataset types.
  - Synthetic set `ZZ-SYNTH-CRIM-OUTLINE` v1.0.0: 11 cases, 36 expected elements, 62 links, 3 gaps, 80
    adversarial items (8 kinds × 10 answerable cases: fabricated law document, altered law quote, shifted
    offsets, version not in force, wrong jurisdiction (`ZZ-NP`), fabricated case document, altered evidence
    quote, evidence from another case). Mix: 8 financial offences (card fraud, fraud, embezzlement, illegal
    fundraising, fundraising fraud ×2, money laundering, crypto-asset manipulation), 5 Chinese-only, 4 English-only,
    2 cross-lingual (008 zh→en, 009 en→zh), 2 missing evidence (003 amount, 007 intent of one defendant group),
    1 defence with contradicting evidence (002 self-defence), 1 no applicable provision (010 → abstain).
    Bonus: 011 defective forensic opinion (`insufficient` gap); 006/007 are two defendant groups of one fundraising
    scheme sharing case files, where the intent element is proved for one group only.
  - Party roles (ADR-0006 §2): `PROSECUTION` for 001, 004, 005, 006, 008; `DEFENDANT` for 002, 003, 007, 009,
    010, 011. No DEFENDANT placeholder is left, so no case needs to switch.
  - ADR-0006 compliance: defences are `contradicts` links on the offence element they negate (002 E4
    "unlawfully"); purposes and gap descriptions state facts only; `burden_on` is `None` everywhere (no synthetic
    offence provision states the burden for its own element); one `as_of` per outline (the conduct date; every
    case lies inside one version window, and 010 is the abstention case).
  - `departments/evaluation/docs/golden-set-spec.md`: CN criminal spec in full (byte-faithful capture with URL,
    retrieval time and hashes; `official` / `secondary` tier, where secondary never supports SUPPORTED; automated
    verbatim-quote check; public judgments and guiding cases as proxy case files and how their evidence recital
    is cited; reviewer identity and qualification per item, named reviewers TBD; workflow; versioning). US is a
    stub.
  - `departments/evaluation/pyproject.toml`: ruff `extend` of the root config plus an allow-list of 7 full-width
    punctuation code points used in the Chinese synthetic texts (the same pattern verification uses). No other
    lint rule is relaxed.
  - `departments/evaluation/CHARTER.md`: Interfaces section lists the public API.
- **How to verify (commands):**
  - `uv run python scripts/check_all.py`
  - `uv run pytest -q departments/evaluation` (42 tests)
  - `uv run python -c "from legalai_evaluation import *; d=load_synthetic_dataset(); print(render_markdown(run_evaluation(d, AlwaysAbstainBuilder(), AbstainingVerifier())))"`
- **Evidence (test output, eval scores):**
  - AC1: `tests/test_synthetic_dataset.py` re-validates every expected outline and adversarial outline against the
    contracts, checks the required mix, and checks that all 98 expected citations resolve, match verbatim and are
    in scope, and that each adversarial item has exactly one bad citation.
  - AC2: `tests/test_runner.py`, hand-computed. AlwaysAbstain + AbstainingVerifier: contract-valid 11/11; element
    recall 0/36; link recall 0/62; gap recall 0/3; abstention 1/1; false abstention 10/10; citation gates not
    measured → gate **INCOMPLETE**; per language en 5 cases (0/14 elements), zh 6 cases (0/22). Oracle +
    RubberStamp: all quality metrics 100 %, 80/80 adversarial false PASS → **FAIL**. Oracle + Abstaining →
    **PASS**. A scripted partially wrong builder gives resolvability 7/8, scope 6/8, element precision 2/3,
    link precision 4/5, gap precision 0/2 and abstention 0/1, all as computed by hand. `tests/test_metrics.py`
    checks the matching rules on hand-offset examples.
  - Cross-department smoke test (`tests/test_independent_verifier_smoke.py`): verification's `IndependentVerifier`
    with an evaluation fake model that approves everything: **0/80 adversarial false PASS**, 0 corrupted items
    judged SUPPORTED, and 10/10 expected outlines PASS. With a model outage: no PASS anywhere.
  - AC3: spec at `departments/evaluation/docs/golden-set-spec.md`.
  - AC4: `scripts/check_all.py` → `ALL CHECKS PASSED` (294 passed, 1 deselected).
- **Known limitations:**
  - Under `docs/ORGANIZATION.md` §4 no other package may import `legalai_evaluation`, so reasoning cannot use
    these fakes in its own tests. For REQ-ARCH-0001 AC2, evaluation must run the comparison by importing
    `legalai_reasoning`'s public API (allowed), or architecture must change the rule. PMO decides.
  - REQ-ARCH-0001 AC2 also asks for token cost and for the share of quotes matching a *retrieved* span. The
    runner records per-case latency and `ModelTrace`s, but `ModelTrace` has no token fields, and quotes are
    checked against the stores, not against what the retriever returned. Both need small follow-ups: a contract
    field via REQ to architecture, and a recording retriever wrapper in evaluation.
  - Soft-gate thresholds stay unset ("set after first baseline", charter). No real builder exists yet to set them.
  - The fake retrievers are a lexical baseline. With k = 1000 they return every target (recall 36/36, 62/62); at
    small k, case-file recall is low (22/62 at k = 5). They are fixtures, not a retrieval benchmark.
  - The golden-set loader that enforces spec §8 is not built; it comes with the first real set (REQ-PMO-0008).
  - The yu-huan pilot was read only as a negative example for the spec. It was not loaded, copied or used.
  - Named reviewers (CN, US) remain open (§6).
