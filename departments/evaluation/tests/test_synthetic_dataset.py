"""REQ-PMO-0005 AC1: the synthetic `ZZ` set loads, meets the required mix, and expected outlines are valid.

All data checked here is fictional (jurisdiction `ZZ`, marker SYNTHETIC).
"""

from collections import Counter

import pytest

from legalai_contracts import (
    CaseFileStore,
    EvidenceOutline,
    EvidenceRelation,
    EvidenceRetriever,
    PartyRole,
    Retriever,
    SourceKind,
    SourceStore,
)
from legalai_evaluation import (
    AdversarialKind,
    CaseTag,
    EvalCase,
    InMemoryCaseFileStore,
    InMemorySourceStore,
    SyntheticDataset,
    check_citation,
    load_synthetic_dataset,
)
from legalai_evaluation.metrics import outline_citations, quote_range


@pytest.fixture(scope="module")
def dataset() -> SyntheticDataset:
    return load_synthetic_dataset()


def _fully_in(case: EvalCase, language: str) -> bool:
    return case.query_language == language and CaseTag.CROSS_LINGUAL not in case.tags


def test_required_mix(dataset: SyntheticDataset) -> None:
    cases = dataset.cases
    tags = Counter(t for c in cases for t in c.tags)
    assert len(cases) >= 10
    assert tags[CaseTag.FINANCIAL_OFFENCE] >= 7
    assert sum(_fully_in(c, "zh") for c in cases) >= 3
    assert sum(_fully_in(c, "en") for c in cases) >= 3
    assert tags[CaseTag.CROSS_LINGUAL] >= 2
    assert tags[CaseTag.MISSING_EVIDENCE] >= 2
    assert tags[CaseTag.DEFENCE_WITH_CONTRADICTING_EVIDENCE] >= 1
    assert tags[CaseTag.NO_APPLICABLE_LAW] >= 1


def test_hand_counted_totals(dataset: SyntheticDataset) -> None:
    # Hand-counted from synthetic/_cases.py; other tests rely on these numbers.
    assert len(dataset.cases) == 11
    assert sum(len(c.expected.elements) for c in dataset.cases) == 36
    assert sum(len(c.expected.links) for c in dataset.cases) == 62
    assert sum(len(c.expected.gaps) for c in dataset.cases) == 3
    assert len(dataset.adversarial) == 80
    assert Counter(a.kind for a in dataset.adversarial) == {kind: 10 for kind in AdversarialKind}


def test_every_expected_outline_passes_contract_validation(dataset: SyntheticDataset) -> None:
    for case in dataset.cases:
        again = EvidenceOutline.model_validate(case.expected.model_dump())
        assert again == case.expected
        assert EvalCase.model_validate(case.model_dump()) == case
    for item in dataset.adversarial:
        assert EvidenceOutline.model_validate(item.outline.model_dump()) == item.outline


def test_every_expected_citation_resolves_matches_and_is_in_scope(dataset: SyntheticDataset) -> None:
    total = 0
    for case in dataset.cases:
        for citation in outline_citations(case.expected):
            check = check_citation(citation, case.query, dataset.source_store, dataset.case_file_store)
            assert check.resolvable and check.quote_matches and check.in_scope, (case.case_id, citation.quote)
            total += 1
    assert total == 36 + 62


def test_every_adversarial_item_has_exactly_one_bad_citation(dataset: SyntheticDataset) -> None:
    for item in dataset.adversarial:
        query = item.outline.query
        checks = [
            check_citation(c, query, dataset.source_store, dataset.case_file_store)
            for c in outline_citations(item.outline)
        ]
        bad = [k for k in checks if not (k.resolvable and k.quote_matches and k.in_scope)]
        assert len(bad) == 1, item.item_id


def test_everything_is_synthetic_zz(dataset: SyntheticDataset) -> None:
    assert isinstance(dataset.source_store, InMemorySourceStore)
    assert isinstance(dataset.case_file_store, InMemoryCaseFileStore)
    for law in dataset.source_store.all_documents():
        assert law.jurisdiction.startswith("ZZ")
        assert "SYNTHETIC" in law.title
        assert law.source_uri.startswith("synthetic://")
    for doc in dataset.case_file_store.all_documents():
        assert "SYNTHETIC" in doc.title
    for case in dataset.cases:
        assert case.query.jurisdiction == "ZZ"
        assert "SYNTHETIC" in case.title


def test_party_roles_follow_adr_0006(dataset: SyntheticDataset) -> None:
    roles = {c.case_id: c.query.party_role for c in dataset.cases}
    assert set(roles.values()) == {PartyRole.PROSECUTION, PartyRole.DEFENDANT}
    for case in dataset.cases:
        for element in case.expected.elements:
            # ADR-0006 §3.2: no synthetic offence provision states the burden for its own element.
            assert element.burden_on is None


