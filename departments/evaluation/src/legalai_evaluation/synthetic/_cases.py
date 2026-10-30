"""Ten fictional `ZZ` criminal cases with expected evidence outlines.

Everything here is invented: people, companies, places, case files and the law they cite. `as_of` is the date of
the alleged conduct, because ZZ Penal Code (SYNTHETIC) Article 1 and ZZ刑事特别条例（SYNTHETIC）第一条 apply the
provisions in force at that time.

`party_role` is DEFENDANT throughout: the contracts have no prosecution role yet (REQ-PMO-0007). Prosecution-burdened
elements therefore leave `burden_on` empty rather than naming the wrong party. Cases tagged
PROSECUTION_ROLE_CANDIDATE have neutral queries and should switch to the prosecution role once it exists.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from legalai_contracts import (
    Citation,
    Element,
    EvidenceLink,
    EvidenceOutline,
    EvidenceRelation,
    Gap,
    GapKind,
    LegalQuery,
    ModelTrace,
    PartyRole,
    TaskType,
)

from legalai_evaluation.dataset import CaseTag, EvalCase
from legalai_evaluation.synthetic._authoring import CaseFile, make_case_file
from legalai_evaluation.synthetic._law import (
    EVIDENCE_RULES,
    PENAL_CODE,
    PROCEDURE_CODE,
    SPECIAL_REGULATION,
    LawLibrary,
)

DATASET_VERSION = "1.0.0"
SUPPORTS = EvidenceRelation.SUPPORTS
CONTRADICTS = EvidenceRelation.CONTRADICTS


@dataclass(frozen=True)
class BuiltCase:
    case: EvalCase
    files: tuple[CaseFile, ...]


def _query(number: int, text: str, as_of: date, response_language: str) -> LegalQuery:
    return LegalQuery(
        query_id=f"zz-crim-{number:03d}-q",
        text=text,
        jurisdiction="ZZ",
        as_of=as_of,
        response_language=response_language,
        task_type=TaskType.EVIDENCE_OUTLINE,
        case_id=f"zz-crim-case-{number:03d}",
        party_role=PartyRole.DEFENDANT,
    )


def _trace(citations: Sequence[Citation]) -> ModelTrace:
    """Authorship record for a hand-written expected outline. No model produced it."""
    versions = sorted({f"{c.span.doc_id}@{c.span.version_id}" for c in citations})
    return ModelTrace(
        model="human-authored:evaluation-synthetic",
        prompt_id="evaluation.synthetic.expected-outline",
        prompt_version=DATASET_VERSION,
        temperature=0,
        source_versions=tuple(versions),
    )


def _outline(
    query: LegalQuery,
    cause: str,
    elements: Sequence[Element],
    links: Sequence[EvidenceLink],
    gaps: Sequence[Gap] = (),
) -> EvidenceOutline:
    cited = [c for e in elements for c in e.legal_basis] + [link.citation for link in links]
    return EvidenceOutline(
        query=query,
        cause_of_action=cause,
        elements=tuple(elements),
        links=tuple(links),
        gaps=tuple(gaps),
        traces=(_trace(cited),),
    )


def _el(element_id: str, description: str, *basis: Citation) -> Element:
    return Element(element_id=element_id, description=description, legal_basis=basis, burden_on=None)


def _ln(
    link_id: str, element_id: str, citation: Citation, relation: EvidenceRelation, purpose: str
) -> EvidenceLink:
    return EvidenceLink(
        link_id=link_id, element_id=element_id, citation=citation, relation=relation, purpose=purpose
    )


def _file(number: int, slug: str, title: str, language: str, *pages: Sequence[str]) -> CaseFile:
    return make_case_file(
        case_id=f"zz-crim-case-{number:03d}",
        doc_id=f"zz-crim-{number:03d}-{slug}",
        title=title,
        language=language,
        pages=pages,
    )


def _case(
    number: int,
    title: str,
    query: LegalQuery,
    language: str,
    expected: EvidenceOutline,
    files: Sequence[CaseFile],
    tags: Sequence[CaseTag] = (),
    notes: str = "",
) -> BuiltCase:
    case = EvalCase(
        case_id=f"ZZ-CRIM-{number:03d}",
        title=title,
        query=query,
        query_language=language,
        expected=expected,
        tags=tuple(tags),
        notes=notes,
    )
    return BuiltCase(case=case, files=tuple(files))


def _case_001(law: LawLibrary) -> BuiltCase:
    pc = law.get(PENAL_CODE, "2022")
    q = _query(
        1,
        "Prepare an evidence outline for the charge of theft under Article 20 of the ZZ Penal Code against "
        "Rowan Vale, who is alleged to have taken a tablet computer from Quill Electronics on 12 April 2023.",
        date(2023, 4, 12),
        "en",
    )
    indictment = _file(
        1,
        "indictment",
        "Indictment ZZ-PP-2023-0412 (SYNTHETIC)",
        "en",
        [
            "INDICTMENT ZZ-PP-2023-0412 (SYNTHETIC)",
            "The ZZ Public Prosecutor charges Rowan Vale with theft contrary to Article 20 of the ZZ Penal Code.",
            "On 12 April 2023 the defendant took a tablet computer from the display of Quill Electronics and "
            "left without paying.",
        ],
    )
    manager = _file(
        1,
        "witness-quill",
        "Witness statement of Tessa Quill (SYNTHETIC)",
        "en",
        [
            "Witness statement of Tessa Quill, manager of Quill Electronics, 12 April 2023 (SYNTHETIC)",
            "The tablet on the display belongs to Quill Electronics.",
            "Nobody gave the man permission to take the tablet, and he did not pay for it.",
        ],
    )
    cctv = _file(
        1,
        "cctv-record",
        "CCTV inspection record (SYNTHETIC)",
        "en",
        [
            "CCTV inspection record, Quill Electronics, prepared by Officer N. Reed on 13 April 2023 (SYNTHETIC)",
            "At 15:02 a man matching the defendant removes a tablet from the display, puts it inside his "
            "jacket and walks past the tills.",
        ],
    )
    valuation = _file(
        1,
        "valuation",
        "Valuation record V-88 (SYNTHETIC)",
        "en",
        [
            "Valuation record V-88 (SYNTHETIC)",
            "The tablet computer taken from Quill Electronics had a retail value of 1,450 ZZ crowns on "
            "12 April 2023.",
        ],
    )
    statement = _file(
        1,
        "defendant-statement",
        "Statement of Rowan Vale (SYNTHETIC)",
        "en",
        [
            "Statement of the defendant Rowan Vale, 14 April 2023 (SYNTHETIC)",
            "I took the tablet because I wanted to keep it for myself.",
        ],
    )
    a20 = "Article 20"
    expected = _outline(
        q,
        "Theft (ZZ Penal Code Article 20)",
        [
            _el("E1", "The defendant took movable property of another.", pc.cite(a20, "takes movable property of another")),
            _el("E2", "The taking was without the owner's consent.", pc.cite(a20, "without consent")),
            _el("E3", "The property was worth 1,000 ZZ crowns or more.", pc.cite(a20, "worth 1,000 ZZ crowns or more")),
            _el(
                "E4",
                "The defendant acted intentionally and with the purpose of keeping the property.",
                pc.cite(a20, "intentionally"),
                pc.cite(a20, "with the purpose of keeping it"),
            ),
        ],
        [
            _ln("L1", "E1", cctv.cite("removes a tablet from the display"), SUPPORTS, "Shows the defendant taking the tablet."),
            _ln(
                "L2",
                "E1",
                manager.cite("The tablet on the display belongs to Quill Electronics."),
                SUPPORTS,
                "Shows the tablet belonged to another.",
            ),
            _ln(
                "L3",
                "E2",
                manager.cite("Nobody gave the man permission to take the tablet"),
                SUPPORTS,
                "Shows the owner did not consent.",
            ),
            _ln(
                "L4",
                "E3",
                valuation.cite("had a retail value of 1,450 ZZ crowns"),
                SUPPORTS,
                "Shows the value exceeds the threshold.",
            ),
            _ln(
                "L5",
                "E4",
                statement.cite("I took the tablet because I wanted to keep it for myself."),
                SUPPORTS,
                "Defendant's admission of intent to keep the tablet.",
            ),
            _ln(
                "L6",
                "E4",
                cctv.cite("puts it inside his jacket and walks past the tills"),
                SUPPORTS,
                "Conduct corroborating the intent to keep (confession not relied on alone).",
            ),
        ],
    )
    return _case(
        1,
        "Theft of a tablet computer (SYNTHETIC)",
        q,
        "en",
        expected,
        [indictment, manager, cctv, valuation, statement],
        [CaseTag.PROSECUTION_ROLE_CANDIDATE],
    )


def _case_002(law: LawLibrary) -> BuiltCase:
    pc = law.get(PENAL_CODE, "2022")
    cpc = law.get(PROCEDURE_CODE, "2015")
    q = _query(
        2,
        "We act for the defendant Ash Morrow, charged with intentional injury under Article 22 of the ZZ Penal "
        "Code for an incident outside the Lantern Bar on 19 August 2023. He says he acted in self-defence. "
        "Prepare an evidence outline of the prosecution's case showing which evidence supports and which "
        "contradicts each element, and any gaps.",
        date(2023, 8, 19),
        "en",
    )
    indictment = _file(
        2,
        "indictment",
        "Indictment ZZ-PP-2023-0819 (SYNTHETIC)",
        "en",
        [
            "INDICTMENT ZZ-PP-2023-0819 (SYNTHETIC)",
            "The ZZ Public Prosecutor charges Ash Morrow with intentional injury contrary to Article 22 of the "
            "ZZ Penal Code.",
        ],
    )
    forensic = _file(
        2,
        "forensic-report",
        "Forensic injury examination report (SYNTHETIC)",
        "en",
        [
            "FORENSIC INJURY EXAMINATION REPORT (SYNTHETIC)",
            "Examiner: Dr. P. Lund. Method: clinical examination and X-ray. Date of examination: 20 August 2023.",
        ],
        ["Bram Holt has a fractured nasal bone.", "Classification: moderate injury."],
    )
    complainant = _file(
        2,
        "complainant-holt",
        "Statement of the complainant Bram Holt (SYNTHETIC)",
        "en",
        [
            "Statement of Bram Holt (SYNTHETIC)",
            "We argued inside the bar.",
            "Outside, after I had already turned to walk away, Ash Morrow punched me in the face.",
        ],
    )
    eyewitness = _file(
        2,
        "witness-fenn",
        "Witness statement of Cora Fenn (SYNTHETIC)",
        "en",
        [
            "Witness statement of Cora Fenn (SYNTHETIC)",
            "I saw Bram Holt swing a glass bottle at Ash Morrow's head before Ash hit him once.",
        ],
    )
    scene = _file(
        2,
        "scene-inspection",
        "Scene inspection record (SYNTHETIC)",
        "en",
        [
            "Scene inspection record, Lantern Bar, 19 August 2023 (SYNTHETIC)",
            "A broken glass bottle was found on the pavement outside the Lantern Bar.",
            "Fingerprints on the bottle neck match Bram Holt.",
        ],
    )
    statement = _file(
        2,
        "defendant-statement",
        "Statement of Ash Morrow (SYNTHETIC)",
        "en",
        [
            "Statement of the defendant Ash Morrow (SYNTHETIC)",
            "Bram came at me with a bottle, so I punched him once to stop him.",
        ],
    )
    a22 = "Article 22"
    expected = _outline(
        q,
        "Intentional injury (ZZ Penal Code Article 22)",
        [
            _el("E1", "The defendant caused bodily injury to another person.", pc.cite(a22, "causes bodily injury to another")),
            _el(
                "E2",
                "A forensic examiner classified the injury as moderate or serious.",
                pc.cite(a22, "a forensic examiner classifies as moderate or serious"),
            ),
            _el("E3", "The defendant acted intentionally.", pc.cite(a22, "intentionally")),
            _el(
                "E4",
                "The conduct was not necessary self-defence against an imminent unlawful attack; once raised with "
                "supporting evidence, the prosecution must disprove the defence.",
                pc.cite("Article 4", "necessary to repel an imminent unlawful attack on the person or another"),
                cpc.cite("Article 12", "the prosecution must disprove the defence beyond reasonable doubt"),
            ),
        ],
        [
            _ln("L1", "E1", complainant.cite("Ash Morrow punched me in the face."), SUPPORTS, "Complainant identifies the blow."),
            _ln("L2", "E1", forensic.cite("Bram Holt has a fractured nasal bone."), SUPPORTS, "Shows the bodily injury."),
            _ln(
                "L3",
                "E2",
                forensic.cite("Classification: moderate injury."),
                SUPPORTS,
                "Forensic classification as moderate.",
            ),
            _ln("L4", "E3", statement.cite("so I punched him once"), SUPPORTS, "Defendant admits a deliberate punch."),
            _ln(
                "L5",
                "E4",
                complainant.cite("after I had already turned to walk away"),
                SUPPORTS,
                "Complainant says no attack was under way when he was struck.",
            ),
            _ln(
                "L6",
                "E4",
                eyewitness.cite("I saw Bram Holt swing a glass bottle at Ash Morrow's head before Ash hit him once."),
                CONTRADICTS,
                "Independent witness supports self-defence: an attack with a bottle preceded the blow.",
            ),
            _ln(
                "L7",
                "E4",
                scene.cite("Fingerprints on the bottle neck match Bram Holt."),
                CONTRADICTS,
                "Physical evidence that the complainant held the bottle.",
            ),
            _ln(
                "L8",
                "E4",
                statement.cite("Bram came at me with a bottle"),
                CONTRADICTS,
                "Defendant's account of an imminent attack.",
            ),
        ],
    )
    return _case(
        2,
        "Injury outside a bar with a self-defence claim (SYNTHETIC)",
        q,
        "en",
        expected,
        [indictment, forensic, complainant, eyewitness, scene, statement],
        [CaseTag.DEFENCE_WITH_CONTRADICTING_EVIDENCE],
        notes="Self-defence is modelled as an element (absence of justification) with supporting and "
        "contradicting links, pending the ADR on defences (REQ-PMO-0007).",
    )


def _case_003(law: LawLibrary) -> BuiltCase:
    pc = law.get(PENAL_CODE, "2012")
    q = _query(
        3,
        "We act for Milo Thorne, charged with fraud under Article 21 of the ZZ Penal Code. The prosecution says "
        "that on 1 June 2021 he sold Iris Penn a camera he described as new and genuine, which was a broken "
        "replica. Prepare an evidence outline of the prosecution's case and identify any gaps.",
        date(2021, 6, 1),
        "en",
    )
    indictment = _file(
        3,
        "indictment",
        "Indictment ZZ-PP-2021-0601 (SYNTHETIC)",
        "en",
        [
            "INDICTMENT ZZ-PP-2021-0601 (SYNTHETIC)",
            "The ZZ Public Prosecutor charges Milo Thorne with fraud contrary to Article 21 of the ZZ Penal Code.",
        ],
    )
    victim = _file(
        3,
        "victim-penn",
        "Statement of Iris Penn (SYNTHETIC)",
        "en",
        [
            "Statement of Iris Penn (SYNTHETIC)",
            "Milo Thorne told me the camera was new and genuine.",
            "Because I believed him, I handed him the money in cash on 1 June 2021.",
        ],
    )
    inspection = _file(
        3,
        "product-inspection",
        "Product inspection record (SYNTHETIC)",
        "en",
        [
            "Product inspection record (SYNTHETIC)",
            "The camera handed in by Iris Penn is a non-working replica, not a genuine product.",
        ],
    )
    messages = _file(
        3,
        "message-extraction",
        "Message extraction record (SYNTHETIC)",
        "en",
        [
            "Message extraction record, phone of Iris Penn (SYNTHETIC)",
            "Message from Milo Thorne to Iris Penn, 31 May 2021: Brand new, genuine, still sealed.",
        ],
    )
    a21 = "Article 21"
    expected = _outline(
        q,
        "Fraud (ZZ Penal Code Article 21)",
        [
            _el("E1", "The defendant deceived the victim.", pc.cite(a21, "by deceiving another")),
            _el(
                "E2",
                "The deception caused the victim to hand over property.",
                pc.cite(a21, "causes that person to hand over property"),
            ),
            _el(
                "E3",
                "The property obtained was worth 1,000 ZZ crowns or more.",
                pc.cite(a21, "obtains property worth 1,000 ZZ crowns or more"),
            ),
        ],
        [
            _ln("L1", "E1", victim.cite("Milo Thorne told me the camera was new and genuine."), SUPPORTS, "The representation made."),
            _ln("L2", "E1", messages.cite("Brand new, genuine, still sealed."), SUPPORTS, "Written representation."),
            _ln(
                "L3",
                "E1",
                inspection.cite("is a non-working replica, not a genuine product"),
                SUPPORTS,
                "Shows the representation was false.",
            ),
            _ln(
                "L4",
                "E2",
                victim.cite("Because I believed him, I handed him the money in cash on 1 June 2021."),
                SUPPORTS,
                "Reliance and handover of money.",
            ),
        ],
        [
            Gap(
                element_id="E3",
                kind=GapKind.NO_EVIDENCE,
                description="No receipt, bank record, valuation or statement in the case file states the "
                "amount handed over, so the 1,000 ZZ crowns threshold is unproven.",
            )
        ],
    )
    return _case(
        3,
        "Sale of a replica camera, amount unproven (SYNTHETIC)",
        q,
        "en",
        expected,
        [indictment, victim, inspection, messages],
        [CaseTag.MISSING_EVIDENCE, CaseTag.SUPERSEDED_VERSION_IN_FORCE],
    )


def _case_004(law: LawLibrary) -> BuiltCase:
    reg = law.get(SPECIAL_REGULATION, "2023")
    ev = law.get(EVIDENCE_RULES, "2019")
    q = _query(
        4,
        "请为林某涉嫌醉酒驾驶罪一案整理证据提纲，列明犯罪构成要件、对应证据和证据缺口。案发时间为2024年2月10日。",
        date(2024, 2, 10),
        "zh",
    )
    indictment = _file(
        4,
        "indictment",
        "起诉书 ZZ检诉〔2024〕21号（SYNTHETIC）",
        "zh",
        [
            "ZZ检察署起诉书 ZZ检诉〔2024〕21号（SYNTHETIC）",
            "被告人林某于2024年2月10日22时许，在ZZ市滨河路上驾驶小型轿车，被执勤交警查获。",
        ],
    )
    police = _file(
        4,
        "police-record",
        "交警现场执法记录（SYNTHETIC）",
        "zh",
        [
            "交警现场执法记录（SYNTHETIC）",
            "2024年2月10日22时05分，执勤民警在滨河路拦停车牌号ZZ-A1234的小型轿车，驾驶人为林某。",
        ],
    )
    blood = _file(
        4,
        "blood-test",
        "血液酒精检验鉴定意见书（SYNTHETIC）",
        "zh",
        [
            "血液酒精检验鉴定意见书（SYNTHETIC）",
            "鉴定人：赵某；鉴定方法：气相色谱法；鉴定日期：2024年2月11日。",
            "林某血液中乙醇含量为每百毫升一百五十六毫克。",
        ],
    )
    witness = _file(
        4,
        "witness-zhou",
        "证人周某证言（SYNTHETIC）",
        "zh",
        ["证人周某证言（SYNTHETIC）", "当晚我和林某一起吃饭，他喝了半斤白酒，之后自己开车走了。"],
    )
    a5 = "第五条"
    expected = _outline(
        q,
        "醉酒驾驶罪（《ZZ刑事特别条例（SYNTHETIC）》第五条）",
        [
            _el("E1", "被告人在道路上驾驶机动车。", reg.cite(a5, "在道路上驾驶机动车")),
            _el(
                "E2",
                "被告人血液酒精含量达到每百毫升一百毫克以上，且鉴定意见符合法定要件。",
                reg.cite(a5, "血液酒精含量达到每百毫升一百毫克以上"),
                ev.cite("第六条", "鉴定意见应当载明鉴定人、鉴定方法和鉴定日期"),
            ),
        ],
        [
            _ln(
                "L1",
                "E1",
                police.cite("执勤民警在滨河路拦停车牌号ZZ-A1234的小型轿车，驾驶人为林某"),
                SUPPORTS,
                "证明被告人在道路上驾驶机动车。",
            ),
            _ln("L2", "E1", witness.cite("之后自己开车走了"), SUPPORTS, "印证被告人饮酒后驾车。"),
            _ln("L3", "E2", blood.cite("林某血液中乙醇含量为每百毫升一百五十六毫克。"), SUPPORTS, "证明血液酒精含量超过标准。"),
            _ln(
                "L4",
                "E2",
                blood.cite("鉴定人：赵某；鉴定方法：气相色谱法；鉴定日期：2024年2月11日。"),
                SUPPORTS,
                "证明鉴定意见载明鉴定人、方法和日期。",
            ),
        ],
    )
    return _case(
        4,
        "醉酒驾驶（SYNTHETIC）",
        q,
        "zh",
        expected,
        [indictment, police, blood, witness],
        [CaseTag.PROSECUTION_ROLE_CANDIDATE],
    )


def _case_005(law: LawLibrary) -> BuiltCase:
    reg = law.get(SPECIAL_REGULATION, "2023")
    q = _query(
        5,
        "请为吴某涉嫌职务侵占罪一案整理证据提纲。吴某系星河物流有限公司出纳，涉嫌于2023年9月30日将公司款项八千ZZ元"
        "转入本人账户。",
        date(2023, 9, 30),
        "zh",
    )
    indictment = _file(
        5,
        "indictment",
        "起诉书 ZZ检诉〔2023〕57号（SYNTHETIC）",
        "zh",
        [
            "ZZ检察署起诉书 ZZ检诉〔2023〕57号（SYNTHETIC）",
            "被告人吴某系星河物流有限公司出纳，利用保管公司资金的职务便利，将公司款项转入本人账户。",
        ],
    )
    contract = _file(
        5,
        "employment-contract",
        "劳动合同（SYNTHETIC）",
        "zh",
        [
            "劳动合同（SYNTHETIC）",
            "甲方：星河物流有限公司；乙方：吴某。",
            "乙方担任出纳岗位，负责保管公司现金和办理银行转账。",
        ],
    )
    audit = _file(
        5,
        "audit-report",
        "专项审计报告（SYNTHETIC）",
        "zh",
        [
            "专项审计报告（SYNTHETIC）",
            "2023年9月30日，公司账户向吴某个人账户转账八千ZZ元，无任何业务凭证。",
            "截至审计日，该笔款项未退回公司。",
        ],
    )
    witness = _file(
        5,
        "witness-zheng",
        "证人郑某证言（SYNTHETIC）",
        "zh",
        ["证人郑某（财务主管）证言（SYNTHETIC）", "公司从未批准向吴某个人账户支付这笔款项。"],
    )
    statement = _file(
        5,
        "defendant-statement",
        "被告人吴某供述（SYNTHETIC）",
        "zh",
        ["被告人吴某供述（SYNTHETIC）", "这笔钱是公司欠我的加班费，我只是先拿回来。"],
    )
    a6 = "第六条"
    expected = _outline(
        q,
        "职务侵占罪（《ZZ刑事特别条例（SYNTHETIC）》第六条）",
        [
            _el("E1", "被告人系公司、企业的工作人员。", reg.cite(a6, "公司、企业的工作人员")),
            _el("E2", "被告人利用了职务上的便利。", reg.cite(a6, "利用职务上的便利")),
            _el("E3", "被告人将本单位财物非法占为己有。", reg.cite(a6, "将本单位财物非法占为己有")),
            _el("E4", "侵占数额在五千ZZ元以上。", reg.cite(a6, "数额在五千ZZ元以上")),
        ],
        [
            _ln("L1", "E1", contract.cite("甲方：星河物流有限公司；乙方：吴某。"), SUPPORTS, "证明被告人与公司存在劳动关系。"),
            _ln(
                "L2",
                "E2",
                contract.cite("乙方担任出纳岗位，负责保管公司现金和办理银行转账。"),
                SUPPORTS,
                "证明被告人职务上负责保管和转出资金。",
            ),
            _ln(
                "L3",
                "E3",
                audit.cite("公司账户向吴某个人账户转账八千ZZ元，无任何业务凭证"),
                SUPPORTS,
                "证明款项无依据转入被告人账户。",
            ),
            _ln("L4", "E3", audit.cite("截至审计日，该笔款项未退回公司。"), SUPPORTS, "证明款项未归还。"),
            _ln("L5", "E3", witness.cite("公司从未批准向吴某个人账户支付这笔款项。"), SUPPORTS, "证明支付未经公司批准。"),
            _ln(
                "L6",
                "E3",
                statement.cite("这笔钱是公司欠我的加班费"),
                CONTRADICTS,
                "被告人辩称系索取应得报酬，否认非法占有。",
            ),
            _ln("L7", "E4", audit.cite("八千ZZ元"), SUPPORTS, "证明数额为八千ZZ元。"),
        ],
    )
    return _case(
        5,
        "出纳职务侵占（SYNTHETIC）",
        q,
        "zh",
        expected,
        [indictment, contract, audit, witness, statement],
        [CaseTag.PROSECUTION_ROLE_CANDIDATE],
    )


def _case_006(law: LawLibrary) -> BuiltCase:
    reg = law.get(SPECIAL_REGULATION, "2016")
    q = _query(
        6,
        "我们担任冯某的辩护人。冯某被指控于2022年3月15日以威胁手段向何某索要三千ZZ元，构成敲诈勒索罪。"
        "请整理控方证据提纲，并指出证据缺口。",
        date(2022, 3, 15),
        "zh",
    )
    indictment = _file(
        6,
        "indictment",
        "起诉书 ZZ检诉〔2022〕19号（SYNTHETIC）",
        "zh",
        [
            "ZZ检察署起诉书 ZZ检诉〔2022〕19号（SYNTHETIC）",
            "被告人冯某于2022年3月15日以威胁手段，迫使被害人何某转账三千ZZ元。",
        ],
    )
    victim = _file(
        6,
        "victim-he",
        "被害人何某陈述（SYNTHETIC）",
        "zh",
        ["被害人何某陈述（SYNTHETIC）", "冯某让我给他三千元，我就通过手机银行转给了他。"],
    )
    bank = _file(
        6,
        "bank-record",
        "银行交易记录（SYNTHETIC）",
        "zh",
        ["银行交易记录（SYNTHETIC）", "2022年3月15日，何某账户向冯某账户转账三千ZZ元。"],
    )
    edata = _file(
        6,
        "edata-record",
        "电子数据检查笔录（SYNTHETIC）",
        "zh",
        [
            "电子数据检查笔录（SYNTHETIC）",
            "从何某手机中提取到冯某发送的短信一条：上次借你的三千元该还了，请转给我。",
            "未发现含有威胁内容的信息。",
        ],
    )
    a7 = "第七条"
    expected = _outline(
        q,
        "敲诈勒索罪（《ZZ刑事特别条例（SYNTHETIC）》第七条）",
        [
            _el("E1", "被告人使用了威胁手段。", reg.cite(a7, "以威胁手段")),
            _el("E2", "被告人迫使他人交付了财物。", reg.cite(a7, "迫使他人交付财物")),
            _el("E3", "数额在二千ZZ元以上。", reg.cite(a7, "数额在二千ZZ元以上")),
        ],
        [
            _ln(
                "L1",
                "E1",
                edata.cite("上次借你的三千元该还了，请转给我。"),
                CONTRADICTS,
                "短信内容为催还借款，不含威胁。",
            ),
            _ln("L2", "E1", edata.cite("未发现含有威胁内容的信息。"), CONTRADICTS, "电子数据检查未发现威胁信息。"),
            _ln("L3", "E2", victim.cite("我就通过手机银行转给了他"), SUPPORTS, "证明被害人交付了款项。"),
            _ln("L4", "E2", bank.cite("何某账户向冯某账户转账三千ZZ元"), SUPPORTS, "证明款项实际转入被告人账户。"),
            _ln("L5", "E3", bank.cite("三千ZZ元"), SUPPORTS, "证明数额为三千ZZ元。"),
        ],
        [
            Gap(
                element_id="E1",
                kind=GapKind.ONLY_CONTRADICTING,
                description="卷宗中没有证据证明存在威胁：被害人陈述未提及威胁，电子数据显示索要理由为还款。",
            )
        ],
    )
    return _case(
        6,
        "索要款项是否构成敲诈勒索（SYNTHETIC）",
        q,
        "zh",
        expected,
        [indictment, victim, bank, edata],
        [CaseTag.MISSING_EVIDENCE, CaseTag.SUPERSEDED_VERSION_IN_FORCE],
    )


def _case_007(law: LawLibrary) -> BuiltCase:
    pc = law.get(PENAL_CODE, "2022")
    q = _query(
        7,
        "请为Felix Crane涉嫌故意毁坏财物（ZZ Penal Code第23条）一案整理证据提纲。案发于2024年3月3日，"
        "其涉嫌用锤子砸坏邻居Gwen Odell的汽车。",
        date(2024, 3, 3),
        "zh",
    )
    indictment = _file(
        7,
        "indictment",
        "Indictment ZZ-PP-2024-0303 (SYNTHETIC)",
        "en",
        [
            "INDICTMENT ZZ-PP-2024-0303 (SYNTHETIC)",
            "The ZZ Public Prosecutor charges Felix Crane with criminal damage contrary to Article 23 of the ZZ "
            "Penal Code.",
        ],
    )
    neighbour = _file(
        7,
        "witness-odell",
        "Witness statement of Gwen Odell (SYNTHETIC)",
        "en",
        [
            "Witness statement of Gwen Odell (SYNTHETIC)",
            "I saw Felix Crane hit the windscreen and both side mirrors of my car with a hammer on 3 March 2024.",
            "He shouted that he would teach me a lesson for parking in front of his gate.",
        ],
    )
    repair = _file(
        7,
        "repair-valuation",
        "Repair estimate and valuation (SYNTHETIC)",
        "en",
        [
            "Repair estimate and valuation (SYNTHETIC)",
            "Repair of the windscreen and two side mirrors of Gwen Odell's car: 2,600 ZZ crowns.",
        ],
    )
    scene = _file(
        7,
        "scene-inspection",
        "Scene inspection record (SYNTHETIC)",
        "en",
        [
            "Scene inspection record, 3 March 2024 (SYNTHETIC)",
            "A hammer bearing the defendant's fingerprints was found in the defendant's garden.",
        ],
    )
    a23 = "Article 23"
    expected = _outline(
        q,
        "故意毁坏财物（criminal damage, ZZ Penal Code Article 23）",
        [
            _el("E1", "被告人毁坏或损坏了他人的财物。", pc.cite(a23, "destroys or damages property of another")),
            _el("E2", "造成的损失达到2,000 ZZ克朗以上。", pc.cite(a23, "causing loss of 2,000 ZZ crowns or more")),
            _el("E3", "被告人系故意实施。", pc.cite(a23, "intentionally")),
        ],
        [
            _ln(
                "L1",
                "E1",
                neighbour.cite("I saw Felix Crane hit the windscreen and both side mirrors of my car with a hammer"),
                SUPPORTS,
                "目击证人证明被告人砸坏汽车。",
            ),
            _ln(
                "L2",
                "E1",
                scene.cite("A hammer bearing the defendant's fingerprints was found in the defendant's garden."),
                SUPPORTS,
                "物证印证被告人使用锤子。",
            ),
            _ln("L3", "E2", repair.cite("2,600 ZZ crowns"), SUPPORTS, "证明损失为2,600 ZZ克朗。"),
            _ln(
                "L4",
                "E3",
                neighbour.cite("He shouted that he would teach me a lesson for parking in front of his gate."),
                SUPPORTS,
                "证明被告人有意报复，系故意。",
            ),
        ],
    )
    return _case(
        7,
        "Criminal damage to a car, Chinese query on English sources (SYNTHETIC)",
        q,
        "zh",
        expected,
        [indictment, neighbour, repair, scene],
        [CaseTag.CROSS_LINGUAL, CaseTag.PROSECUTION_ROLE_CANDIDATE],
    )


def _case_008(law: LawLibrary) -> BuiltCase:
    reg = law.get(SPECIAL_REGULATION, "2023")
    q = _query(
        8,
        "We act for Chu (褚某), charged under Article 8 (第八条) of the ZZ Special Criminal Regulation (SYNTHETIC) "
        "with forging the company seal of Yuanhang Trading Co (远航贸易有限公司) and using it to sign a contract on "
        "20 May 2024. Prepare an evidence outline of the prosecution's case with any gaps.",
        date(2024, 5, 20),
        "en",
    )
    indictment = _file(
        8,
        "indictment",
        "起诉书 ZZ检诉〔2024〕40号（SYNTHETIC）",
        "zh",
        [
            "ZZ检察署起诉书 ZZ检诉〔2024〕40号（SYNTHETIC）",
            "被告人褚某私刻远航贸易有限公司公章，并于2024年5月20日使用该公章与他人签订购销合同。",
        ],
    )
    seal_exam = _file(
        8,
        "seal-examination",
        "印章鉴定意见书（SYNTHETIC）",
        "zh",
        [
            "印章鉴定意见书（SYNTHETIC）",
            "鉴定人：孙某；鉴定方法：印文比对；鉴定日期：2024年6月3日。",
            "购销合同上的远航贸易有限公司印文与该公司备案印章印文不一致，系另行刻制。",
        ],
    )
    contract = _file(
        8,
        "sales-contract",
        "购销合同（SYNTHETIC）",
        "zh",
        ["购销合同（SYNTHETIC）", "卖方：远航贸易有限公司（盖章）；买方：东升建材有限公司。签订日期：2024年5月20日。"],
    )
    engraver = _file(
        8,
        "witness-li",
        "证人李某证言（SYNTHETIC）",
        "zh",
        [
            "证人刻章店店主李某证言（SYNTHETIC）",
            "2024年5月中旬，褚某拿着一张图样让我刻了一枚远航贸易有限公司的公章，没有出示任何授权文件。",
        ],
    )
    company = _file(
        8,
        "company-statement",
        "远航贸易有限公司情况说明（SYNTHETIC）",
        "zh",
        ["远航贸易有限公司情况说明（SYNTHETIC）", "本公司从未授权褚某刻制或使用本公司印章。"],
    )
    a8 = "第八条"
    expected = _outline(
        q,
        "Forging a company seal (ZZ Special Criminal Regulation (SYNTHETIC) Article 8, 伪造印章罪)",
        [
            _el("E1", "The defendant forged the seal of a company.", reg.cite(a8, "伪造公司、企业印章")),
            _el("E2", "The forged seal was used to sign a contract or issue a certificate.", reg.cite(a8, "用于签订合同或者出具证明")),
        ],
        [
            _ln(
                "L1",
                "E1",
                seal_exam.cite("系另行刻制"),
                SUPPORTS,
                "Forensic comparison: the seal impression is not the registered seal.",
            ),
            _ln(
                "L2",
                "E1",
                engraver.cite("褚某拿着一张图样让我刻了一枚远航贸易有限公司的公章"),
                SUPPORTS,
                "Engraver links the defendant to making the seal.",
            ),
            _ln("L3", "E1", company.cite("本公司从未授权褚某刻制或使用本公司印章。"), SUPPORTS, "The company never authorised it."),
            _ln(
                "L4",
                "E2",
                contract.cite("卖方：远航贸易有限公司（盖章）"),
                SUPPORTS,
                "The seal was applied to a sales contract.",
            ),
            _ln(
                "L5",
                "E2",
                seal_exam.cite("购销合同上的远航贸易有限公司印文与该公司备案印章印文不一致"),
                SUPPORTS,
                "The impression on the contract is the forged seal.",
            ),
        ],
    )
    return _case(
        8,
        "Forged company seal, English query on Chinese sources (SYNTHETIC)",
        q,
        "en",
        expected,
        [indictment, seal_exam, contract, engraver, company],
        [CaseTag.CROSS_LINGUAL],
    )


def _case_009(law: LawLibrary) -> BuiltCase:
    q = _query(
        9,
        "We act for Nina Shaw. She is charged with unauthorised access to a computer system under Article 30 of "
        "the ZZ Penal Code for logging in to her former employer's email server with her old password on "
        "1 May 2020. Prepare an evidence outline for the charge.",
        date(2020, 5, 1),
        "en",
    )
    indictment = _file(
        9,
        "indictment",
        "Indictment ZZ-PP-2020-0501 (SYNTHETIC)",
        "en",
        [
            "INDICTMENT ZZ-PP-2020-0501 (SYNTHETIC)",
            "The ZZ Public Prosecutor charges Nina Shaw with unauthorised access contrary to Article 30 of the "
            "ZZ Penal Code.",
            "On 1 May 2020 the defendant logged in to the email server of Orchid Media Ltd with a password "
            "issued to her during her former employment.",
        ],
    )
    log = _file(
        9,
        "access-log",
        "Server access log extract (SYNTHETIC)",
        "en",
        [
            "Server access log extract, Orchid Media Ltd (SYNTHETIC)",
            "2020-05-01 21:14 login to mail.orchid.example with account n.shaw from an external address.",
        ],
    )
    expected = EvidenceOutline(
        query=q,
        cause_of_action="Unauthorised access (ZZ Penal Code Article 30)",
        abstained=True,
        abstain_reason="No offence provision in force on 2020-05-01 covers the conduct: the version of the "
        "ZZ Penal Code (SYNTHETIC) in force on that date has no Article 30, and Article 1 requires a provision "
        "in force at the time of the conduct.",
        traces=(_trace([]),),
    )
    return _case(
        9,
        "Charge under a provision not yet in force (SYNTHETIC)",
        q,
        "en",
        expected,
        [indictment, log],
        [CaseTag.NO_APPLICABLE_LAW, CaseTag.SUPERSEDED_VERSION_IN_FORCE],
        notes="Expected abstention. Citing ZZ Penal Code 2022 Article 30 here is a not-in-force error.",
    )


def _case_010(law: LawLibrary) -> BuiltCase:
    reg = law.get(SPECIAL_REGULATION, "2016")
    q = _query(
        10,
        "我们是被告人陈某的辩护人。陈某被指控于2022年11月5日醉酒驾驶摩托车。请整理控方证据提纲，标明各要件的证据和缺口。",
        date(2022, 11, 5),
        "zh",
    )
    indictment = _file(
        10,
        "indictment",
        "起诉书 ZZ检诉〔2022〕88号（SYNTHETIC）",
        "zh",
        [
            "ZZ检察署起诉书 ZZ检诉〔2022〕88号（SYNTHETIC）",
            "被告人陈某于2022年11月5日23时许在ZZ市环城路上驾驶摩托车，被执勤交警查获。",
        ],
    )
    police = _file(
        10,
        "police-record",
        "交警现场执法记录（SYNTHETIC）",
        "zh",
        [
            "交警现场执法记录（SYNTHETIC）",
            "2022年11月5日23时10分，民警在环城路拦停一辆摩托车，驾驶人为陈某，其呼出气体有明显酒味。",
        ],
    )
    blood = _file(
        10,
        "blood-test",
        "血液酒精检验鉴定意见书（SYNTHETIC）",
        "zh",
        [
            "血液酒精检验鉴定意见书（SYNTHETIC）",
            "鉴定人：钱某；鉴定日期：2022年11月6日。",
            "陈某血液中乙醇含量为每百毫升一百五十毫克。",
        ],
    )
    a5 = "第五条"
    expected = _outline(
        q,
        "醉酒驾驶罪（《ZZ刑事特别条例（SYNTHETIC）》第五条）",
        [
            _el("E1", "被告人在道路上驾驶机动车。", reg.cite(a5, "在道路上驾驶机动车")),
            _el("E2", "被告人血液酒精含量达到每百毫升一百二十毫克以上。", reg.cite(a5, "血液酒精含量达到每百毫升一百二十毫克以上")),
        ],
        [
            _ln(
                "L1",
                "E1",
                police.cite("民警在环城路拦停一辆摩托车，驾驶人为陈某"),
                SUPPORTS,
                "证明被告人在道路上驾驶机动车。",
            ),
            _ln("L2", "E2", blood.cite("陈某血液中乙醇含量为每百毫升一百五十毫克。"), SUPPORTS, "鉴定意见所载血液酒精含量。"),
        ],
        [
            Gap(
                element_id="E2",
                kind=GapKind.INSUFFICIENT,
                description="鉴定意见书未载明鉴定方法，依《ZZ刑事证据规则（SYNTHETIC）》第六条不得作为定案根据，"
                "卷宗中也没有其他证明血液酒精含量的证据。",
            )
        ],
    )
    return _case(
        10,
        "醉驾案鉴定意见缺少鉴定方法（SYNTHETIC）",
        q,
        "zh",
        expected,
        [indictment, police, blood],
        [CaseTag.DEFECTIVE_EVIDENCE, CaseTag.SUPERSEDED_VERSION_IN_FORCE],
    )


CASE_BUILDERS = (
    _case_001,
    _case_002,
    _case_003,
    _case_004,
    _case_005,
    _case_006,
    _case_007,
    _case_008,
    _case_009,
    _case_010,
)


def build_cases(law: LawLibrary) -> list[BuiltCase]:
    return [builder(law) for builder in CASE_BUILDERS]
