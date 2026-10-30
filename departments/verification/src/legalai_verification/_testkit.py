"""Test support for verification's own tests: in-memory ZZ fakes of the contract ports and scripted models.

Private (not in `__all__`); other departments must not use it. All data is synthetic: jurisdiction
`ZZ` (or a `ZZ-*` subdivision), titles marked SYNTHETIC, wording invented for these tests. None of the
texts below is, or quotes, real law.
"""

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from legalai_contracts import (
    CaseDocument,
    Citation,
    DocType,
    Element,
    EvidenceLink,
    EvidenceOutline,
    EvidenceRelation,
    Gap,
    GapKind,
    LegalQuery,
    ModelTrace,
    PartyRole,
    SourceDocument,
    SourceKind,
    SourceSpan,
    TaskType,
)

AS_OF = date(2026, 6, 1)
CASE_ID = "zz-case-001"
OTHER_CASE_ID = "zz-case-999"
_FETCHED = datetime(2026, 1, 1, tzinfo=UTC)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- fake stores


class FakeSourceStore:
    """In-memory `SourceStore`. Unknown doc/version raises KeyError; records every text read."""

    def __init__(self) -> None:
        self._docs: dict[tuple[str, str], tuple[SourceDocument, str]] = {}
        self.text_reads: list[tuple[str, str, int, int]] = []

    def add(
        self,
        doc_id: str,
        version_id: str,
        text: str,
        *,
        effective_from: date,
        effective_to: date | None = None,
        jurisdiction: str = "ZZ",
        doc_type: DocType = DocType.STATUTE,
        language: str = "zh-CN",
    ) -> SourceDocument:
        doc = SourceDocument(
            doc_id=doc_id,
            version_id=version_id,
            title=f"SYNTHETIC {doc_id} {version_id}",
            jurisdiction=jurisdiction,
            doc_type=doc_type,
            language=language,
            effective_from=effective_from,
            effective_to=effective_to,
            source_uri=f"synthetic://zz/{doc_id}/{version_id}",
            retrieved_at=_FETCHED,
            content_sha256=_sha(text),
            char_count=len(text),
        )
        self._docs[(doc_id, version_id)] = (doc, text)
        return doc

    def full_text(self, doc_id: str, version_id: str) -> str:
        return self._docs[(doc_id, version_id)][1]

    def list_documents(self, jurisdiction: str) -> list[SourceDocument]:
        return [d for d, _ in self._docs.values() if d.jurisdiction == jurisdiction]

    def get_document(self, doc_id: str, version_id: str) -> SourceDocument:
        return self._docs[(doc_id, version_id)][0]

    def get_text(self, doc_id: str, version_id: str, start_char: int, end_char: int) -> str:
        doc, text = self._docs[(doc_id, version_id)]
        if not 0 <= start_char < end_char <= doc.char_count:
            raise ValueError("offsets outside document")
        self.text_reads.append((doc_id, version_id, start_char, end_char))
        return text[start_char:end_char]


class FakeCaseFileStore:
    """In-memory `CaseFileStore`. Unknown doc/version raises KeyError; records every text read."""

    def __init__(self) -> None:
        self._docs: dict[tuple[str, str], tuple[CaseDocument, str]] = {}
        self.text_reads: list[tuple[str, str, int, int]] = []

    def add(self, case_id: str, doc_id: str, version_id: str, pages: list[str]) -> CaseDocument:
        text = "".join(pages)
        starts: list[int] = []
        offset = 0
        for page in pages:
            starts.append(offset)
            offset += len(page)
        doc = CaseDocument(
            case_id=case_id,
            doc_id=doc_id,
            version_id=version_id,
            title=f"SYNTHETIC {doc_id}",
            language="zh-CN",
            media_type="text/plain",
            received_at=_FETCHED,
            content_sha256=_sha(text),
            char_count=len(text),
            page_starts=tuple(starts),
        )
        self._docs[(doc_id, version_id)] = (doc, text)
        return doc

    def full_text(self, doc_id: str, version_id: str) -> str:
        return self._docs[(doc_id, version_id)][1]

    def list_documents(self, case_id: str) -> list[CaseDocument]:
        return [d for d, _ in self._docs.values() if d.case_id == case_id]

    def get_document(self, doc_id: str, version_id: str) -> CaseDocument:
        return self._docs[(doc_id, version_id)][0]

    def get_text(self, doc_id: str, version_id: str, start_char: int, end_char: int) -> str:
        doc, text = self._docs[(doc_id, version_id)]
        if not 0 <= start_char < end_char <= doc.char_count:
            raise ValueError("offsets outside document")
        self.text_reads.append((doc_id, version_id, start_char, end_char))
        return text[start_char:end_char]


