"""Eval runner: drives any `OutlineBuilder` + `Verifier` pair over a pinned dataset into an `EvalReport`."""

import time
from datetime import UTC, datetime

from pydantic import ValidationError

from legalai_contracts import (
    CONTRACT_VERSION,
    EvidenceOutline,
    EvidenceRetriever,
    LegalQuery,
    OutlineBuilder,
    ReportStatus,
    Retriever,
    Verdict,
    VerificationReport,
    Verifier,
)
from legalai_evaluation.dataset import AdversarialItem, EvalCase, EvalDataset
from legalai_evaluation.metrics import (
    check_citation,
    evidence_targets,
    law_targets,
    outline_citations,
    recall_hits,
    score_outline,
)
from legalai_evaluation.report import (
    AdversarialResult,
    CaseCounts,
    CaseResult,
    EvalReport,
    OutlineStatus,
    aggregate,
    breakdown,
    evaluate_gate,
    summarize_adversarial,
)


def _describe(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}"


def _revalidate_outline(produced: object, query: LegalQuery) -> tuple[EvidenceOutline | None, str | None]:
    """Re-run contract validation (catches `model_construct` bypasses) and check the query was echoed."""
    if not isinstance(produced, EvidenceOutline):
        return None, f"builder returned {type(produced).__name__}, not EvidenceOutline"
    try:
        outline = EvidenceOutline.model_validate(produced.model_dump())
    except ValidationError as exc:
        return None, _describe(exc)
    if outline.query != query:
        return None, "outline.query differs from the query that was asked"
    return outline, None


def _revalidate_report(produced: object, query_id: str) -> tuple[VerificationReport | None, str | None]:
    if not isinstance(produced, VerificationReport):
        return None, f"verifier returned {type(produced).__name__}, not VerificationReport"
    try:
        report = VerificationReport.model_validate(produced.model_dump())
    except ValidationError as exc:
        return None, _describe(exc)
    if report.query_id != query_id:
        return None, "verification report query_id differs from the outline's query"
    return report, None


def _verify(
    verifier: Verifier, outline: EvidenceOutline, fail_fast: bool
) -> tuple[VerificationReport | None, str | None]:
    try:
        produced = verifier.verify_outline(outline)
    except Exception as exc:
        if fail_fast:
            raise
        return None, _describe(exc)
    return _revalidate_report(produced, outline.query.query_id)


def _run_case(
    dataset: EvalDataset,
    case: EvalCase,
    builder: OutlineBuilder,
    verifier: Verifier,
    retriever: Retriever | None,
    evidence_retriever: EvidenceRetriever | None,
    retrieval_k: int,
    fail_fast: bool,
) -> CaseResult:
    started = time.perf_counter()
    error: str | None = None
    outline: EvidenceOutline | None = None
    try:
        produced: object = builder.build_outline(case.query)
    except Exception as exc:
        if fail_fast:
            raise
        status = OutlineStatus.ERROR
        error = _describe(exc)
    else:
        outline, error = _revalidate_outline(produced, case.query)
        if outline is None:
            status = OutlineStatus.INVALID
        else:
            status = OutlineStatus.ABSTAINED if outline.abstained else OutlineStatus.OUTLINE
    latency_ms = (time.perf_counter() - started) * 1000

    checks = [
        check_citation(c, case.query, dataset.source_store, dataset.case_file_store)
        for c in (outline_citations(outline) if outline is not None else [])
    ]
    score = score_outline(case.expected, outline)

    verification_status: ReportStatus | None = None
    verification_error: str | None = None
    if outline is not None and not outline.abstained:
        report, verification_error = _verify(verifier, outline, fail_fast)
        verification_status = report.status if report is not None else None
    any_bad = any(not (c.resolvable and c.quote_matches and c.in_scope) for c in checks)

    law_t = law_h = ev_t = ev_h = 0
    if retriever is not None and evidence_retriever is not None:
        law_t, law_h = recall_hits(law_targets(case.expected), retriever.retrieve(case.query, retrieval_k))
        if not case.expected.abstained and case.query.case_id is not None:
            for element in case.expected.elements:
                spans = evidence_retriever.search_case(case.query.case_id, element.description, retrieval_k)
                t, h = recall_hits(evidence_targets(case.expected, element.element_id), spans)
                ev_t += t
                ev_h += h

    counts = CaseCounts(
        citations=len(checks),
        citations_resolvable=sum(c.resolvable for c in checks),
        quotes_matched=sum(c.quote_matches for c in checks),
        citations_in_scope=sum(c.in_scope for c in checks),
        expected_elements=score.expected_elements,
        produced_elements=score.produced_elements,
        matched_elements=score.matched_elements,
        expected_links=score.expected_links,
        produced_links=score.produced_links,
        matched_links=score.matched_links,
        expected_gaps=score.expected_gaps,
        produced_gaps=score.produced_gaps,
        matched_gaps=score.matched_gaps,
        gap_kind_agreements=score.gap_kind_agreements,
        law_targets=law_t,
        law_hits=law_h,
        evidence_targets=ev_t,
        evidence_hits=ev_h,
    )
    return CaseResult(
        case_id=case.case_id,
        query_id=case.query.query_id,
        jurisdiction=case.query.jurisdiction,
        query_language=case.query_language,
        tags=case.tags,
        expects_abstention=case.expects_abstention,
        status=status,
        error=error,
        counts=counts,
        verification_status=verification_status,
        verification_error=verification_error,
        verifier_false_pass=verification_status is ReportStatus.PASS and any_bad,
        latency_ms=latency_ms,
        traces=outline.traces if outline is not None else (),
    )


