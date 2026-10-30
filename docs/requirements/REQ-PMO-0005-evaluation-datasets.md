---
id: REQ-PMO-0005
title: Build synthetic outline set, golden-set spec and eval runner
from: pmo
to: evaluation
owner: pmo
status: open
priority: P1
created: 2026-10-30
updated: 2026-10-30
depends_on: [ADR-0004, ADR-0005]
---

# REQ-PMO-0005: Build synthetic outline set, golden-set spec and eval runner

## 1. Context
Nothing ships unmeasured (P6). The framework spike (REQ-ARCH-0001) needs a synthetic set now; the real golden
sets need qualified human review. Sequencing (project owner, 2026-10-30): CN first, US later.
**Practice area (project owner, 2026-10-30, revises D6):** CN **criminal** cases replace civil contract disputes.

PMO check of the owner-supplied pilot `<data_dir>/evaluation/yu-huan-pilot/` (2026-10-30): hashes and offsets are
internally consistent, but document 01 is not verbatim to its official source page, and three documents are secondary
mirrors. The pilot is therefore **not** golden data in its current form.

## 2. Requirement
1. A synthetic `ZZ` dataset of ≥ 10 **criminal** cases: fictional penal and criminal-procedure provisions, fictional
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
_Pending (evaluation)._

## 8. Delivery
_Pending (evaluation)._
