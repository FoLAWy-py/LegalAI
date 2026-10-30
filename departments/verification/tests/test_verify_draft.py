"""`verify(DraftAnswer)`: claims re-checked like outline items; inferences need supported premises."""

from legalai_contracts import (
    Citation,
    Claim,
    ClaimKind,
    DraftAnswer,
    LegalQuery,
    ReportStatus,
    TaskType,
    Verdict,
)
from legalai_verification import IndependentVerifier
from legalai_verification._testkit import (
    ACT,
    ART1,
    ART1_QUOTE,
    ART2,
    ART2_QUOTE,
    EMAIL,
    EMAIL_QUOTE,
    EMAIL_SENTENCE,
    OLD_ART1,
    TRACE,
    ApprovingModel,
    ExplodingModel,
    World,
    build_world,
    case_cite,
    law_cite,
)


def _query(world: World, *, case_id: str | None = None) -> LegalQuery:
    return LegalQuery(
        query_id="zz-q-draft",
        text="SYNTHETIC：未交付标的物的后果？",
        jurisdiction="ZZ",
        as_of=world.query.as_of,
        response_language="zh-CN",
        task_type=TaskType.RESEARCH_QA,
        case_id=case_id,
    )


def _rule(cid: str, *cites: Citation) -> Claim:
    return Claim(
        claim_id=cid,
        text="未按照约定交付标的物的，应当承担违约责任。",
        kind=ClaimKind.LEGAL_RULE,
        citations=cites,
    )


def _draft(query: LegalQuery, *claims: Claim) -> DraftAnswer:
    return DraftAnswer(query=query, claims=claims, answer_text="SYNTHETIC answer", traces=(TRACE,))


def _verify(world: World, draft: DraftAnswer, model: ApprovingModel | ExplodingModel) -> dict[str, Verdict]:
    report = IndependentVerifier(source_store=world.sources, case_store=world.cases, model=model).verify(
        draft
    )
    if all(i.verdict is Verdict.SUPPORTED for i in report.items):
        assert report.status is ReportStatus.PASS
    else:
        assert report.status is ReportStatus.FAIL
    return {i.item_id: i.verdict for i in report.items}


def test_supported_rule_and_inference_pass() -> None:
    world = build_world()
    c1 = _rule("c1", law_cite(world, ACT, "v2025", ART1, ART1_QUOTE))
    c2 = Claim(
        claim_id="c2",
        text="主张违约者须证明合同成立。",
        kind=ClaimKind.LEGAL_RULE,
        citations=(law_cite(world, ACT, "v2025", ART2, ART2_QUOTE),),
    )
    c3 = Claim(
        claim_id="c3", text="未交付者应承担违约责任。", kind=ClaimKind.INFERENCE, derived_from=("c1", "c2")
    )
    model = ApprovingModel()
    assert _verify(world, _draft(_query(world), c1, c2, c3), model) == {
        "c1": Verdict.SUPPORTED,
        "c2": Verdict.SUPPORTED,
        "c3": Verdict.SUPPORTED,
    }
    inference_payload = model.payloads()[2]
    assert inference_payload["premises"] == [{"text": c1.text}, {"text": c2.text}]


def test_inference_with_unsupported_premise_is_unsupported_without_model_call() -> None:
    world = build_world()
    bad = _rule("c1", law_cite(world, ACT, "v2020", OLD_ART1, "应当赔偿对方损失"))
    inf = Claim(claim_id="c2", text="SYNTHETIC", kind=ClaimKind.INFERENCE, derived_from=("c1",))
    model = ExplodingModel()
    assert _verify(world, _draft(_query(world), bad, inf), model) == {
        "c1": Verdict.NOT_IN_FORCE,
        "c2": Verdict.UNSUPPORTED,
    }
    assert model.calls == []


def test_inference_premise_declared_after_it_is_resolved_first() -> None:
    world = build_world()
    inf = Claim(claim_id="c2", text="SYNTHETIC", kind=ClaimKind.INFERENCE, derived_from=("c1",))
    c1 = _rule("c1", law_cite(world, ACT, "v2025", ART1, ART1_QUOTE))
    verdicts = _verify(world, _draft(_query(world), inf, c1), ApprovingModel())
    assert verdicts == {"c2": Verdict.SUPPORTED, "c1": Verdict.SUPPORTED}