# --------------------------------------------------------------------------- scripted models


@dataclass
class RecordingModel:
    """Base for fake models: records (system_prompt, user_content) of every call."""

    model_id: str = "zz-fake-model"
    calls: list[tuple[str, str]] = field(default_factory=list)

    def payloads(self) -> list[dict[str, object]]:
        out: list[dict[str, object]] = []
        for _, user in self.calls:
            loaded = json.loads(user)
            assert isinstance(loaded, dict)
            out.append(loaded)
        return out


def _first_text(node: object) -> str | None:
    if isinstance(node, dict):
        value = node.get("text")
        if isinstance(value, str) and value:
            return value
        children: list[object] = list(node.values())
    elif isinstance(node, list):
        children = list(node)
    else:
        return None
    for child in children:
        found = _first_text(child)
        if found is not None:
            return found
    return None


@dataclass
class ApprovingModel(RecordingModel):
    """Adversarial yes-man: answers 'supported' for everything, with a correctly grounded basis_quote.

    Used to prove that Phase A alone stops bad citations: if anything bad reaches this model it passes.
    """

    def complete_json(self, system_prompt: str, user_content: str) -> str:
        self.calls.append((system_prompt, user_content))
        text = _first_text(json.loads(user_content)) or ""
        return json.dumps(
            {"verdict": "supported", "basis_quote": text[:6], "rationale": "approve everything"},
            ensure_ascii=False,
        )


@dataclass
class ScriptedModel(RecordingModel):
    """Returns `reply(system_prompt, user_content)` verbatim, or raises what `reply` raises."""

    reply: Callable[[str, str], str] = field(default=lambda _s, _u: "")

    def complete_json(self, system_prompt: str, user_content: str) -> str:
        self.calls.append((system_prompt, user_content))
        return self.reply(system_prompt, user_content)


@dataclass
class ExplodingModel(RecordingModel):
    """Fails if called at all. Tests assert `calls == []` to prove a path made no model call."""

    def complete_json(self, system_prompt: str, user_content: str) -> str:
        self.calls.append((system_prompt, user_content))
        raise AssertionError("model must not be called")


# --------------------------------------------------------------------------- synthetic ZZ world

ACT = "zz-model-contract-act"
LAW_V2025 = (
    "《ZZ示范合同法》（SYNTHETIC，2025年修订）\n"
    "第一条　当事人一方未按照约定交付标的物的，应当向对方承担“违约责任”。\n"
    "第二条　主张对方违约的当事人，应当对合同成立的事实承担举证责任。\n"
    "第三条　约定违约金的，违约方应当按照约定支付违约金。\n"
)
LAW_V2020 = (
    "《ZZ示范合同法》（SYNTHETIC，2020年版）\n第一条　当事人一方未按照约定交付标的物的，应当赔偿对方损失。\n"
)
ART1 = "第一条　当事人一方未按照约定交付标的物的，应当向对方承担“违约责任”。"
ART1_QUOTE = "当事人一方未按照约定交付标的物的，应当向对方承担“违约责任”。"
ART2 = "第二条　主张对方违约的当事人，应当对合同成立的事实承担举证责任。"
ART2_QUOTE = "应当对合同成立的事实承担举证责任"
ART3 = "第三条　约定违约金的，违约方应当按照约定支付违约金。"
OLD_ART1 = "第一条　当事人一方未按照约定交付标的物的，应当赔偿对方损失。"

RULES = "zz-procedure-rules"
# U+20BB7 (outside the BMP) precedes the cited article: UTF-16 offsets would be off by one.
RULES_TEXT = "《ZZ\U00020bb7野程序规则》（SYNTHETIC）\n第一条　当事人对自己提出的主张，应当提供证据。\n"
RULES_ART1 = "第一条　当事人对自己提出的主张，应当提供证据。"

SALE_ACT = "zz-sale-act"
SALE_TEXT = (
    "SYNTHETIC ZZ Sale Act\n"
    "s. 1 A seller who fails to deliver the goods on the agreed date is liable to the buyer.\n"
)
SALE_S1 = "s. 1 A seller who fails to deliver the goods on the agreed date is liable to the buyer."

