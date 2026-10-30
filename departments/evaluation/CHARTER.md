---
id: CHARTER-EVALUATION
owner: evaluation
status: active
updated: 2026-10-30
---

# Evaluation Charter

## Mission
Measure how right the system is and block releases that make it worse.

## Owns
- Golden datasets per use case and jurisdiction (with expected sources, expected answers, and
  unanswerable questions), adversarial sets (fabricated citations, outdated law, cross-jurisdiction traps).
- Metrics, the regression suite, eval reports, and the **release gate** with its thresholds.
- Labelling guidelines for human reviewers.

## Does not own
Fixing failures (the responsible department, via REQ). Changing contracts (architecture).

## Interfaces
- **Consumes:** public APIs of all departments and the `interface` pipeline factory.
- **Provides:** eval runner, reports, and gate verdicts referenced in REQ §8 deliveries. Public API
  (`legalai_evaluation.__all__`): `run_evaluation(dataset, builder, verifier, ...)` → `EvalReport` (versioned,
  dataset-pinned, with gate verdict) and `render_markdown`; `load_synthetic_dataset()` → `SyntheticDataset`
  (synthetic `ZZ` criminal outlines, adversarial citation set, in-memory `SourceStore` / `CaseFileStore` /
  `Retriever` / `EvidenceRetriever` fakes); calibration baselines `AlwaysAbstainBuilder`, `OracleBuilder`,
  `AbstainingVerifier`, `RubberStampVerifier`. Golden-set format: `docs/golden-set-spec.md`.

## Release gate
| Metric | Threshold | Type |
|---|---|---|
| Citation resolvability (span exists, text matches) | 100% | hard |
| Exact-quote match | 100% | hard |
| False PASS on adversarial citation set | 0 | hard |
| Element recall / precision vs. golden outline | _set after first baseline_ | soft |
| Evidence-link precision (link truly supports element) | _set after first baseline_ | soft |
| Gap correctness (declared gaps are real gaps; real gaps are declared) | _set after first baseline_ | soft |
| Law retrieval recall@k, case-file retrieval recall@k | _set after first baseline_ | soft |
| All metrics reported per jurisdiction (CN, US) and per query language | — | reporting rule |

## Quality bars
- Golden data is reviewed by a qualified person before use; each item records its reviewer and source.
- Eval runs are reproducible (pinned dataset version, recorded traces).

## Reliability duties
P6 (owner). Thresholds can only be lowered by an accepted ADR. Golden data never comes from model output
without human review.
