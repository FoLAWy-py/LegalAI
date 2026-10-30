"""Store misbehaviour and malformed input: an internal error is CHECK_ERROR for that item, never SUPPORTED."""

from legalai_contracts import (
    CaseDocument,
    EvidenceOutline,
    ReportStatus,
    SourceDocument,
    Verdict,
)
from legalai_verification import IndependentVerifier
from legalai_verification._testkit import (
    ACT,
    ApprovingModel,
    FakeCaseFileStore,
    FakeSourceStore,
    World,
    build_world,
    good_elements,
    good_links,
    good_outline,
    outline,
)


class RaisingTextStore(FakeSourceStore):
    def get_text(self, doc_id: str, version_id: str, start_char: int, end_char: int) -> str:
        raise RuntimeError("disk error")


class WrongLengthStore(FakeSourceStore):
    def get_text(self, doc_id: str, version_id: str, start_char: int, end_char: int) -> str:
        return super().get_text(doc_id, version_id, start_char, end_char)[:-1]


class WrongDocumentStore(FakeSourceStore):
    def get_document(self, doc_id: str, version_id: str) -> SourceDocument:
        return super().get_document(ACT, "v2020")


class ValueErrorStore(FakeSourceStore):
    def get_document(self, doc_id: str, version_id: str) -> SourceDocument:
        raise ValueError("backend unavailable")


class UnlistedCaseStore(FakeCaseFileStore):
    def list_documents(self, case_id: str) -> list[CaseDocument]:
        return []


def _with_sources(cls: type[FakeSourceStore]) -> World:
    base = build_world()
    store = cls()
    for doc in base.sources.list_documents("ZZ") + base.sources.list_documents("ZZ-B"):
        store.add(
            doc.doc_id,
            doc.version_id,
            base.sources.full_text(doc.doc_id, doc.version_id),
            effective_from=doc.effective_from,
            effective_to=doc.effective_to,
            jurisdiction=doc.jurisdiction,
            doc_type=doc.doc_type,
            language=doc.language,
        )
    return World(sources=store, cases=base.cases, query=base.query)


def _element_verdicts(world: World) -> tuple[list[Verdict], ApprovingModel]:
    model = ApprovingModel()
    report = IndependentVerifier(
        source_store=world.sources, case_store=world.cases, model=model
    ).verify_outline(outline(world, good_elements(build_world())))
    assert report.status is ReportStatus.FAIL
    return [i.verdict for i in report.items], model


def test_store_exception_on_text_is_check_error() -> None:
    verdicts, model = _element_verdicts(_with_sources(RaisingTextStore))
    assert verdicts == [Verdict.CHECK_ERROR, Verdict.CHECK_ERROR]
    assert model.calls == []


def test_store_returning_wrong_length_is_check_error() -> None:
    verdicts, model = _element_verdicts(_with_sources(WrongLengthStore))
    assert verdicts == [Verdict.CHECK_ERROR, Verdict.CHECK_ERROR]
    assert model.calls == []


def test_store_returning_other_document_is_check_error() -> None:
    verdicts, _ = _element_verdicts(_with_sources(WrongDocumentStore))
    assert verdicts == [Verdict.CHECK_ERROR, Verdict.CHECK_ERROR]


def test_store_non_lookup_exception_is_check_error() -> None:
    verdicts, _ = _element_verdicts(_with_sources(ValueErrorStore))
    assert verdicts == [Verdict.CHECK_ERROR, Verdict.CHECK_ERROR]