def test_defence_case_uses_contradicting_links_not_elements(dataset: SyntheticDataset) -> None:
    case = next(c for c in dataset.cases if CaseTag.DEFENCE_WITH_CONTRADICTING_EVIDENCE in c.tags)
    relations = {link.relation for link in case.expected.links}
    assert relations == {EvidenceRelation.SUPPORTS, EvidenceRelation.CONTRADICTS}
    assert not any("defence" in e.description.lower() for e in case.expected.elements)


def test_missing_evidence_cases_declare_gaps(dataset: SyntheticDataset) -> None:
    for case in dataset.cases:
        if CaseTag.MISSING_EVIDENCE in case.tags or CaseTag.DEFECTIVE_EVIDENCE in case.tags:
            assert case.expected.gaps, case.case_id


def test_cross_lingual_cases_cite_sources_in_another_language(dataset: SyntheticDataset) -> None:
    for case in dataset.cases:
        if CaseTag.CROSS_LINGUAL not in case.tags:
            continue
        law_langs = {
            dataset.source_store.get_document(c.span.doc_id, c.span.version_id).language
            for e in case.expected.elements
            for c in e.legal_basis
        }
        assert law_langs and case.query_language not in law_langs, case.case_id


def test_expected_element_anchors_are_disjoint(dataset: SyntheticDataset) -> None:
    """Element matching is only unambiguous if no two expected elements share a quoted range."""
    for case in dataset.cases:
        ranges = [(e.element_id, quote_range(c)) for e in case.expected.elements for c in e.legal_basis]
        for i, (a_id, a) in enumerate(ranges):
            for b_id, b in ranges[i + 1 :]:
                assert a_id == b_id or not a.overlaps(b), (case.case_id, a_id, b_id)


def test_abstention_case_has_no_law_in_force_for_the_charge(dataset: SyntheticDataset) -> None:
    case = next(c for c in dataset.cases if CaseTag.NO_APPLICABLE_LAW in c.tags)
    assert case.expects_abstention
    spans = dataset.retriever.retrieve(case.query, 1000)
    assert spans
    assert all(s.pinpoint != "Article 30" for s in spans)


def test_fakes_implement_the_ports(dataset: SyntheticDataset) -> None:
    assert isinstance(dataset.source_store, SourceStore)
    assert isinstance(dataset.case_file_store, CaseFileStore)
    assert isinstance(dataset.retriever, Retriever)
    assert isinstance(dataset.evidence_retriever, EvidenceRetriever)


def test_retriever_filters_jurisdiction_and_time(dataset: SyntheticDataset) -> None:
    for case in dataset.cases:
        for span in dataset.retriever.retrieve(case.query, 1000):
            doc = dataset.source_store.get_document(span.doc_id, span.version_id)
            assert doc.jurisdiction == case.query.jurisdiction
            assert doc.in_force_on(case.query.as_of)
            assert span.source is SourceKind.LAW


def test_evidence_retriever_stays_inside_the_case(dataset: SyntheticDataset) -> None:
    for case in dataset.cases:
        assert case.query.case_id is not None
        for span in dataset.evidence_retriever.search_case(case.query.case_id, case.query.text, 1000):
            doc = dataset.case_file_store.get_document(span.doc_id, span.version_id)
            assert doc.case_id == case.query.case_id


def test_every_expected_citation_is_retrievable_with_large_k(dataset: SyntheticDataset) -> None:
    for case in dataset.cases:
        law = dataset.retriever.retrieve(case.query, 1000)
        assert case.query.case_id is not None
        evidence = dataset.evidence_retriever.search_case(case.query.case_id, "", 1000)
        for e in case.expected.elements:
            assert all(c.span in law for c in e.legal_basis), case.case_id
        for link in case.expected.links:
            assert link.citation.span in evidence, case.case_id


def test_store_errors_are_lookup_or_value_errors(dataset: SyntheticDataset) -> None:
    with pytest.raises(KeyError):
        dataset.source_store.get_document("zz-nonexistent", "v1")
    law = dataset.source_store.all_documents()[0]
    with pytest.raises(ValueError):
        dataset.source_store.get_text(law.doc_id, law.version_id, 0, law.char_count + 1)


def test_fingerprint_is_stable_and_sensitive() -> None:
    a, b = load_synthetic_dataset(), load_synthetic_dataset()
    assert a.fingerprint() == b.fingerprint()
    assert len(a.fingerprint()) == 64
    trimmed = SyntheticDataset(
        dataset_id=a.dataset_id,
        version=a.version,
        cases=a.cases[:-1],
        adversarial=a.adversarial,
        source_store=a.source_store,
        case_file_store=a.case_file_store,
        document_manifest=a.document_manifest,
        retriever=a.retriever,
        evidence_retriever=a.evidence_retriever,
    )
    assert trimmed.fingerprint() != a.fingerprint()
