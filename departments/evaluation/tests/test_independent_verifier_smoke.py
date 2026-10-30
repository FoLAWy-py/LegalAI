"""Smoke test: the runner against verification's `IndependentVerifier` (public API) on the synthetic set.

The model clients below are evaluation's own fakes; no network is used. With a model that approves everything,
only verification's deterministic Phase A stands between the adversarial set and a false PASS, so this also
checks the charter's hard gate end to end.
"""

import json
from datetime import UTC, datetime

import pytest

from legalai_contracts import ReportStatus, Verdict
from legalai_evaluation import (
    GateVerdict,
    OracleBuilder,
    SyntheticDataset,
    load_synthetic_dataset,
    run_evaluation,
)
from legalai_verification import IndependentVerifier, ModelCallError

FIXED_TIME = datetime(2026, 10, 30, tzinfo=UTC)


def _first_quote(node: object) -> str | None:
    if isinstance(node, dict):
        if isinstance(node.get("quote"), str) and isinstance(node.get("text"), str):
            return str(node["quote"])
        children: list[object] = list(node.values())
    elif isinstance(node, list):
        children = list(node)
    else:
        return None
    for child in children:
        found = _first_quote(child)
        if found is not None:
            return found
    return None


class ApproveEverythingModel:
    """Answers 'supported' to every Phase B question, quoting a verbatim passage from the payload."""

    model_id = "evaluation-fake:approve-everything"

    def complete_json(self, system_prompt: str, user_content: str) -> str:
        quote = _first_quote(json.loads(user_content)) or ""
        return json.dumps({"verdict": "supported", "basis_quote": quote, "rationale": "fake approval"})


class UnavailableModel:
    model_id = "evaluation-fake:unavailable"

    def complete_json(self, system_prompt: str, user_content: str) -> str:
        raise ModelCallError("fake outage")


@pytest.fixture(scope="module")
def dataset() -> SyntheticDataset:
    return load_synthetic_dataset()


def test_phase_a_alone_blocks_every_adversarial_item(dataset: SyntheticDataset) -> None:
    verifier = IndependentVerifier(
        source_store=dataset.source_store, case_store=dataset.case_file_store, model=ApproveEverythingModel()
    )
    report = run_evaluation(dataset, OracleBuilder(dataset), verifier, created_at=FIXED_TIME)
    assert report.adversarial.items == 80
    assert report.adversarial.verifier_errors == 0
    assert report.adversarial.false_pass == 0
    assert report.adversarial.target_false_supported == 0
    assert {g.metric: g.verdict for g in report.gate.results}["adversarial_false_pass"] is GateVerdict.PASS
    # The expected outlines themselves are clean, so an approving model lets them PASS.
    assert report.overall.verifier_pass.denominator == 10
    assert report.overall.verifier_pass.numerator == 10
    assert report.overall.verifier_false_pass == 0


def test_model_outage_never_yields_pass(dataset: SyntheticDataset) -> None:
    verifier = IndependentVerifier(
        source_store=dataset.source_store, case_store=dataset.case_file_store, model=UnavailableModel()
    )
    report = run_evaluation(dataset, OracleBuilder(dataset), verifier, created_at=FIXED_TIME)
    assert report.adversarial.false_pass == 0
    assert report.overall.verifier_pass.numerator == 0
    for result in report.adversarial_results:
        assert result.status is not ReportStatus.PASS
        assert result.target_verdict is not Verdict.SUPPORTED