def test_case_document_not_listed_for_case_is_invalid() -> None:
    base = build_world()
    cases = UnlistedCaseStore()
    for doc in base.cases.list_documents("zz-case-001"):
        text = base.cases.full_text(doc.doc_id, doc.version_id)
        pages = [text[a:b] for a, b in zip(doc.page_starts, (*doc.page_starts[1:], len(text)), strict=True)]
        cases.add(doc.case_id, doc.doc_id, doc.version_id, pages)
    world = World(sources=base.sources, cases=cases, query=base.query)
    model = ApprovingModel()
    report = IndependentVerifier(source_store=world.sources, case_store=cases, model=model).verify_outline(
        good_outline(base)
    )
    verdicts = {i.item_id: i.verdict for i in report.items}
    assert verdicts["l1"] is Verdict.CITATION_INVALID
    assert verdicts["l2"] is Verdict.CITATION_INVALID
    assert cases.text_reads == []


def test_item_error_is_isolated_to_that_item() -> None:
    """A link pointing at a broken object fails alone; other items are still judged."""
    world = build_world()
    l1, l2 = good_links(world)
    broken = l2.model_copy(update={"citation": None})
    bad = EvidenceOutline.model_construct(**{**good_outline(world).__dict__, "links": (l1, broken)})
    report = IndependentVerifier(
        source_store=world.sources, case_store=world.cases, model=ApprovingModel()
    ).verify_outline(bad)
    verdicts = {i.item_id: i.verdict for i in report.items}
    assert verdicts == {
        "e1": Verdict.SUPPORTED,
        "e2": Verdict.SUPPORTED,
        "l1": Verdict.SUPPORTED,
        "l2": Verdict.CHECK_ERROR,
    }
    assert report.status is ReportStatus.FAIL


def test_duplicate_item_ids_are_check_error() -> None:
    world = build_world()
    e1, _ = good_elements(world)
    l1, _ = good_links(world)
    dup = EvidenceOutline.model_construct(**{**outline(world, (e1,), (l1,)).__dict__, "elements": (e1, e1)})
    report = IndependentVerifier(
        source_store=world.sources, case_store=world.cases, model=ApprovingModel()
    ).verify_outline(dup)
    assert [(i.item_id, i.verdict) for i in report.items] == [
        ("e1", Verdict.CHECK_ERROR),
        ("e1", Verdict.CHECK_ERROR),
        ("l1", Verdict.UNSUPPORTED),  # its element is ambiguous
    ]
    assert report.status is ReportStatus.FAIL


def test_link_to_unknown_element_is_unsupported() -> None:
    world = build_world()
    e1, _ = good_elements(world)
    l1, _ = good_links(world)
    stray = l1.model_copy(update={"link_id": "l9", "element_id": "e-missing"})
    bad = EvidenceOutline.model_construct(**{**outline(world, (e1,), (l1,)).__dict__, "links": (l1, stray)})
    model = ApprovingModel()
    report = IndependentVerifier(
        source_store=world.sources, case_store=world.cases, model=model
    ).verify_outline(bad)
    assert [i.verdict for i in report.items] == [Verdict.SUPPORTED, Verdict.SUPPORTED, Verdict.UNSUPPORTED]


def test_outline_query_without_case_id_rejects_evidence() -> None:
    world = build_world()
    query = world.query.model_copy(update={"case_id": None})
    base = good_outline(world)
    bad = EvidenceOutline.model_construct(**{**base.__dict__, "query": query})
    report = IndependentVerifier(
        source_store=world.sources, case_store=world.cases, model=ApprovingModel()
    ).verify_outline(bad)
    verdicts = {i.item_id: i.verdict for i in report.items}
    assert verdicts["l1"] is Verdict.CITATION_INVALID
    assert verdicts["l2"] is Verdict.CITATION_INVALID


def test_abstained_outline_reports_abstain() -> None:
    world = build_world()
    abstained = EvidenceOutline(
        query=world.query,
        cause_of_action="",
        abstained=True,
        abstain_reason="SYNTHETIC: no applicable law found",
        traces=good_outline(world).traces,
    )
    model = ApprovingModel()
    report = IndependentVerifier(
        source_store=world.sources, case_store=world.cases, model=model
    ).verify_outline(abstained)
    assert report.status is ReportStatus.ABSTAIN
    assert report.items == ()
    assert model.calls == []
    assert report.query_id == world.query.query_id