CONTRACT = "zz-contract-001"
CONTRACT_PAGES = [
    "买卖合同（SYNTHETIC）\n甲方：ZZ甲贸易有限公司\n乙方：ZZ乙制造有限公司\n",
    "第一条　乙方应于2026年3月1日前向甲方交付货物一批。\n"
    "第二条　任何一方违约的，应当向对方支付违约金ZZ币１０，０００元。\n",
]
CONTRACT_ART1 = "第一条　乙方应于2026年3月1日前向甲方交付货物一批。"
CONTRACT_ART1_QUOTE = "乙方应于2026年3月1日前向甲方交付货物一批"
CONTRACT_ART2 = "第二条　任何一方违约的，应当向对方支付违约金ZZ币１０，０００元。"

EMAIL = "zz-email-001"
EMAIL_PAGES = [
    "发件人：乙方\n收件人：甲方\n主题：关于交付\n\n甲方：因原料短缺，我方无法在约定的2026年3月1日前交付货物。\n",
    "我方愿意按照合同支付“违约金”ZZ币１０，０００元。\n乙方（SYNTHETIC）\n",
]
EMAIL_SENTENCE = "因原料短缺，我方无法在约定的2026年3月1日前交付货物。"
EMAIL_QUOTE = "我方无法在约定的2026年3月1日前交付货物"
EMAIL_PAGE2_SENTENCE = "我方愿意按照合同支付“违约金”ZZ币１０，０００元。"

OTHER_EMAIL = "zz-email-999"
OTHER_EMAIL_PAGES = ["发件人：丙方\n收件人：丁方\n\n因原料短缺，我方无法在约定的2026年3月1日前交付货物。\n"]


@dataclass
class World:
    sources: FakeSourceStore
    cases: FakeCaseFileStore
    query: LegalQuery


def build_world() -> World:
    """A small synthetic ZZ legal system with one case (`zz-case-001`) and one unrelated case."""
    sources = FakeSourceStore()
    sources.add(ACT, "v2025", LAW_V2025, effective_from=date(2025, 1, 1))
    sources.add(ACT, "v2020", LAW_V2020, effective_from=date(2020, 1, 1), effective_to=date(2025, 1, 1))
    sources.add(RULES, "v1", RULES_TEXT, effective_from=date(2024, 1, 1), doc_type=DocType.REGULATION)
    sources.add("zz-b-contract-act", "v1", LAW_V2025, effective_from=date(2025, 1, 1), jurisdiction="ZZ-B")
    sources.add("zz-future-act", "v1", LAW_V2025, effective_from=date(2027, 1, 1))
    sources.add(
        "zz-interim-rules", "v1", LAW_V2025, effective_from=date(2025, 6, 1), effective_to=AS_OF
    )  # expires exactly on as_of; end date is exclusive
    sources.add("zz-commentary", "v1", LAW_V2025, effective_from=date(2025, 1, 1), doc_type=DocType.SECONDARY)
    sources.add(SALE_ACT, "v1", SALE_TEXT, effective_from=date(2024, 1, 1), language="en")

    cases = FakeCaseFileStore()
    cases.add(CASE_ID, CONTRACT, "v1", CONTRACT_PAGES)
    cases.add(CASE_ID, EMAIL, "v1", EMAIL_PAGES)
    cases.add(OTHER_CASE_ID, OTHER_EMAIL, "v1", OTHER_EMAIL_PAGES)

    query = LegalQuery(
        query_id="zz-q-001",
        text="SYNTHETIC：乙方未按约定交付货物，甲方主张违约责任。",
        jurisdiction="ZZ",
        as_of=AS_OF,
        response_language="zh-CN",
        task_type=TaskType.EVIDENCE_OUTLINE,
        case_id=CASE_ID,
        party_role=PartyRole.PLAINTIFF,
    )
    return World(sources=sources, cases=cases, query=query)


def make_span(
    full_text: str,
    context: str,
    *,
    source: SourceKind,
    doc_id: str,
    version_id: str,
    pinpoint: str | None = None,
) -> SourceSpan:
    """A correct span over the first occurrence of `context` in `full_text` (code-point offsets)."""
    start = full_text.index(context)
    return SourceSpan(
        source=source,
        doc_id=doc_id,
        version_id=version_id,
        start_char=start,
        end_char=start + len(context),
        text=context,
        pinpoint=pinpoint,
    )


