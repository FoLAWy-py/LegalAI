"""The `Verifier` implementation: Phase A (deterministic, decisive on failure), then Phase B (model)."""

from collections import Counter
from collections.abc import Callable, Sequence
from functools import partial

from legalai_contracts import (
    CaseFileStore,
    Citation,
    Claim,
    ClaimKind,
    DraftAnswer,
    Element,
    EvidenceLink,
    EvidenceOutline,
    ItemVerification,
    LegalQuery,
    ReportStatus,
    SourceKind,
    SourceStore,
    Verdict,
    VerificationReport,
)
from legalai_verification._phase_a import (
    CitationFailure,
    CitationOutcome,
    ResolvedCitation,
    check_case_citation,
    check_law_citation,
    worst_failure,
)
from legalai_verification._phase_b import ModelJudge, citation_payload
from legalai_verification._prompts import (
    CLAIM_PROMPT,
    ELEMENT_PROMPT,
    INFERENCE_PROMPT,
    LINK_PROMPT,
    load_prompts,
)
from legalai_verification.model_client import JsonChatModel

VERIFIER_VERSION = "legalai_verification/0.1.0"
"""Recorded in every `VerificationReport.verifier_version`. Bump when checks or prompts change."""

_ERROR_LIMIT = 300


def _item(item_id: str, verdict: Verdict, method: str, rationale: str) -> ItemVerification:
    return ItemVerification(item_id=item_id, verdict=verdict, method=method, rationale=rationale)


def _guarded(item_id: str, check: Callable[[], ItemVerification]) -> ItemVerification:
    """Run one item's checks. Any exception becomes CHECK_ERROR for that item only (charter)."""
    try:
        result = check()
    except Exception as exc:  # noqa: BLE001 - fail closed: an internal error must never become SUPPORTED
        detail = f"{type(exc).__name__}: {exc}"[:_ERROR_LIMIT]
        return _item(item_id, Verdict.CHECK_ERROR, "guard:internal_error", detail)
    if not isinstance(result, ItemVerification) or result.item_id != item_id:
        return _item(item_id, Verdict.CHECK_ERROR, "guard:internal_error", "check returned an invalid result")
    return result


def _safe_id(value: object, fallback: str) -> str:
    return value if isinstance(value, str) and value else fallback


def _as_tuple(value: object) -> tuple[object, ...]:
    if isinstance(value, tuple | list):
        return tuple(value)
    raise TypeError(f"expected a sequence, got {type(value).__name__}")


def _report(query_id: str, items: Sequence[ItemVerification]) -> VerificationReport:
    passed = bool(items) and all(i.verdict is Verdict.SUPPORTED for i in items)
    return VerificationReport(
        query_id=query_id,
        status=ReportStatus.PASS if passed else ReportStatus.FAIL,
        items=tuple(items),
        verifier_version=VERIFIER_VERSION,
    )


def _abstain(query_id: str) -> VerificationReport:
    return VerificationReport(
        query_id=query_id, status=ReportStatus.ABSTAIN, items=(), verifier_version=VERIFIER_VERSION
    )


def _decide_phase_a(
    item_id: str, outcomes: Sequence[CitationOutcome]
) -> list[ResolvedCitation] | ItemVerification:
    """All citations resolved, or the item's Phase A verdict (decisive: Phase B is skipped)."""
    failures = [o for o in outcomes if isinstance(o, CitationFailure)]
    if failures:
        decisive = worst_failure(failures)
        return _item(item_id, decisive.verdict, decisive.method, "; ".join(f.reason for f in failures))
    return [o for o in outcomes if isinstance(o, ResolvedCitation)]


