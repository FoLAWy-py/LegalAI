"""LegalAI evaluation department. Public API: only names in __all__ may be imported by other departments.

- Synthetic `ZZ` criminal outline set: `load_synthetic_dataset()` returns a `SyntheticDataset` with expected
  `EvidenceOutline`s, an adversarial citation set, and in-memory `SourceStore` / `CaseFileStore` /
  `Retriever` / `EvidenceRetriever` fakes.
- Eval runner: `run_evaluation(dataset, builder, verifier, ...)` returns a versioned `EvalReport` with the
  release-gate verdict; `render_markdown(report)` summarizes it.
- Baselines for calibration: `AlwaysAbstainBuilder`, `OracleBuilder`, `AbstainingVerifier`,
  `RubberStampVerifier`.
"""

from legalai_evaluation.baselines import (
    AbstainingVerifier,
    AlwaysAbstainBuilder,
    OracleBuilder,
    RubberStampVerifier,
)
from legalai_evaluation.dataset import AdversarialItem, AdversarialKind, CaseTag, EvalCase, EvalDataset
from legalai_evaluation.fakes import (
    IndexedSpan,
    InMemoryCaseFileStore,
    InMemoryEvidenceRetriever,
    InMemoryRetriever,
    InMemorySourceStore,
)
from legalai_evaluation.metrics import CitationCheck, check_citation
from legalai_evaluation.report import (
    REPORT_SCHEMA_VERSION,
    RUNNER_VERSION,
    SOFT_THRESHOLDS,
    AdversarialResult,
    AdversarialSummary,
    CaseCounts,
    CaseResult,
    EvalReport,
    GateKind,
    GateResult,
    GateSummary,
    GateVerdict,
    MetricSet,
    OutlineStatus,
    OverallVerdict,
    Ratio,
    render_markdown,
)
from legalai_evaluation.runner import run_evaluation
from legalai_evaluation.synthetic import SYNTHETIC_DATASET_ID, SyntheticDataset, load_synthetic_dataset

__all__: list[str] = [
    "REPORT_SCHEMA_VERSION",
    "RUNNER_VERSION",
    "SOFT_THRESHOLDS",
    "SYNTHETIC_DATASET_ID",
    "AbstainingVerifier",
    "AdversarialItem",
    "AdversarialKind",
    "AdversarialResult",
    "AdversarialSummary",
    "AlwaysAbstainBuilder",
    "CaseCounts",
    "CaseResult",
    "CaseTag",
    "CitationCheck",
    "EvalCase",
    "EvalDataset",
    "EvalReport",
    "GateKind",
    "GateResult",
    "GateSummary",
    "GateVerdict",
    "InMemoryCaseFileStore",
    "InMemoryEvidenceRetriever",
    "InMemoryRetriever",
    "InMemorySourceStore",
    "IndexedSpan",
    "MetricSet",
    "OracleBuilder",
    "OutlineStatus",
    "OverallVerdict",
    "Ratio",
    "RubberStampVerifier",
    "SyntheticDataset",
    "check_citation",
    "load_synthetic_dataset",
    "render_markdown",
    "run_evaluation",
]
