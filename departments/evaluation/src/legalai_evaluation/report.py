"""Versioned evaluation report: per-case results, aggregated metrics, breakdowns and the release gate."""

from collections.abc import Callable, Sequence
from datetime import datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from legalai_contracts import ModelTrace, ReportStatus, Verdict
from legalai_evaluation.dataset import AdversarialKind, CaseTag

REPORT_SCHEMA_VERSION = "1.0.0"
RUNNER_VERSION = "0.1.0"


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Ratio(_Frozen):
    """numerator / denominator; `value` is None when nothing was measured (denominator 0).

    `value` is derived when omitted and rejected when inconsistent, so reports round-trip through JSON.
    """

    numerator: int = Field(ge=0)
    denominator: int = Field(ge=0)
    value: float | None = None

    @model_validator(mode="before")
    @classmethod
    def _derive_value(cls, data: object) -> object:
        if isinstance(data, dict) and "value" not in data:
            n, d = data.get("numerator"), data.get("denominator")
            if isinstance(n, int) and isinstance(d, int):
                return {**data, "value": None if d == 0 else n / d}
        return data

    @model_validator(mode="after")
    def _consistent(self) -> "Ratio":
        if self.numerator > self.denominator:
            raise ValueError("numerator exceeds denominator")
        expected = None if self.denominator == 0 else self.numerator / self.denominator
        if self.value != expected:
            raise ValueError("value is inconsistent with numerator / denominator")
        return self


class OutlineStatus(StrEnum):
    OUTLINE = "outline"
    ABSTAINED = "abstained"
    INVALID = "invalid"
    ERROR = "error"


class CaseCounts(_Frozen):
    """Raw counts for one case. Every metric is a ratio of sums of these, so breakdowns aggregate exactly."""

    citations: int = 0
    citations_resolvable: int = 0
    quotes_matched: int = 0
    citations_in_scope: int = 0
    expected_elements: int = 0
    produced_elements: int = 0
    matched_elements: int = 0
    expected_links: int = 0
    produced_links: int = 0
    matched_links: int = 0
    expected_gaps: int = 0
    produced_gaps: int = 0
    matched_gaps: int = 0
    gap_kind_agreements: int = 0
    law_targets: int = 0
    law_hits: int = 0
    evidence_targets: int = 0
    evidence_hits: int = 0


class CaseResult(_Frozen):
    case_id: str
    query_id: str
    jurisdiction: str
    query_language: str
    tags: tuple[CaseTag, ...]
    expects_abstention: bool
    status: OutlineStatus
    error: str | None = None
    counts: CaseCounts
    verification_status: ReportStatus | None = None
    verification_error: str | None = None
    verifier_false_pass: bool = Field(
        default=False,
        description="Verifier said PASS although evaluation found a bad or out-of-scope citation.",
    )
    latency_ms: float = Field(
        ge=0, description="Builder wall-clock time; not reproducible, excluded from gates."
    )
    traces: tuple[ModelTrace, ...] = ()


class MetricSet(_Frozen):
    """All release-gate metrics plus diagnostics, for one slice of cases."""

    cases: int
    contract_valid: Ratio
    builder_errors: int
    citation_resolvability: Ratio
    exact_quote_match: Ratio
    citation_scope: Ratio
    element_recall: Ratio
    element_precision: Ratio
    evidence_link_precision: Ratio
    evidence_link_recall: Ratio
    gap_precision: Ratio
    gap_recall: Ratio
    gap_kind_agreement: Ratio
    abstention_recall: Ratio = Field(description="Expected-abstention cases on which the builder abstained.")
    false_abstention: Ratio = Field(description="Answerable cases on which the builder abstained.")
    verifier_pass: Ratio = Field(description="Verified outlines that the verifier PASSed (informational).")
    verifier_false_pass: int
    law_recall_at_k: Ratio | None = None
    case_recall_at_k: Ratio | None = None


class AdversarialResult(_Frozen):
    item_id: str
    kind: AdversarialKind
    base_case_id: str
    target_item_id: str
    status: ReportStatus | None
    target_verdict: Verdict | None
    error: str | None = None
    false_pass: bool = Field(default=False, description="True exactly when the verifier said PASS.")

    @model_validator(mode="before")
    @classmethod
    def _derive_false_pass(cls, data: object) -> object:
        if isinstance(data, dict) and "false_pass" not in data:
            return {**data, "false_pass": data.get("status") in (ReportStatus.PASS, ReportStatus.PASS.value)}
        return data

    @model_validator(mode="after")
    def _consistent(self) -> "AdversarialResult":
        if self.false_pass != (self.status is ReportStatus.PASS):
            raise ValueError("false_pass must equal (status == PASS)")
        return self


