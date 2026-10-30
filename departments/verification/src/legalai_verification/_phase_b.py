"""Phase B: model-based checks. Only ever called on items whose citations all passed Phase A.

The model sees only text re-read from the stores by Phase A (never text carried by the draft), and
its reply must match a strict schema. Anything unexpected is CHECK_ERROR, never SUPPORTED.
"""

import json
from collections.abc import Mapping, Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from legalai_contracts import ItemVerification, Verdict
from legalai_verification._phase_a import ResolvedCitation
from legalai_verification._prompts import Prompt
from legalai_verification.model_client import JsonChatModel, ModelCallError

_RATIONALE_LIMIT = 600

_VERDICTS: Mapping[str, Verdict] = {
    "supported": Verdict.SUPPORTED,
    "unsupported": Verdict.UNSUPPORTED,
    "contradicted": Verdict.CONTRADICTED,
}


class ModelJudgement(BaseModel):
    """The only reply shape accepted from the model."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    verdict: Literal["supported", "unsupported", "contradicted"]
    basis_quote: str
    rationale: str


class MalformedJudgement(Exception):
    pass


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    keys = [k for k, _ in pairs]
    if len(keys) != len(set(keys)):
        raise MalformedJudgement("duplicate keys in model reply")
    return dict(pairs)


def parse_judgement(raw: object) -> ModelJudgement:
    """Parse the model's raw reply strictly. No repair: fences, prose or extra keys are rejected."""
    if not isinstance(raw, str):
        raise MalformedJudgement("model reply is not text")
    try:
        data = json.loads(raw, object_pairs_hook=_reject_duplicate_keys)
    except json.JSONDecodeError as exc:
        raise MalformedJudgement(f"model reply is not JSON ({exc.msg})") from exc
    if not isinstance(data, dict):
        raise MalformedJudgement("model reply is not a JSON object")
    try:
        return ModelJudgement.model_validate(data, strict=True)
    except ValidationError as exc:
        raise MalformedJudgement(f"model reply does not match schema ({exc.error_count()} error(s))") from exc


def citation_payload(c: ResolvedCitation) -> dict[str, object]:
    payload: dict[str, object] = {"text": c.stored_text, "quote": c.quote}
    if c.title is not None:
        payload["title"] = c.title
    if c.pinpoint is not None:
        payload["pinpoint"] = c.pinpoint
    return payload


class ModelJudge:
    """Runs one prompt for one item and turns the reply into an `ItemVerification`."""

    def __init__(self, model: JsonChatModel) -> None:
        self._model = model

    def judge(
        self,
        *,
        item_id: str,
        prompt: Prompt,
        payload: Mapping[str, object],
        grounding_texts: Sequence[str],
    ) -> ItemVerification:
        method = f"phase_b:{prompt.ref}:model={self._model.model_id}"

        def error(reason: str) -> ItemVerification:
            return ItemVerification(
                item_id=item_id, verdict=Verdict.CHECK_ERROR, method=method, rationale=reason
            )

        user_content = json.dumps(payload, ensure_ascii=False, indent=2)
        try:
            raw = self._model.complete_json(prompt.text, user_content)
        except ModelCallError as exc:
            return error(f"model call failed: {exc}")
        try:
            judgement = parse_judgement(raw)
        except MalformedJudgement as exc:
            return error(f"malformed model reply: {exc}")
        verdict = _VERDICTS[judgement.verdict]
        if verdict is not Verdict.UNSUPPORTED:
            quote = judgement.basis_quote
            if not quote.strip() or not any(quote in text for text in grounding_texts):
                return error(
                    f"model answered {judgement.verdict!r} but its basis_quote is not verbatim in the "
                    "re-read source text"
                )
        rationale = judgement.rationale.strip()[:_RATIONALE_LIMIT] or "(model gave no rationale)"
        return ItemVerification(item_id=item_id, verdict=verdict, method=method, rationale=rationale)