def test_circular_inference_is_unsupported() -> None:
    world = build_world()
    a = Claim(claim_id="a", text="SYNTHETIC a", kind=ClaimKind.INFERENCE, derived_from=("b",))
    b = Claim(claim_id="b", text="SYNTHETIC b", kind=ClaimKind.INFERENCE, derived_from=("a",))
    selfref = Claim(claim_id="s", text="SYNTHETIC s", kind=ClaimKind.INFERENCE, derived_from=("s",))
    model = ExplodingModel()
    verdicts = _verify(world, _draft(_query(world), a, b, selfref), model)
    assert verdicts == {"a": Verdict.UNSUPPORTED, "b": Verdict.UNSUPPORTED, "s": Verdict.UNSUPPORTED}
    assert model.calls == []


def test_missing_premise_is_unsupported() -> None:
    world = build_world()
    inf = Claim.model_construct(
        claim_id="c1", text="SYNTHETIC", kind=ClaimKind.INFERENCE, citations=(), derived_from=("ghost",)
    )
    draft = DraftAnswer.model_construct(
        query=_query(world),
        claims=(inf,),
        answer_text="x",
        abstained=False,
        abstain_reason=None,
        traces=(TRACE,),
    )
    assert _verify(world, draft, ExplodingModel()) == {"c1": Verdict.UNSUPPORTED}


def test_legal_rule_citing_case_file_is_invalid() -> None:
    world = build_world()
    claim = _rule("c1", case_cite(world, EMAIL, EMAIL_SENTENCE, EMAIL_QUOTE))
    assert _verify(world, _draft(_query(world, case_id="zz-case-001"), claim), ExplodingModel()) == {
        "c1": Verdict.CITATION_INVALID
    }


def test_fact_citing_case_file_needs_query_case_id() -> None:
    world = build_world()
    fact = Claim(
        claim_id="f1",
        text="乙方表示无法按期交付货物。",
        kind=ClaimKind.FACT,
        citations=(case_cite(world, EMAIL, EMAIL_SENTENCE, EMAIL_QUOTE),),
    )
    assert _verify(world, _draft(_query(world), fact), ExplodingModel()) == {"f1": Verdict.CITATION_INVALID}
    assert world.cases.text_reads == []
    assert _verify(world, _draft(_query(world, case_id="zz-case-001"), fact), ApprovingModel()) == {
        "f1": Verdict.SUPPORTED
    }
    assert _verify(world, _draft(_query(world, case_id="zz-case-999"), fact), ExplodingModel()) == {
        "f1": Verdict.CITATION_INVALID
    }


def test_fabricated_and_wrong_jurisdiction_claims_fail() -> None:
    world = build_world()
    fabricated = _rule(
        "c1",
        law_cite(world, ACT, "v2025", ART1, ART1_QUOTE).model_copy(
            update={
                "span": law_cite(world, ACT, "v2025", ART1, ART1_QUOTE).span.model_copy(
                    update={"doc_id": "zz-x"}
                )
            }
        ),
    )
    foreign = _rule("c2", law_cite(world, "zz-b-contract-act", "v1", ART1, ART1_QUOTE))
    model = ExplodingModel()
    assert _verify(world, _draft(_query(world), fabricated, foreign), model) == {
        "c1": Verdict.CITATION_INVALID,
        "c2": Verdict.WRONG_JURISDICTION,
    }
    assert model.calls == []


def test_abstained_draft_reports_abstain() -> None:
    world = build_world()
    draft = DraftAnswer(
        query=_query(world),
        answer_text="",
        abstained=True,
        abstain_reason="SYNTHETIC: no source",
        traces=(TRACE,),
    )
    report = IndependentVerifier(
        source_store=world.sources, case_store=world.cases, model=ExplodingModel()
    ).verify(draft)
    assert report.status is ReportStatus.ABSTAIN
    assert report.items == ()