class IndependentVerifier:
    """Checks every element, evidence link and claim against the authoritative stores (P1-P4).

    Guarantees:
    - One report item per element (`item_id = element_id`) and per evidence link (`item_id = link_id`);
      for drafts, one per claim (`item_id = claim_id`).
    - Phase A runs first and makes no model call; any Phase A failure decides the item's verdict and
      the model is not consulted for that item.
    - Phase B runs only on items whose citations all passed Phase A, using verification's own prompts
      and only text re-read from the stores.
    - Any error yields CHECK_ERROR for the affected item; nothing that is not positively established
      is SUPPORTED.
    - Report status is PASS only if every item is SUPPORTED; an abstained input yields ABSTAIN.
    - Reads no environment variables; stores and model are injected.
    """

    def __init__(self, *, source_store: SourceStore, case_store: CaseFileStore, model: JsonChatModel) -> None:
        self._sources = source_store
        self._cases = case_store
        self._judge = ModelJudge(model)
        self._prompts = load_prompts()

    # ----------------------------------------------------------------- outlines

    def verify_outline(self, outline: EvidenceOutline) -> VerificationReport:
        """Judge every element and evidence link of `outline`."""
        query = outline.query
        if outline.abstained:
            return _abstain(query.query_id)
        elements = _as_tuple(outline.elements)
        links = _as_tuple(outline.links)
        element_ids = [
            _safe_id(getattr(e, "element_id", None), f"element[{i}]") for i, e in enumerate(elements)
        ]
        link_ids = [_safe_id(getattr(lk, "link_id", None), f"link[{i}]") for i, lk in enumerate(links)]
        counts = Counter(element_ids + link_ids)
        by_id = {
            eid: e
            for eid, e in zip(element_ids, elements, strict=True)
            if isinstance(e, Element) and counts[eid] == 1
        }

        items: list[ItemVerification] = []
        for eid, element in zip(element_ids, elements, strict=True):
            if counts[eid] > 1:
                items.append(_item(eid, Verdict.CHECK_ERROR, "input:duplicate_id", "item id is not unique"))
            else:
                items.append(_guarded(eid, partial(self._verify_element, eid, element, outline, query)))
        for lid, link in zip(link_ids, links, strict=True):
            if counts[lid] > 1:
                items.append(_item(lid, Verdict.CHECK_ERROR, "input:duplicate_id", "item id is not unique"))
            else:
                items.append(_guarded(lid, partial(self._verify_link, lid, link, by_id, query)))
        return _report(query.query_id, items)

    def _verify_element(
        self, item_id: str, element: object, outline: EvidenceOutline, query: LegalQuery
    ) -> ItemVerification:
        if not isinstance(element, Element):
            return _item(item_id, Verdict.CHECK_ERROR, "input:type", "element is not a contract Element")
        basis = _as_tuple(element.legal_basis)
        if not basis:
            return _item(item_id, Verdict.CITATION_INVALID, "phase_a:no_citation", "element cites no law")
        outcomes = [
            self._law(c, f"legal_basis[{n}]", query, require_law_doc_type=True) for n, c in enumerate(basis)
        ]
        resolved = _decide_phase_a(item_id, outcomes)
        if isinstance(resolved, ItemVerification):
            return resolved
        payload: dict[str, object] = {
            "jurisdiction": query.jurisdiction,
            "as_of": query.as_of.isoformat(),
            "cause_of_action": outline.cause_of_action,
            "element": element.description,
            "burden_on": element.burden_on.value if element.burden_on is not None else None,
            "legal_basis": [citation_payload(c) for c in resolved],
        }
        return self._judge.judge(
            item_id=item_id,
            prompt=self._prompts[ELEMENT_PROMPT],
            payload=payload,
            grounding_texts=[c.stored_text for c in resolved],
        )

    def _verify_link(
        self, item_id: str, link: object, elements: dict[str, Element], query: LegalQuery
    ) -> ItemVerification:
        if not isinstance(link, EvidenceLink):
            return _item(item_id, Verdict.CHECK_ERROR, "input:type", "link is not a contract EvidenceLink")
        resolved = _decide_phase_a(item_id, [self._case(link.citation, "citation", query)])
        if isinstance(resolved, ItemVerification):
            return resolved
        element = elements.get(link.element_id)
        if element is None:
            return _item(
                item_id,
                Verdict.UNSUPPORTED,
                "input:unknown_element",
                "link refers to an unknown or ambiguous element",
            )
        if not isinstance(link.purpose, str) or not link.purpose.strip():
            return _item(item_id, Verdict.UNSUPPORTED, "input:no_purpose", "link states no purpose")
        evidence = resolved[0]
        payload: dict[str, object] = {
            "element": element.description,
            "relation": link.relation.value,
            "purpose": link.purpose,
            "evidence": citation_payload(evidence),
        }
        return self._judge.judge(
            item_id=item_id,
            prompt=self._prompts[LINK_PROMPT],
            payload=payload,
            grounding_texts=[evidence.stored_text],
        )

    # ------------------------------------------------------------------- drafts

    def verify(self, draft: DraftAnswer) -> VerificationReport:
        """Judge every claim of `draft`; an inference is SUPPORTED only if all its premises are."""
        query = draft.query
        if draft.abstained:
            return _abstain(query.query_id)
        run = _DraftRun(self, query, _as_tuple(draft.claims))
        return _report(query.query_id, [run.resolve(cid, frozenset()) for cid in run.ids])

    def _check_claim(self, claim: Claim, query: LegalQuery) -> list[ResolvedCitation] | ItemVerification:
        """Phase A for one claim's citations."""
        outcomes: list[CitationOutcome] = []
        for n, citation in enumerate(_as_tuple(claim.citations)):
            label = f"citations[{n}]"
            if not isinstance(citation, Citation):
                outcomes.append(
                    CitationFailure(Verdict.CHECK_ERROR, "phase_a:input_type", f"{label}: not a Citation")
                )
            elif citation.span.source is SourceKind.CASE_FILE and claim.kind is ClaimKind.LEGAL_RULE:
                outcomes.append(
                    CitationFailure(
                        Verdict.CITATION_INVALID,
                        "phase_a:source_kind",
                        f"{label}: a legal rule must cite law, not a case file",
                    )
                )
            elif citation.span.source is SourceKind.CASE_FILE:
                outcomes.append(self._case(citation, label, query))
            else:
                outcomes.append(
                    self._law(citation, label, query, require_law_doc_type=claim.kind is ClaimKind.LEGAL_RULE)
                )
        return _decide_phase_a(claim.claim_id, outcomes)

    def _judge_claim(
        self, claim: Claim, query: LegalQuery, resolved: Sequence[ResolvedCitation]
    ) -> ItemVerification:
        payload: dict[str, object] = {
            "jurisdiction": query.jurisdiction,
            "as_of": query.as_of.isoformat(),
            "kind": claim.kind.value,
            "claim": claim.text,
            "sources": [citation_payload(c) for c in resolved],
        }
        return self._judge.judge(
            item_id=claim.claim_id,
            prompt=self._prompts[CLAIM_PROMPT],
            payload=payload,
            grounding_texts=[c.stored_text for c in resolved],
        )

    def _judge_inference(
        self, claim: Claim, premises: Sequence[Claim], resolved: Sequence[ResolvedCitation]
    ) -> ItemVerification:
        payload: dict[str, object] = {
            "conclusion": claim.text,
            "premises": [{"text": p.text} for p in premises],
            "sources": [citation_payload(c) for c in resolved],
        }
        return self._judge.judge(
            item_id=claim.claim_id,
            prompt=self._prompts[INFERENCE_PROMPT],
            payload=payload,
            grounding_texts=[p.text for p in premises] + [c.stored_text for c in resolved],
        )

    # ------------------------------------------------------------------ helpers

    def _law(
        self, citation: object, label: str, query: LegalQuery, *, require_law_doc_type: bool
    ) -> CitationOutcome:
        if not isinstance(citation, Citation):
            return CitationFailure(Verdict.CHECK_ERROR, "phase_a:input_type", f"{label}: not a Citation")
        return check_law_citation(
            citation, label=label, query=query, store=self._sources, require_law_doc_type=require_law_doc_type
        )

    def _case(self, citation: object, label: str, query: LegalQuery) -> CitationOutcome:
        if not isinstance(citation, Citation):
            return CitationFailure(Verdict.CHECK_ERROR, "phase_a:input_type", f"{label}: not a Citation")
        return check_case_citation(citation, label=label, query=query, store=self._cases)