def _run_adversarial(item: AdversarialItem, verifier: Verifier, fail_fast: bool) -> AdversarialResult:
    report, error = _verify(verifier, item.outline, fail_fast)
    target: Verdict | None = None
    if report is not None:
        target = next((i.verdict for i in report.items if i.item_id == item.target_item_id), None)
    return AdversarialResult(
        item_id=item.item_id,
        kind=item.kind,
        base_case_id=item.base_case_id,
        target_item_id=item.target_item_id,
        status=report.status if report is not None else None,
        target_verdict=target,
        error=error,
    )


def run_evaluation(
    dataset: EvalDataset,
    builder: OutlineBuilder,
    verifier: Verifier,
    *,
    builder_name: str | None = None,
    verifier_name: str | None = None,
    retriever: Retriever | None = None,
    evidence_retriever: EvidenceRetriever | None = None,
    retrieval_k: int = 10,
    created_at: datetime | None = None,
    fail_fast: bool = False,
) -> EvalReport:
    """Evaluate `builder` + `verifier` on every case and adversarial item of `dataset`.

    Guarantees:
    - Every release-gate metric of the evaluation charter is computed, overall and per jurisdiction and per
      query language; the gate verdict is FAIL if any metric fails, INCOMPLETE if a hard metric could not be
      measured, PASS otherwise.
    - Citation metrics come from evaluation's own store checks, independent of the verifier.
    - A builder or verifier exception is recorded in the report and counted against the system (never as a
      PASS); with `fail_fast=True` it propagates instead.
    - Retrieval recall@k is measured only when both `retriever` and `evidence_retriever` are given;
      otherwise it is reported as not measured.
    - The report pins `dataset_id`, `version` and `fingerprint()`; apart from `created_at` and latencies, the
      same inputs give the same report.
    """
    if retrieval_k <= 0:
        raise ValueError("retrieval_k must be positive")
    measured = retriever is not None and evidence_retriever is not None
    if (retriever is None) != (evidence_retriever is None):
        raise ValueError("pass both retriever and evidence_retriever, or neither")
    results = tuple(
        _run_case(dataset, case, builder, verifier, retriever, evidence_retriever, retrieval_k, fail_fast)
        for case in dataset.cases
    )
    adversarial_results = tuple(_run_adversarial(item, verifier, fail_fast) for item in dataset.adversarial)
    overall = aggregate(results, measured)
    adversarial = summarize_adversarial(adversarial_results)
    return EvalReport(
        contract_version=CONTRACT_VERSION,
        dataset_id=dataset.dataset_id,
        dataset_version=dataset.version,
        dataset_fingerprint=dataset.fingerprint(),
        builder_name=builder_name or type(builder).__name__,
        verifier_name=verifier_name or type(verifier).__name__,
        created_at=created_at or datetime.now(UTC),
        retrieval_k=retrieval_k if measured else None,
        overall=overall,
        by_jurisdiction=breakdown(results, lambda r: r.jurisdiction, measured),
        by_language=breakdown(results, lambda r: r.query_language, measured),
        adversarial=adversarial,
        gate=evaluate_gate(overall, adversarial),
        cases=results,
        adversarial_results=adversarial_results,
    )
