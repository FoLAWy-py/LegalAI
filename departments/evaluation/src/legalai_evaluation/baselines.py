"""Trivial reference implementations for calibrating the eval runner. Never wire these into a pipeline."""

from legalai_contracts import (
    DraftAnswer,
    EvidenceOutline,
    ItemVerification,
    LegalQuery,
    ModelTrace,
    ReportStatus,
    Verdict,
    VerificationReport,
)
from legalai_evaluation.dataset import EvalDataset


class AlwaysAbstainBuilder:
    """`OutlineBuilder` that abstains on every query. Lower bound: never wrong, never useful."""

    def build_outline(self, query: LegalQuery) -> EvidenceOutline:
        return EvidenceOutline(
            query=query,
            cause_of_action="",
            abstained=True,
            abstain_reason="baseline: always abstains",
            traces=(
                ModelTrace(
                    model="baseline:always-abstain", prompt_id="none", prompt_version="0", temperature=0
                ),
            ),
        )


class OracleBuilder:
    """`OutlineBuilder` that returns the dataset's expected outline. Upper bound.

    Raises KeyError for a query that is not in the dataset.
    """

    def __init__(self, dataset: EvalDataset) -> None:
        self._expected = {c.query.query_id: c.expected for c in dataset.cases}

    def build_outline(self, query: LegalQuery) -> EvidenceOutline:
        return self._expected[query.query_id]


class AbstainingVerifier:
    """`Verifier` that never judges anything: always ABSTAIN with no items. Can never produce a false PASS."""

    version = "baseline:abstaining-0.1"

    def verify(self, draft: DraftAnswer) -> VerificationReport:
        return VerificationReport(
            query_id=draft.query.query_id, status=ReportStatus.ABSTAIN, verifier_version=self.version
        )

    def verify_outline(self, outline: EvidenceOutline) -> VerificationReport:
        return VerificationReport(
            query_id=outline.query.query_id, status=ReportStatus.ABSTAIN, verifier_version=self.version
        )


class RubberStampVerifier:
    """`Verifier` that marks every item SUPPORTED without checking. Exists to prove the gate catches it.

    PASS whenever there is at least one item; ABSTAIN otherwise (PASS needs items).
    """

    version = "baseline:rubber-stamp-0.1"

    def _report(self, query_id: str, item_ids: list[str]) -> VerificationReport:
        items = tuple(
            ItemVerification(
                item_id=i, verdict=Verdict.SUPPORTED, method="baseline:rubber-stamp", rationale="unchecked"
            )
            for i in item_ids
        )
        status = ReportStatus.PASS if items else ReportStatus.ABSTAIN
        return VerificationReport(
            query_id=query_id, status=status, items=items, verifier_version=self.version
        )

    def verify(self, draft: DraftAnswer) -> VerificationReport:
        return self._report(draft.query.query_id, [c.claim_id for c in draft.claims])

    def verify_outline(self, outline: EvidenceOutline) -> VerificationReport:
        ids = [e.element_id for e in outline.elements] + [link.link_id for link in outline.links]
        return self._report(outline.query.query_id, ids)