class _DraftRun:
    """Per-draft state: each claim is judged once (memoised); premises are resolved before inferences."""

    def __init__(self, verifier: IndependentVerifier, query: LegalQuery, claims: tuple[object, ...]) -> None:
        self._verifier = verifier
        self._query = query
        self.ids = [_safe_id(getattr(c, "claim_id", None), f"claim[{i}]") for i, c in enumerate(claims)]
        self._counts = Counter(self.ids)
        self._by_id = {
            cid: c
            for cid, c in zip(self.ids, claims, strict=True)
            if isinstance(c, Claim) and self._counts[cid] == 1
        }
        self._done: dict[str, ItemVerification] = {}

    def resolve(self, cid: str, active: frozenset[str]) -> ItemVerification:
        if cid in self._done:
            return self._done[cid]
        if self._counts[cid] > 1:
            result = _item(cid, Verdict.CHECK_ERROR, "input:duplicate_id", "item id is not unique")
        elif cid not in self._by_id:
            result = _item(cid, Verdict.CHECK_ERROR, "input:type", "claim is not a contract Claim")
        else:
            result = _guarded(cid, partial(self._check, cid, active | {cid}))
        self._done[cid] = result
        return result

    def _check(self, cid: str, active: frozenset[str]) -> ItemVerification:
        claim = self._by_id[cid]
        if claim.kind is not ClaimKind.INFERENCE and not _as_tuple(claim.citations):
            return _item(cid, Verdict.CITATION_INVALID, "phase_a:no_citation", "claim cites no source")
        resolved = self._verifier._check_claim(claim, self._query)
        if isinstance(resolved, ItemVerification):
            return resolved
        if claim.kind is not ClaimKind.INFERENCE:
            return self._verifier._judge_claim(claim, self._query, resolved)
        premise_ids = [p if isinstance(p, str) else repr(p) for p in _as_tuple(claim.derived_from)]
        if not premise_ids:
            return _item(cid, Verdict.UNSUPPORTED, "phase_a:premises", "inference names no premises")
        premises: list[Claim] = []
        for pid in premise_ids:
            if pid in active:
                return _item(cid, Verdict.UNSUPPORTED, "phase_a:premises", f"circular premise {pid}")
            if self._counts[pid] == 0:
                return _item(cid, Verdict.UNSUPPORTED, "phase_a:premises", f"premise {pid} does not exist")
            premise_result = self.resolve(pid, active)
            if premise_result.verdict is not Verdict.SUPPORTED:
                return _item(
                    cid,
                    Verdict.UNSUPPORTED,
                    "phase_a:premises",
                    f"premise {pid} is not supported ({premise_result.verdict.value})",
                )
            premises.append(self._by_id[pid])
        return self._verifier._judge_inference(claim, premises, resolved)
