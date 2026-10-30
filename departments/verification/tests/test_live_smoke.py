"""REQ-PMO-0004 AC4: live Phase B smoke test against the configured DeepInfra model (ADR-0003).

Run with:  uv run pytest -m live departments/verification/tests/test_live_smoke.py
Needs DEEPINFRA_API_KEY and LLM_BASE_URL, plus VERIFICATION_LLM_MODEL or LLM_MODEL, in the environment.
Skips cleanly when any is missing. Only synthetic ZZ data is sent (P9).
The test (not the package) reads the environment, standing in for `interface`.
"""

import os

import pytest

from legalai_contracts import Verdict
from legalai_verification import IndependentVerifier, OpenAICompatibleChatModel, VerificationModelConfig
from legalai_verification._testkit import (
    ACT,
    ART3,
    build_world,
    element,
    good_elements,
    good_links,
    law_cite,
    outline,
)

pytestmark = pytest.mark.live


def _config() -> VerificationModelConfig:
    key = os.environ.get("DEEPINFRA_API_KEY", "").strip()
    base_url = os.environ.get("LLM_BASE_URL", "").strip()
    model = (os.environ.get("VERIFICATION_LLM_MODEL") or os.environ.get("LLM_MODEL") or "").strip()
    if not (key and base_url and model):
        pytest.skip("live model not configured (DEEPINFRA_API_KEY, LLM_BASE_URL, LLM_MODEL)")
    return VerificationModelConfig(base_url=base_url, api_key=key, model=model, timeout_seconds=180)


def test_live_phase_b_judges_synthetic_outline() -> None:
    model = OpenAICompatibleChatModel(_config())
    world = build_world()
    e1, e2 = good_elements(world)
    l1, l2 = good_links(world)
    # Cites a valid, in-force article that is about liquidated damages, not about written form.
    unrelated = element("e3", "合同必须以书面形式订立", law_cite(world, ACT, "v2025", ART3, "支付违约金"))
    report = IndependentVerifier(
        source_store=world.sources, case_store=world.cases, model=model
    ).verify_outline(outline(world, (e1, e2, unrelated), (l1, l2)))
    by_id = {i.item_id: i for i in report.items}
    for item in report.items:
        print(f"{item.item_id}: {item.verdict.value} [{item.method}] {item.rationale}")
    # The model answered every item in the strict schema with a grounded quote.
    assert all(i.verdict is not Verdict.CHECK_ERROR for i in report.items), "model reply rejected"
    # Obvious positive: article 1 states the delivery-failure element almost verbatim.
    assert by_id["e1"].verdict is Verdict.SUPPORTED
    assert by_id["l1"].verdict is Verdict.SUPPORTED
    # Obvious negative: never SUPPORTED.
    assert by_id["e3"].verdict is not Verdict.SUPPORTED