def law_cite(world: World, doc_id: str, version_id: str, context: str, quote: str) -> Citation:
    full = world.sources.full_text(doc_id, version_id)
    span = make_span(full, context, source=SourceKind.LAW, doc_id=doc_id, version_id=version_id)
    return Citation(span=span, quote=quote)


def case_cite(world: World, doc_id: str, context: str, quote: str, version_id: str = "v1") -> Citation:
    full = world.cases.full_text(doc_id, version_id)
    span = make_span(full, context, source=SourceKind.CASE_FILE, doc_id=doc_id, version_id=version_id)
    return Citation(span=span, quote=quote)


def raw_citation(
    *,
    source: SourceKind,
    doc_id: str,
    version_id: str,
    start_char: int,
    end_char: int,
    text: str,
    quote: str,
) -> Citation:
    """A citation built WITHOUT contract validation: simulates a draft that bypassed the validators."""
    span = SourceSpan.model_construct(
        source=source,
        doc_id=doc_id,
        version_id=version_id,
        start_char=start_char,
        end_char=end_char,
        text=text,
        pinpoint=None,
    )
    return Citation.model_construct(span=span, quote=quote)


TRACE = ModelTrace(model="zz-generator", prompt_id="zz.generator", prompt_version="0", temperature=0)


def element(element_id: str, description: str, *basis: Citation, validate: bool = True) -> Element:
    """An element; `validate=False` skips contract validation (bypass simulation)."""
    fields: dict[str, object] = {
        "element_id": element_id,
        "description": description,
        "legal_basis": tuple(basis),
        "burden_on": PartyRole.PLAINTIFF,
    }
    return Element.model_validate(fields) if validate else Element.model_construct(**fields)  # type: ignore[arg-type]


def link(
    link_id: str,
    element_id: str,
    citation: Citation,
    purpose: str,
    *,
    relation: EvidenceRelation = EvidenceRelation.SUPPORTS,
    validate: bool = True,
) -> EvidenceLink:
    """An evidence link; `validate=False` skips contract validation (bypass simulation)."""
    fields: dict[str, object] = {
        "link_id": link_id,
        "element_id": element_id,
        "citation": citation,
        "relation": relation,
        "purpose": purpose,
    }
    if validate:
        return EvidenceLink.model_validate(fields)
    return EvidenceLink.model_construct(**fields)  # type: ignore[arg-type]


def good_elements(world: World) -> tuple[Element, Element]:
    e1 = element("e1", "被告（乙方）未按照约定交付标的物", law_cite(world, ACT, "v2025", ART1, ART1_QUOTE))
    e2 = element("e2", "双方之间成立合同", law_cite(world, ACT, "v2025", ART2, ART2_QUOTE))
    return e1, e2


def good_links(world: World) -> tuple[EvidenceLink, EvidenceLink]:
    l1 = link(
        "l1", "e1", case_cite(world, EMAIL, EMAIL_SENTENCE, EMAIL_QUOTE), "证明乙方自认无法按期交付货物"
    )
    l2 = link(
        "l2", "e2", case_cite(world, CONTRACT, CONTRACT_ART1, CONTRACT_ART1_QUOTE), "证明双方订立了买卖合同"
    )
    return l1, l2


def outline(
    world: World,
    elements: tuple[Element, ...],
    links: tuple[EvidenceLink, ...] = (),
    *,
    validate: bool = True,
) -> EvidenceOutline:
    """Build an outline; elements without a supporting link get a gap so the contract is satisfied.

    With `validate=False` the outline is built without contract validation (bypass simulation).
    """
    supported = {lk.element_id for lk in links}
    gaps = tuple(
        Gap(element_id=e.element_id, kind=GapKind.NO_EVIDENCE, description="SYNTHETIC gap")
        for e in elements
        if e.element_id not in supported
    )
    fields: dict[str, object] = {
        "query": world.query,
        "cause_of_action": "SYNTHETIC 买卖合同违约",
        "elements": elements,
        "links": links,
        "gaps": gaps,
        "abstained": False,
        "abstain_reason": None,
        "traces": (TRACE,),
    }
    if validate:
        return EvidenceOutline.model_validate(fields)
    return EvidenceOutline.model_construct(**fields)  # type: ignore[arg-type]


def good_outline(world: World) -> EvidenceOutline:
    return outline(world, good_elements(world), good_links(world))