class AdversarialSummary(_Frozen):
    items: int
    false_pass: int
    verifier_errors: int
    target_false_supported: int = Field(description="Corrupted items the verifier judged SUPPORTED.")
    false_pass_by_kind: dict[str, Ratio]


class GateKind(StrEnum):
    HARD = "hard"
    SOFT = "soft"


class GateVerdict(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    NOT_MEASURED = "not_measured"
    NO_THRESHOLD = "no_threshold"


class OverallVerdict(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    INCOMPLETE = "incomplete"


class GateResult(_Frozen):
    metric: str
    kind: GateKind
    threshold: str | None
    observed: float | None
    verdict: GateVerdict


class GateSummary(_Frozen):
    verdict: OverallVerdict
    results: tuple[GateResult, ...]


class EvalReport(_Frozen):
    """One evaluation run, pinned to a dataset version and fingerprint, reproducible from its inputs."""

    report_schema_version: str = REPORT_SCHEMA_VERSION
    runner_version: str = RUNNER_VERSION
    contract_version: str
    dataset_id: str
    dataset_version: str
    dataset_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    builder_name: str
    verifier_name: str
    created_at: datetime
    retrieval_k: int | None
    overall: MetricSet
    by_jurisdiction: dict[str, MetricSet]
    by_language: dict[str, MetricSet]
    adversarial: AdversarialSummary
    gate: GateSummary
    cases: tuple[CaseResult, ...]
    adversarial_results: tuple[AdversarialResult, ...]

    def to_json(self) -> str:
        return self.model_dump_json(indent=2)

    def write_json(self, path: Path) -> Path:
        """Write the report as UTF-8 JSON to `path` (parent directories created). Returns `path`."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json(), encoding="utf-8")
        return path


# --- aggregation ---------------------------------------------------------------------------------------


def aggregate(results: Sequence[CaseResult], retrieval_measured: bool) -> MetricSet:
    def total(field: Callable[[CaseCounts], int]) -> int:
        return sum(field(r.counts) for r in results)

    def ratio(num: Callable[[CaseCounts], int], den: Callable[[CaseCounts], int]) -> Ratio:
        return Ratio(numerator=total(num), denominator=total(den))

    valid = [r for r in results if r.status in (OutlineStatus.OUTLINE, OutlineStatus.ABSTAINED)]
    expect_abstain = [r for r in results if r.expects_abstention]
    answerable = [r for r in results if not r.expects_abstention]
    verified = [r for r in results if r.verification_status is not None]
    return MetricSet(
        cases=len(results),
        contract_valid=Ratio(numerator=len(valid), denominator=len(results)),
        builder_errors=sum(1 for r in results if r.status is OutlineStatus.ERROR),
        citation_resolvability=ratio(lambda c: c.citations_resolvable, lambda c: c.citations),
        exact_quote_match=ratio(lambda c: c.quotes_matched, lambda c: c.citations),
        citation_scope=ratio(lambda c: c.citations_in_scope, lambda c: c.citations),
        element_recall=ratio(lambda c: c.matched_elements, lambda c: c.expected_elements),
        element_precision=ratio(lambda c: c.matched_elements, lambda c: c.produced_elements),
        evidence_link_precision=ratio(lambda c: c.matched_links, lambda c: c.produced_links),
        evidence_link_recall=ratio(lambda c: c.matched_links, lambda c: c.expected_links),
        gap_precision=ratio(lambda c: c.matched_gaps, lambda c: c.produced_gaps),
        gap_recall=ratio(lambda c: c.matched_gaps, lambda c: c.expected_gaps),
        gap_kind_agreement=ratio(lambda c: c.gap_kind_agreements, lambda c: c.matched_gaps),
        abstention_recall=Ratio(
            numerator=sum(1 for r in expect_abstain if r.status is OutlineStatus.ABSTAINED),
            denominator=len(expect_abstain),
        ),
        false_abstention=Ratio(
            numerator=sum(1 for r in answerable if r.status is OutlineStatus.ABSTAINED),
            denominator=len(answerable),
        ),
        verifier_pass=Ratio(
            numerator=sum(1 for r in verified if r.verification_status is ReportStatus.PASS),
            denominator=len(verified),
        ),
        verifier_false_pass=sum(1 for r in results if r.verifier_false_pass),
        law_recall_at_k=ratio(lambda c: c.law_hits, lambda c: c.law_targets) if retrieval_measured else None,
        case_recall_at_k=(
            ratio(lambda c: c.evidence_hits, lambda c: c.evidence_targets) if retrieval_measured else None
        ),
    )


def breakdown(
    results: Sequence[CaseResult], key: Callable[[CaseResult], str], retrieval_measured: bool
) -> dict[str, MetricSet]:
    groups: dict[str, list[CaseResult]] = {}
    for r in results:
        groups.setdefault(key(r), []).append(r)
    return {k: aggregate(v, retrieval_measured) for k, v in sorted(groups.items())}


def summarize_adversarial(results: Sequence[AdversarialResult]) -> AdversarialSummary:
    by_kind: dict[str, Ratio] = {}
    for kind in AdversarialKind:
        of_kind = [r for r in results if r.kind is kind]
        if of_kind:
            by_kind[kind.value] = Ratio(
                numerator=sum(r.false_pass for r in of_kind), denominator=len(of_kind)
            )
    return AdversarialSummary(
        items=len(results),
        false_pass=sum(r.false_pass for r in results),
        verifier_errors=sum(1 for r in results if r.error is not None),
        target_false_supported=sum(1 for r in results if r.target_verdict is Verdict.SUPPORTED),
        false_pass_by_kind=by_kind,
    )


# --- release gate (departments/evaluation/CHARTER.md) ----------------------------------------------------

SOFT_THRESHOLDS: dict[str, float | None] = {
    "element_recall": None,
    "element_precision": None,
    "evidence_link_precision": None,
    "gap_precision": None,
    "gap_recall": None,
    "law_recall_at_k": None,
    "case_recall_at_k": None,
}
"""Charter: soft thresholds are 'set after first baseline'. None = not yet set; reported, never blocking."""


def _hard_ratio(name: str, ratio: Ratio) -> GateResult:
    value = ratio.value
    if value is None:
        verdict = GateVerdict.NOT_MEASURED
    else:
        verdict = GateVerdict.PASS if ratio.numerator == ratio.denominator else GateVerdict.FAIL
    return GateResult(metric=name, kind=GateKind.HARD, threshold="100%", observed=value, verdict=verdict)


def evaluate_gate(overall: MetricSet, adversarial: AdversarialSummary) -> GateSummary:
    results = [
        _hard_ratio("citation_resolvability", overall.citation_resolvability),
        _hard_ratio("exact_quote_match", overall.exact_quote_match),
    ]
    if adversarial.items == 0:
        adv_verdict = GateVerdict.NOT_MEASURED
    else:
        adv_verdict = GateVerdict.PASS if adversarial.false_pass == 0 else GateVerdict.FAIL
    results.append(
        GateResult(
            metric="adversarial_false_pass",
            kind=GateKind.HARD,
            threshold="0",
            observed=float(adversarial.false_pass) if adversarial.items else None,
            verdict=adv_verdict,
        )
    )
    for name, threshold in SOFT_THRESHOLDS.items():
        ratio = getattr(overall, name)
        value = None if ratio is None else ratio.value
        if value is None:
            verdict = GateVerdict.NOT_MEASURED
        elif threshold is None:
            verdict = GateVerdict.NO_THRESHOLD
        else:
            verdict = GateVerdict.PASS if value >= threshold else GateVerdict.FAIL
        results.append(
            GateResult(
                metric=name,
                kind=GateKind.SOFT,
                threshold=None if threshold is None else f">= {threshold:.2%}",
                observed=value,
                verdict=verdict,
            )
        )
    if any(r.verdict is GateVerdict.FAIL for r in results):
        overall_verdict = OverallVerdict.FAIL
    elif any(r.kind is GateKind.HARD and r.verdict is not GateVerdict.PASS for r in results):
        overall_verdict = OverallVerdict.INCOMPLETE
    else:
        overall_verdict = OverallVerdict.PASS
    return GateSummary(verdict=overall_verdict, results=tuple(results))


# --- rendering -----------------------------------------------------------------------------------------


def _fmt(ratio: Ratio | None) -> str:
    if ratio is None:
        return "not measured"
    if ratio.value is None:
        return "n/a (0/0)"
    return f"{ratio.value:.1%} ({ratio.numerator}/{ratio.denominator})"


_ROWS: tuple[tuple[str, Callable[[MetricSet], Ratio | None]], ...] = (
    ("contract-valid output", lambda m: m.contract_valid),
    ("citation resolvability (hard)", lambda m: m.citation_resolvability),
    ("exact-quote match (hard)", lambda m: m.exact_quote_match),
    ("citation scope (jurisdiction, in force, case)", lambda m: m.citation_scope),
    ("element recall", lambda m: m.element_recall),
    ("element precision", lambda m: m.element_precision),
    ("evidence-link precision", lambda m: m.evidence_link_precision),
    ("evidence-link recall", lambda m: m.evidence_link_recall),
    ("gap precision", lambda m: m.gap_precision),
    ("gap recall", lambda m: m.gap_recall),
    ("gap kind agreement", lambda m: m.gap_kind_agreement),
    ("abstention on no-applicable-law cases", lambda m: m.abstention_recall),
    ("false abstention", lambda m: m.false_abstention),
    ("verifier PASS rate", lambda m: m.verifier_pass),
    ("law retrieval recall@k", lambda m: m.law_recall_at_k),
    ("case-file retrieval recall@k", lambda m: m.case_recall_at_k),
)


def _metric_table(columns: dict[str, MetricSet]) -> list[str]:
    names = list(columns)
    lines = ["| Metric | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
    for label, get in _ROWS:
        lines.append(f"| {label} | " + " | ".join(_fmt(get(columns[n])) for n in names) + " |")
    lines.append(
        "| verifier false PASS (main set) | "
        + " | ".join(str(columns[n].verifier_false_pass) for n in names)
        + " |"
    )
    lines.append("| builder errors | " + " | ".join(str(columns[n].builder_errors) for n in names) + " |")
    return lines


def render_markdown(report: EvalReport) -> str:
    """Human-readable summary of a report (for REQ §8 evidence). The JSON report remains authoritative."""
    lines = [
        f"# Eval report: {report.builder_name} + {report.verifier_name}",
        "",
        f"- Dataset: `{report.dataset_id}` v{report.dataset_version}, "
        f"fingerprint `{report.dataset_fingerprint}`",
        f"- Runner {report.runner_version}, report schema {report.report_schema_version}, "
        f"contracts {report.contract_version}",
        f"- Created: {report.created_at.isoformat()}; retrieval k: {report.retrieval_k}",
        f"- **Release gate: {report.gate.verdict.value.upper()}**",
        "",
        "## Gate",
        "| Metric | Type | Threshold | Observed | Verdict |",
        "|---|---|---|---|---|",
    ]
    for g in report.gate.results:
        observed = "-" if g.observed is None else f"{g.observed:.4g}"
        lines.append(
            f"| {g.metric} | {g.kind.value} | {g.threshold or 'unset'} | {observed} | {g.verdict.value} |"
        )
    lines += ["", "## Metrics", *_metric_table({"overall": report.overall})]
    lines += ["", "## By jurisdiction", *_metric_table(report.by_jurisdiction)]
    lines += ["", "## By query language", *_metric_table(report.by_language)]
    adv = report.adversarial
    lines += [
        "",
        "## Adversarial citation set",
        f"- Items: {adv.items}; false PASS: {adv.false_pass}; verifier errors: {adv.verifier_errors}; "
        f"corrupted item judged SUPPORTED: {adv.target_false_supported}",
        "",
        "| Kind | False PASS |",
        "|---|---|",
        *[f"| {kind} | {_fmt(r)} |" for kind, r in adv.false_pass_by_kind.items()],
        "",
        "## Cases",
        "| Case | Lang | Status | Verification | Elements matched | Links matched | Gaps matched |",
        "|---|---|---|---|---|---|---|",
    ]
    for c in report.cases:
        k = c.counts
        verification = c.verification_status.value if c.verification_status else "-"
        lines.append(
            f"| {c.case_id} | {c.query_language} | {c.status.value} | {verification} | "
            f"{k.matched_elements}/{k.expected_elements} | {k.matched_links}/{k.expected_links} | "
            f"{k.matched_gaps}/{k.expected_gaps} |"
        )
    return "\n".join(lines) + "\n"
