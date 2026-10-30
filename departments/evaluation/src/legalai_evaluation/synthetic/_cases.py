"""Eleven fictional `ZZ` criminal cases with expected evidence outlines; eight are financial offences.

Everything here is invented: people, companies, places, case files and the law they cite.

Modelling rules (ADR-0006):
- `as_of` is the date of the alleged conduct (one reference date per outline, §6.2). The fictional law says the
  provisions in force at the time of the conduct apply (ZZ Penal Code Article 1, ZZ刑事特别条例第一条), and every
  case's dates fall inside one version window, except ZZ-CRIM-010, which is an expected abstention.
- Defences are `CONTRADICTS` links on the offence element they would negate, never elements of their own (§4.1).
  Link purposes and gap descriptions state facts only, never the legal rule of a defence (§4.3).
- `burden_on` stays `None`: no cited offence provision states the burden for its own element (§3.2).
- `party_role` is PROSECUTION for prosecution-side outlines and DEFENDANT for defence-side outlines (§2.1).
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
from legalai_evaluation.synthetic._authoring import CaseFile, LawDoc, make_case_file
from legalai_evaluation.synthetic._law import PENAL_CODE, SPECIAL_REGULATION, LawLibrary

DATASET_VERSION = "1.0.0"
SUPPORTS = EvidenceRelation.SUPPORTS
CONTRADICTS = EvidenceRelation.CONTRADICTS
PROSECUTION = PartyRole.PROSECUTION
DEFENDANT = PartyRole.DEFENDANT
FIN = CaseTag.FINANCIAL_OFFENCE


@dataclass(frozen=True)
class BuiltCase:
    case: EvalCase
    files: tuple[CaseFile, ...]


def _case_id(number: int) -> str:
    return f"zz-crim-case-{number:03d}"


def _query(
    number: int,
    text: str,
    as_of: date,
    response_language: str,
    role: PartyRole,
    case_number: int | None = None,
) -> LegalQuery:
    return LegalQuery(
        query_id=f"zz-crim-{number:03d}-q",
        text=text,
        jurisdiction="ZZ",
        as_of=as_of,
        response_language=response_language,
        task_type=TaskType.EVIDENCE_OUTLINE,
        case_id=_case_id(case_number or number),
        party_role=role,
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
    charge: str,
    elements: Sequence[Element],
    links: Sequence[EvidenceLink],
    gaps: Sequence[Gap] = (),
) -> EvidenceOutline:
    cited = [c for e in elements for c in e.legal_basis] + [link.citation for link in links]
    return EvidenceOutline(
        query=query,
        cause_of_action=charge,
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
        case_id=_case_id(number),
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
        "Prepare an evidence outline for the charge of payment card fraud under Article 24 of the ZZ Penal Code "
        "against Owen Price, who is alleged to have used Lena Hart's bank card at Harbour Electronics on "
        "2 November 2023.",
        date(2023, 11, 2),
        "en",
        PROSECUTION,
    )
    indictment = _file(
        1,
        "indictment",
        "Indictment ZZ-PP-2023-1102 (SYNTHETIC)",
        "en",
        [
            "INDICTMENT ZZ-PP-2023-1102 (SYNTHETIC)",
            "The ZZ Public Prosecutor charges Owen Price with payment card fraud contrary to Article 24 of the "
            "ZZ Penal Code.",
        ],
    )
    bank = _file(
        1,
        "card-transactions",
        "Card transaction record, ZZ Commerce Bank (SYNTHETIC)",
        "en",
        [
            "CARD TRANSACTION RECORD, ZZ COMMERCE BANK (SYNTHETIC)",
            "Card ending 4417, issued to Lena Hart.",
            "2 November 2023 14:20, Harbour Electronics, 1,880 ZZ crowns, chip and PIN.",
        ],
    )
    holder = _file(
        1,
        "cardholder-hart",
        "Statement of Lena Hart (SYNTHETIC)",
        "en",
        [
            "Statement of Lena Hart (SYNTHETIC)",
            "I lost my wallet with my bank card on 1 November 2023.",
            "I did not allow anyone to use my card and I did not make the purchase at Harbour Electronics.",
        ],
    )
    cctv = _file(
        1,
        "cctv-record",
        "CCTV inspection record, Harbour Electronics (SYNTHETIC)",
        "en",
        [
            "CCTV inspection record, Harbour Electronics, prepared by Officer N. Reed (SYNTHETIC)",
            "At 14:20 on 2 November 2023 the man at the till, identified as Owen Price, pays with a card and "
            "enters a PIN.",
        ],
    )
    statement = _file(
        1,
        "defendant-statement",
        "Statement of Owen Price (SYNTHETIC)",
        "en",
        [
            "Statement of the defendant Owen Price, 4 November 2023 (SYNTHETIC)",
            "I found a wallet in the street and used the card inside it to buy a laptop.",
        ],
    )
    a24 = "Article 24"
    expected = _outline(
        q,
        "Payment card fraud (ZZ Penal Code Article 24)",
        [
            _el("E1", "The defendant used a payment card issued to another.", pc.cite(a24, "uses a payment card issued to another")),
            _el("E2", "The use was without the cardholder's authorisation.", pc.cite(a24, "without that person's authorisation")),
            _el(
                "E3",
                "The defendant obtained money or goods worth 1,000 ZZ crowns or more.",
                pc.cite(a24, "to obtain money or goods worth 1,000 ZZ crowns or more"),
            ),
        ],
        [
            _ln("L1", "E1", bank.cite("Card ending 4417, issued to Lena Hart."), SUPPORTS, "The card was issued to Lena Hart."),
            _ln(
                "L2",
                "E1",
                cctv.cite("the man at the till, identified as Owen Price, pays with a card"),
                SUPPORTS,
                "Identifies the defendant as the person paying with the card.",
            ),
            _ln(
                "L3",
                "E1",
                statement.cite("used the card inside it to buy a laptop"),
                SUPPORTS,
                "The defendant says he used a found card to buy a laptop.",
            ),
            _ln("L4", "E2", holder.cite("I did not allow anyone to use my card"), SUPPORTS, "The cardholder allowed no one to use the card."),
            _ln("L5", "E3", bank.cite("1,880 ZZ crowns"), SUPPORTS, "The purchase was for 1,880 ZZ crowns."),
        ],
    )
    return _case(1, "Use of a found bank card (SYNTHETIC)", q, "en", expected, [indictment, bank, holder, cctv, statement], [FIN])


def _case_002(law: LawLibrary) -> BuiltCase:
    pc = law.get(PENAL_CODE, "2022")
    q = _query(
        2,
        "We act for the defendant Ash Morrow, charged with intentional injury under Article 22 of the ZZ Penal "
        "Code for an incident outside the Lantern Bar on 19 August 2023. He says he acted in self-defence. "
        "Prepare an evidence outline of the prosecution's case showing which evidence supports and which "
        "contradicts each element, and any gaps.",
        date(2023, 8, 19),
        "en",
        DEFENDANT,
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
            _el("E4", "The defendant caused the injury unlawfully.", pc.cite(a22, "unlawfully")),
        ],
        [
            _ln("L1", "E1", complainant.cite("Ash Morrow punched me in the face."), SUPPORTS, "The complainant says the defendant punched him."),
            _ln("L2", "E1", forensic.cite("Bram Holt has a fractured nasal bone."), SUPPORTS, "The complainant has a fractured nasal bone."),
            _ln("L3", "E2", forensic.cite("Classification: moderate injury."), SUPPORTS, "The examiner classified the injury as moderate."),
            _ln("L4", "E3", statement.cite("so I punched him once"), SUPPORTS, "The defendant says he punched deliberately."),
            _ln(
                "L5",
                "E4",
                complainant.cite("after I had already turned to walk away"),
                SUPPORTS,
                "The complainant says he was walking away when struck.",
            ),
            _ln(
                "L6",
                "E4",
                eyewitness.cite("I saw Bram Holt swing a glass bottle at Ash Morrow's head before Ash hit him once."),
                CONTRADICTS,
                "An independent witness saw the complainant swing a bottle at the defendant before the blow.",
            ),
            _ln(
                "L7",
                "E4",
                scene.cite("Fingerprints on the bottle neck match Bram Holt."),
                CONTRADICTS,
                "The complainant's fingerprints are on the bottle found at the scene.",
            ),
            _ln(
                "L8",
                "E4",
                statement.cite("Bram came at me with a bottle"),
                CONTRADICTS,
                "The defendant says the complainant came at him with a bottle.",
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
        notes="Non-financial control case. The self-defence evidence is modelled as contradicting links on the "
        "unlawfulness element (ADR-0006 §4.1); E4 still has a supporting link, so it carries no gap.",
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
        DEFENDANT,
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
            _ln("L1", "E1", victim.cite("Milo Thorne told me the camera was new and genuine."), SUPPORTS, "What the defendant told the victim."),
            _ln("L2", "E1", messages.cite("Brand new, genuine, still sealed."), SUPPORTS, "The defendant's written description of the camera."),
            _ln(
                "L3",
                "E1",
                inspection.cite("is a non-working replica, not a genuine product"),
                SUPPORTS,
                "The camera is a non-working replica.",
            ),
            _ln(
                "L4",
                "E2",
                victim.cite("Because I believed him, I handed him the money in cash on 1 June 2021."),
                SUPPORTS,
                "The victim paid in cash because she believed the description.",
            ),
        ],
        [
            Gap(
                element_id="E3",
                kind=GapKind.NO_EVIDENCE,
                description="No receipt, bank record, valuation or statement in the case file states the amount "
                "handed over.",
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
        [FIN, CaseTag.MISSING_EVIDENCE, CaseTag.SUPERSEDED_VERSION_IN_FORCE],
    )


def _case_004(law: LawLibrary) -> BuiltCase:
    reg = law.get(SPECIAL_REGULATION, "2023")
    q = _query(
        4,
        "请为林某涉嫌醉酒驾驶罪一案整理证据提纲，列明犯罪构成要件、对应证据和证据缺口。案发时间为2024年2月10日。",
        date(2024, 2, 10),
        "zh",
        PROSECUTION,
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
            _el("E2", "被告人血液酒精含量达到每百毫升一百毫克以上。", reg.cite(a5, "血液酒精含量达到每百毫升一百毫克以上")),
        ],
        [
            _ln(
                "L1",
                "E1",
                police.cite("执勤民警在滨河路拦停车牌号ZZ-A1234的小型轿车，驾驶人为林某"),
                SUPPORTS,
                "民警在滨河路拦停由林某驾驶的小型轿车。",
            ),
            _ln("L2", "E1", witness.cite("之后自己开车走了"), SUPPORTS, "林某饮酒后自行开车离开。"),
            _ln("L3", "E2", blood.cite("林某血液中乙醇含量为每百毫升一百五十六毫克。"), SUPPORTS, "林某血液乙醇含量为每百毫升一百五十六毫克。"),
            _ln(
                "L4",
                "E2",
                blood.cite("鉴定人：赵某；鉴定方法：气相色谱法；鉴定日期：2024年2月11日。"),
                SUPPORTS,
                "鉴定意见书载明了鉴定人、鉴定方法和鉴定日期。",
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
        notes="Non-financial control case.",
    )


def _case_005(law: LawLibrary) -> BuiltCase:
    reg = law.get(SPECIAL_REGULATION, "2023")
    q = _query(
        5,
        "请为吴某涉嫌职务侵占罪一案整理证据提纲。吴某系星河物流有限公司出纳，涉嫌于2023年9月30日将公司款项八千ZZ元"
        "转入本人账户。",
        date(2023, 9, 30),
        "zh",
        PROSECUTION,
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
            _ln("L1", "E1", contract.cite("甲方：星河物流有限公司；乙方：吴某。"), SUPPORTS, "吴某与星河物流有限公司订有劳动合同。"),
            _ln(
                "L2",
                "E2",
                contract.cite("乙方担任出纳岗位，负责保管公司现金和办理银行转账。"),
                SUPPORTS,
                "吴某任出纳，负责保管现金和办理转账。",
            ),
            _ln(
                "L3",
                "E3",
                audit.cite("公司账户向吴某个人账户转账八千ZZ元，无任何业务凭证"),
                SUPPORTS,
                "款项无业务凭证转入吴某个人账户。",
            ),
            _ln("L4", "E3", audit.cite("截至审计日，该笔款项未退回公司。"), SUPPORTS, "款项至审计日未退回。"),
            _ln("L5", "E3", witness.cite("公司从未批准向吴某个人账户支付这笔款项。"), SUPPORTS, "公司未批准该笔支付。"),
            _ln("L6", "E3", statement.cite("这笔钱是公司欠我的加班费"), CONTRADICTS, "吴某称该款项是公司欠付的加班费。"),
            _ln("L7", "E4", audit.cite("八千ZZ元"), SUPPORTS, "转账数额为八千ZZ元。"),
        ],
    )
    return _case(
        5,
        "出纳职务侵占（SYNTHETIC）",
        q,
        "zh",
        expected,
        [indictment, contract, audit, witness, statement],
        [FIN],
    )


def _fundraising_files() -> list[CaseFile]:
    """Case files of the 金穗 scheme (case 6), shared by the outlines for two defendant groups."""
    n = 6
    return [
        _file(
            n,
            "indictment",
            "起诉书 ZZ检诉〔2021〕73号（SYNTHETIC）",
            "zh",
            [
                "ZZ检察署起诉书 ZZ检诉〔2021〕73号（SYNTHETIC）",
                "被告人冯某、何某以金穗投资管理有限公司名义，未经批准向社会公众募集资金，均以集资诈骗罪提起公诉。",
            ],
        ),
        _file(
            n,
            "regulator-letter",
            "ZZ金融监管局复函（SYNTHETIC）",
            "zh",
            ["ZZ金融监管局复函（SYNTHETIC）", "经查，金穗投资管理有限公司从未取得吸收公众资金的许可或批准。"],
        ),
        _file(
            n,
            "promotion-record",
            "宣传材料提取笔录（SYNTHETIC）",
            "zh",
            [
                "宣传材料提取笔录（SYNTHETIC）",
                "金穗投资管理有限公司在小区公告栏、短视频平台和推介会上发布“金穗农业合作项目”广告。",
                "广告称：投资满一年保本保息，年化收益百分之十八，到期由公司回购。",
            ],
        ),
        _file(
            n,
            "investor-testimony",
            "投资人证言汇总（SYNTHETIC）",
            "zh",
            [
                "投资人证言汇总（SYNTHETIC）",
                "共询问投资人四十二名，均系通过广告或亲友转告得知项目，与公司此前并无联系。",
                "投资人卫某称：业务员告诉我到期公司按合同回购，保证拿回本金和收益。",
            ],
        ),
        _file(
            n,
            "buyback-agreement",
            "回购协议（样本）（SYNTHETIC）",
            "zh",
            [
                "回购协议（样本）（SYNTHETIC）",
                "甲方金穗投资管理有限公司承诺于投资期满时按本金加百分之十八收益回购乙方份额。",
            ],
        ),
        _file(
            n,
            "fund-flow-audit",
            "资金流向审计报告（SYNTHETIC）",
            "zh",
            [
                "资金流向审计报告（SYNTHETIC）",
                "共吸收资金一千二百万ZZ元，投入农业项目的不足百分之五。",
                "约七百万ZZ元经多个账户转入冯某个人账户，用于购买房产、车辆及偿还其个人债务。",
            ],
            ["何某个人账户仅收到按其销售额百分之三计算的提成款。"],
        ),
        _file(
            n,
            "spending-record",
            "冯某个人消费记录调取笔录（SYNTHETIC）",
            "zh",
            ["冯某个人消费记录调取笔录（SYNTHETIC）", "2020年5月，冯某以个人名义购买别墅一套，付款来源为公司募集资金。"],
        ),
        _file(
            n,
            "accountant-testimony",
            "证人蒋某证言（SYNTHETIC）",
            "zh",
            ["证人蒋某（公司会计）证言（SYNTHETIC）", "公司账户的资金调度只由冯某决定，何某无权过问。"],
        ),
        _file(
            n,
            "he-statement",
            "被告人何某供述（SYNTHETIC）",
            "zh",
            [
                "被告人何某供述（SYNTHETIC）",
                "我只负责按公司给的材料对外宣传，不知道资金被冯某挪作他用，我以为钱都投到了农业项目。",
            ],
        ),
    ]


def _fundraising_common(
    reg: LawDoc, files: dict[str, CaseFile]
) -> tuple[list[Element], list[EvidenceLink]]:
    """Elements E1-E4 (第九条 conduct) and their links, identical for both defendant groups."""
    a9 = "第九条"
    elements = [
        _el("E1", "未经金融监管部门批准吸收资金（非法性）。", reg.cite(a9, "未经金融监管部门批准")),
        _el("E2", "通过公开宣传吸收资金（公开性）。", reg.cite(a9, "通过公开宣传")),
        _el("E3", "承诺在一定期限内还本付息或者给付回报（利诱性）。", reg.cite(a9, "承诺在一定期限内还本付息或者给付回报")),
        _el("E4", "向社会不特定对象吸收资金（社会性）。", reg.cite(a9, "向社会不特定对象吸收资金")),
    ]
    links = [
        _ln(
            "L1",
            "E1",
            files["regulator-letter"].cite("金穗投资管理有限公司从未取得吸收公众资金的许可或批准"),
            SUPPORTS,
            "监管部门确认公司未取得批准。",
        ),
        _ln(
            "L2",
            "E2",
            files["promotion-record"].cite("在小区公告栏、短视频平台和推介会上发布“金穗农业合作项目”广告"),
            SUPPORTS,
            "公司通过公告栏、短视频和推介会发布广告。",
        ),
        _ln(
            "L3",
            "E3",
            files["promotion-record"].cite("投资满一年保本保息，年化收益百分之十八，到期由公司回购"),
            SUPPORTS,
            "广告承诺保本保息和百分之十八年化收益。",
        ),
        _ln(
            "L4",
            "E3",
            files["buyback-agreement"].cite("承诺于投资期满时按本金加百分之十八收益回购乙方份额"),
            SUPPORTS,
            "回购协议约定期满按本金加收益回购。",
        ),
        _ln(
            "L5",
            "E3",
            files["investor-testimony"].cite("业务员告诉我到期公司按合同回购，保证拿回本金和收益"),
            SUPPORTS,
            "业务员向投资人保证回购和收益。",
        ),
        _ln(
            "L6",
            "E4",
            files["investor-testimony"].cite("均系通过广告或亲友转告得知项目，与公司此前并无联系"),
            SUPPORTS,
            "四十二名投资人经广告或转告得知项目，与公司此前无联系。",
        ),
    ]
    return elements, links


def _case_006(law: LawLibrary) -> BuiltCase:
    reg = law.get(SPECIAL_REGULATION, "2016")
    files = _fundraising_files()
    by_slug = {f.document.doc_id.removeprefix("zz-crim-006-"): f for f in files}
    q = _query(
        6,
        "请为冯某涉嫌集资诈骗罪一案整理证据提纲。冯某系金穗投资管理有限公司实际控制人，2019年3月至2021年6月以"
        "“金穗农业合作项目”名义向社会公众募集资金。",
        date(2021, 6, 30),
        "zh",
        PROSECUTION,
    )
    elements, links = _fundraising_common(reg, by_slug)
    elements.append(_el("E5", "冯某具有非法占有募集资金的目的。", reg.cite("第十条", "以非法占有为目的")))
    audit = by_slug["fund-flow-audit"]
    links += [
        _ln("L7", "E5", audit.cite("投入农业项目的不足百分之五"), SUPPORTS, "投入宣传项目的资金不足百分之五。"),
        _ln(
            "L8",
            "E5",
            audit.cite("约七百万ZZ元经多个账户转入冯某个人账户，用于购买房产、车辆及偿还其个人债务。"),
            SUPPORTS,
            "约七百万ZZ元转入冯某个人账户并用于个人消费和还债。",
        ),
        _ln(
            "L9",
            "E5",
            by_slug["spending-record"].cite("冯某以个人名义购买别墅一套，付款来源为公司募集资金"),
            SUPPORTS,
            "冯某用募集资金以个人名义购买别墅。",
        ),
        _ln(
            "L10",
            "E5",
            by_slug["accountant-testimony"].cite("公司账户的资金调度只由冯某决定"),
            SUPPORTS,
            "资金调度由冯某一人决定。",
        ),
    ]
    expected = _outline(q, "集资诈骗罪（《ZZ刑事特别条例（SYNTHETIC）》第十条）", elements, links)
    return _case(
        6,
        "金穗农业合作项目集资案：实际控制人冯某（SYNTHETIC）",
        q,
        "zh",
        expected,
        files,
        [FIN],
        notes="Conduct 2019-03 to 2021-06 lies wholly inside the 2016 version window of the regulation; as_of is "
        "the last day of the conduct.",
    )


def _case_007(law: LawLibrary) -> BuiltCase:
    reg = law.get(SPECIAL_REGULATION, "2016")
    files = _fundraising_files()
    by_slug = {f.document.doc_id.removeprefix("zz-crim-006-"): f for f in files}
    q = _query(
        7,
        "我们担任何某的辩护人。何某系金穗投资管理有限公司销售经理，与冯某一同被指控集资诈骗罪（行为期间2019年3月至"
        "2021年6月）。请整理控方对何某的证据提纲，并指出证据缺口。",
        date(2021, 6, 30),
        "zh",
        DEFENDANT,
        case_number=6,
    )
    elements, links = _fundraising_common(reg, by_slug)
    elements.append(_el("E5", "何某具有非法占有募集资金的目的。", reg.cite("第十条", "以非法占有为目的")))
    links += [
        _ln(
            "L7",
            "E5",
            by_slug["fund-flow-audit"].cite("何某个人账户仅收到按其销售额百分之三计算的提成款。"),
            CONTRADICTS,
            "何某个人账户只收到销售提成。",
        ),
        _ln(
            "L8",
            "E5",
            by_slug["accountant-testimony"].cite("何某无权过问"),
            CONTRADICTS,
            "何某无权过问公司资金调度。",
        ),
        _ln(
            "L9",
            "E5",
            by_slug["he-statement"].cite("不知道资金被冯某挪作他用，我以为钱都投到了农业项目"),
            CONTRADICTS,
            "何某称不知道资金被挪用。",
        ),
    ]
    gaps = [
        Gap(
            element_id="E5",
            kind=GapKind.ONLY_CONTRADICTING,
            description="卷宗中没有证据显示何某占有或支配募集资金；在案证据显示其只收到销售提成、无权调度资金，"
            "且称不知道资金去向。",
        )
    ]
    expected = _outline(q, "集资诈骗罪（《ZZ刑事特别条例（SYNTHETIC）》第十条）", elements, links, gaps)
    return _case(
        7,
        "金穗农业合作项目集资案：销售经理何某（SYNTHETIC）",
        q,
        "zh",
        expected,
        [],
        [FIN, CaseTag.MISSING_EVIDENCE],
        notes="Shares the case files of ZZ-CRIM-006 (case_id zz-crim-case-006). Same conduct elements; the intent "
        "element has only contradicting evidence for this defendant group.",
    )


def _case_008(law: LawLibrary) -> BuiltCase:
    pc = law.get(PENAL_CODE, "2022")
    q = _query(
        8,
        "请为Quinn Ashby涉嫌洗钱（ZZ Penal Code第25条）一案整理证据提纲。其涉嫌于2024年1月15日将Rhys Gale诈骗所得资金"
        "转入其开设的多个账户并兑换为加密资产。",
        date(2024, 1, 15),
        "zh",
        PROSECUTION,
    )
    indictment = _file(
        8,
        "indictment",
        "Indictment ZZ-PP-2024-0115 (SYNTHETIC)",
        "en",
        [
            "INDICTMENT ZZ-PP-2024-0115 (SYNTHETIC)",
            "The ZZ Public Prosecutor charges Quinn Ashby with money laundering contrary to Article 25 of the "
            "ZZ Penal Code.",
        ],
    )
    judgment = _file(
        8,
        "predicate-judgment",
        "Judgment ZZ-DC-2023-310 against Rhys Gale (SYNTHETIC)",
        "en",
        [
            "JUDGMENT ZZ-DC-2023-310 (SYNTHETIC)",
            "Rhys Gale is convicted of fraud for obtaining 60,000 ZZ crowns from investors between March and "
            "June 2023.",
        ],
    )
    flows = _file(
        8,
        "fund-flow-analysis",
        "Fund flow analysis report (SYNTHETIC)",
        "en",
        [
            "FUND FLOW ANALYSIS REPORT (SYNTHETIC)",
            "On 15 January 2024, 58,000 ZZ crowns from an account controlled by Rhys Gale were paid into three "
            "accounts opened by Quinn Ashby.",
            "Within two days Quinn Ashby converted the funds into crypto-assets and sent them to a wallet that "
            "Rhys Gale controls.",
        ],
    )
    messages = _file(
        8,
        "message-extraction",
        "Message extraction record (SYNTHETIC)",
        "en",
        [
            "MESSAGE EXTRACTION RECORD, phone of Quinn Ashby (SYNTHETIC)",
            "Message from Rhys Gale to Quinn Ashby, 14 January 2024: The investor money is hot, break it up and "
            "turn it into coins.",
            "Reply from Quinn Ashby: Understood, I will use the new accounts so nobody can trace it.",
        ],
    )
    statement = _file(
        8,
        "defendant-statement",
        "Statement of Quinn Ashby (SYNTHETIC)",
        "en",
        [
            "Statement of the defendant Quinn Ashby (SYNTHETIC)",
            "I thought the money came from Rhys's business and I only helped him move it.",
        ],
    )
    a25 = "Article 25"
    expected = _outline(
        q,
        "洗钱（money laundering, ZZ Penal Code Article 25）",
        [
            _el("E1", "涉案资金系犯罪所得。", pc.cite(a25, "funds are the proceeds of an offence")),
            _el("E2", "被告人明知资金系犯罪所得。", pc.cite(a25, "knowing that")),
            _el("E3", "被告人转移或转换了该资金。", pc.cite(a25, "transfers or converts the funds")),
            _el("E4", "目的在于掩饰、隐瞒资金来源。", pc.cite(a25, "in order to conceal or disguise their origin")),
        ],
        [
            _ln(
                "L1",
                "E1",
                judgment.cite("Rhys Gale is convicted of fraud for obtaining 60,000 ZZ crowns from investors"),
                SUPPORTS,
                "Rhys Gale已因诈骗投资人60,000 ZZ克朗被定罪。",
            ),
            _ln(
                "L2",
                "E1",
                flows.cite("58,000 ZZ crowns from an account controlled by Rhys Gale"),
                SUPPORTS,
                "资金来自Rhys Gale控制的账户。",
            ),
            _ln(
                "L3",
                "E2",
                messages.cite("The investor money is hot, break it up and turn it into coins."),
                SUPPORTS,
                "Rhys Gale告知被告人该资金是“投资人的钱”且“很烫手”。",
            ),
            _ln(
                "L4",
                "E2",
                statement.cite("I thought the money came from Rhys's business"),
                CONTRADICTS,
                "被告人称以为资金来自Rhys Gale的生意。",
            ),
            _ln(
                "L5",
                "E3",
                flows.cite("were paid into three accounts opened by Quinn Ashby"),
                SUPPORTS,
                "资金转入被告人开设的三个账户。",
            ),
            _ln(
                "L6",
                "E3",
                flows.cite("Quinn Ashby converted the funds into crypto-assets"),
                SUPPORTS,
                "被告人将资金兑换为加密资产。",
            ),
            _ln(
                "L7",
                "E4",
                messages.cite("I will use the new accounts so nobody can trace it."),
                SUPPORTS,
                "被告人称使用新账户使资金无法追踪。",
            ),
        ],
    )
    return _case(
        8,
        "Money laundering through crypto-assets, Chinese query on English sources (SYNTHETIC)",
        q,
        "zh",
        expected,
        [indictment, judgment, flows, messages, statement],
        [FIN, CaseTag.CROSS_LINGUAL],
    )


def _case_009(law: LawLibrary) -> BuiltCase:
    reg = law.get(SPECIAL_REGULATION, "2023")
    q = _query(
        9,
        "We act for Chu (褚某), charged under Article 9 (第九条) of the ZZ Special Criminal Regulation (SYNTHETIC) "
        "with illegally taking funds from the public through the Qinghe Mutual Aid Club (青禾互助会) from "
        "1 August to 31 December 2023. Prepare an evidence outline of the prosecution's case with any gaps.",
        date(2023, 12, 31),
        "en",
        DEFENDANT,
    )
    indictment = _file(
        9,
        "indictment",
        "起诉书 ZZ检诉〔2024〕12号（SYNTHETIC）",
        "zh",
        [
            "ZZ检察署起诉书 ZZ检诉〔2024〕12号（SYNTHETIC）",
            "被告人褚某以青禾互助会名义，未经批准向社会公众吸收资金，以非法吸收公众资金罪提起公诉。",
        ],
    )
    regulator = _file(
        9,
        "regulator-letter",
        "ZZ金融监管局复函（SYNTHETIC）",
        "zh",
        ["ZZ金融监管局复函（SYNTHETIC）", "青禾互助会及褚某均未取得吸收公众资金的批准。"],
    )
    chats = _file(
        9,
        "group-chat-record",
        "微信群聊天记录提取笔录（SYNTHETIC）",
        "zh",
        [
            "微信群聊天记录提取笔录（SYNTHETIC）",
            "褚某在三个公开微信群中发布入会邀请，群成员共一千余人，邀请可自由转发。",
            "邀请称：每月存入一千ZZ元，一年后返还本金并另付百分之十二的互助金。",
        ],
    )
    members = _file(
        9,
        "member-testimony",
        "会员证言汇总（SYNTHETIC）",
        "zh",
        ["会员证言汇总（SYNTHETIC）", "共询问会员六十名，大多通过群内转发得知互助会，与褚某素不相识。"],
    )
    ledger = _file(
        9,
        "club-ledger",
        "互助会账簿（SYNTHETIC）",
        "zh",
        ["互助会账簿（SYNTHETIC）", "2023年8月至12月共收取会员存款二百四十万ZZ元。"],
    )
    statement = _file(
        9,
        "defendant-statement",
        "被告人褚某供述（SYNTHETIC）",
        "zh",
        ["被告人褚某供述（SYNTHETIC）", "互助会只在亲戚朋友之间进行，没有对外公开。"],
    )
    a9 = "第九条"
    expected = _outline(
        q,
        "Illegally taking funds from the public (ZZ Special Criminal Regulation (SYNTHETIC) Article 9, "
        "非法吸收公众资金罪)",
        [
            _el("E1", "The funds were taken without approval of the financial regulator.", reg.cite(a9, "未经金融监管部门批准")),
            _el("E2", "The funds were solicited through public promotion.", reg.cite(a9, "通过公开宣传")),
            _el(
                "E3",
                "Repayment with interest or a return within a set period was promised.",
                reg.cite(a9, "承诺在一定期限内还本付息或者给付回报"),
            ),
            _el("E4", "The funds were taken from unspecified members of the public.", reg.cite(a9, "向社会不特定对象吸收资金")),
        ],
        [
            _ln("L1", "E1", regulator.cite("青禾互助会及褚某均未取得吸收公众资金的批准。"), SUPPORTS, "The regulator confirms no approval was given."),
            _ln(
                "L2",
                "E2",
                chats.cite("褚某在三个公开微信群中发布入会邀请，群成员共一千余人，邀请可自由转发。"),
                SUPPORTS,
                "Invitations were posted in three open chat groups of over a thousand members and could be forwarded.",
            ),
            _ln("L3", "E2", statement.cite("没有对外公开"), CONTRADICTS, "The defendant says the club was not made public."),
            _ln(
                "L4",
                "E3",
                chats.cite("一年后返还本金并另付百分之十二的互助金"),
                SUPPORTS,
                "The invitation promised principal back plus 12 percent after one year.",
            ),
            _ln(
                "L5",
                "E4",
                members.cite("大多通过群内转发得知互助会，与褚某素不相识"),
                SUPPORTS,
                "Most of the sixty members questioned learned of the club by forwarding and did not know the defendant.",
            ),
            _ln(
                "L6",
                "E4",
                statement.cite("互助会只在亲戚朋友之间进行"),
                CONTRADICTS,
                "The defendant says only relatives and friends took part.",
            ),
        ],
    )
    return _case(
        9,
        "Mutual-aid club fundraising, English query on Chinese sources (SYNTHETIC)",
        q,
        "en",
        expected,
        [indictment, regulator, chats, members, ledger, statement],
        [FIN, CaseTag.CROSS_LINGUAL],
        notes="Conduct 2023-08-01 to 2023-12-31 lies inside the 2023 version window of the regulation.",
    )


def _case_010(law: LawLibrary) -> BuiltCase:
    q = _query(
        10,
        "We act for Nina Shaw. She is charged with crypto-asset market manipulation under Article 30 of the ZZ "
        "Penal Code for placing and cancelling large sell orders for ZZcoin on the ZZX exchange on 1 May 2020. "
        "Prepare an evidence outline for the charge.",
        date(2020, 5, 1),
        "en",
        DEFENDANT,
    )
    indictment = _file(
        10,
        "indictment",
        "Indictment ZZ-PP-2020-0501 (SYNTHETIC)",
        "en",
        [
            "INDICTMENT ZZ-PP-2020-0501 (SYNTHETIC)",
            "The ZZ Public Prosecutor charges Nina Shaw with crypto-asset market manipulation contrary to "
            "Article 30 of the ZZ Penal Code.",
        ],
    )
    log = _file(
        10,
        "order-log",
        "ZZX exchange order log extract (SYNTHETIC)",
        "en",
        [
            "ZZX EXCHANGE ORDER LOG EXTRACT (SYNTHETIC)",
            "2020-05-01 21:14 to 21:40: account n.shaw placed 214 sell orders for ZZcoin and cancelled each of "
            "them within 3 seconds.",
        ],
    )
    expected = EvidenceOutline(
        query=q,
        cause_of_action="Crypto-asset market manipulation (ZZ Penal Code Article 30)",
        abstained=True,
        abstain_reason="No offence provision in force on 2020-05-01 covers the conduct: the ZZ Penal Code "
        "(SYNTHETIC) version in force on that date has no Article 30.",
        traces=(_trace([]),),
    )
    return _case(
        10,
        "Charge under a provision not in force at the time of the conduct (SYNTHETIC)",
        q,
        "en",
        expected,
        [indictment, log],
        [FIN, CaseTag.NO_APPLICABLE_LAW, CaseTag.SUPERSEDED_VERSION_IN_FORCE],
        notes="Expected abstention. Citing ZZ Penal Code 2022 Article 30 here is a not-in-force error.",
    )


def _case_011(law: LawLibrary) -> BuiltCase:
    reg = law.get(SPECIAL_REGULATION, "2016")
    q = _query(
        11,
        "我们是被告人陈某的辩护人。陈某被指控于2022年11月5日醉酒驾驶摩托车。请整理控方证据提纲，标明各要件的证据和缺口。",
        date(2022, 11, 5),
        "zh",
        DEFENDANT,
    )
    indictment = _file(
        11,
        "indictment",
        "起诉书 ZZ检诉〔2022〕88号（SYNTHETIC）",
        "zh",
        [
            "ZZ检察署起诉书 ZZ检诉〔2022〕88号（SYNTHETIC）",
            "被告人陈某于2022年11月5日23时许在ZZ市环城路上驾驶摩托车，被执勤交警查获。",
        ],
    )
    police = _file(
        11,
        "police-record",
        "交警现场执法记录（SYNTHETIC）",
        "zh",
        [
            "交警现场执法记录（SYNTHETIC）",
            "2022年11月5日23时10分，民警在环城路拦停一辆摩托车，驾驶人为陈某，其呼出气体有明显酒味。",
        ],
    )
    blood = _file(
        11,
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
            _ln("L1", "E1", police.cite("民警在环城路拦停一辆摩托车，驾驶人为陈某"), SUPPORTS, "民警在环城路拦停由陈某驾驶的摩托车。"),
            _ln("L2", "E2", blood.cite("陈某血液中乙醇含量为每百毫升一百五十毫克。"), SUPPORTS, "鉴定意见书所载陈某血液乙醇含量。"),
        ],
        [
            Gap(
                element_id="E2",
                kind=GapKind.INSUFFICIENT,
                description="唯一证明血液酒精含量的鉴定意见书未载明鉴定方法；卷宗中没有其他证明血液酒精含量的证据。",
            )
        ],
    )
    return _case(
        11,
        "醉驾案鉴定意见未载明鉴定方法（SYNTHETIC）",
        q,
        "zh",
        expected,
        [indictment, police, blood],
        [CaseTag.DEFECTIVE_EVIDENCE, CaseTag.SUPERSEDED_VERSION_IN_FORCE],
        notes="Non-financial control case. The defect matters under ZZ刑事证据规则（SYNTHETIC）第六条, which the "
        "outline cannot cite in a gap; a builder is expected to flag the element as insufficiently proven.",
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
    _case_011,
)


def build_cases(law: LawLibrary) -> list[BuiltCase]:
    return [builder(law) for builder in CASE_BUILDERS]
