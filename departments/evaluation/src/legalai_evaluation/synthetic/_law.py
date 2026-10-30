"""Fictional `ZZ` criminal law. Every text here is invented for testing and is not the law of any real place.

Financial offences are the v1 focus: payment card fraud, money laundering and crypto-asset
manipulation (Penal Code), illegal public fundraising and fundraising fraud (Special Criminal
Regulation). Their structure, not their wording, is modelled on offence types found in real systems.

Versions are chosen so that temporal traps exist: the ZZ Penal Code (SYNTHETIC) gained Article 30
only on 2022-01-01, and the ZZ Special Criminal Regulation (SYNTHETIC) lowered its blood-alcohol
threshold on 2023-07-01.
"""

from dataclasses import dataclass
from datetime import date

from legalai_contracts import DocType
from legalai_evaluation.synthetic._authoring import Article, LawDoc, make_law_doc

PENAL_CODE = "zz-penal-code"
SPECIAL_REGULATION = "zz-special-criminal-regulation"
PROCEDURE_CODE = "zz-criminal-procedure-code"
EVIDENCE_RULES = "zz-criminal-evidence-rules"
NP_ORDINANCE = "zz-np-public-order-ordinance"


def _penal_articles(*, with_article_30: bool, theft_max: str) -> list[Article]:
    articles = [
        Article(
            "Article 1",
            "Article 1 (Legality). No person may be punished for conduct unless an offence provision of this "
            "Code in force at the time of the conduct prohibits it.",
            ("legality", "罪刑法定", "行为时"),
        ),
        Article(
            "Article 3",
            "Article 3 (Age). A person who had not reached the age of 16 at the time of the conduct is not "
            "criminally responsible.",
            ("age", "年龄", "刑事责任"),
        ),
        Article(
            "Article 4",
            "Article 4 (Self-defence). Conduct is not unlawful if it was necessary to repel an imminent "
            "unlawful attack on the person or another and did not clearly exceed what was needed to repel "
            "the attack.",
            ("self-defence", "defence", "attack", "正当防卫", "防卫"),
        ),
        Article(
            "Article 20",
            "Article 20 (Theft). A person who intentionally takes movable property of another worth 1,000 ZZ "
            "crowns or more, without consent and with the purpose of keeping it, commits theft and is liable "
            f"to imprisonment of up to {theft_max} years.",
            ("theft", "steal", "stole", "盗窃"),
        ),
        Article(
            "Article 21",
            "Article 21 (Fraud). A person who, by deceiving another, causes that person to hand over "
            "property "
            "and thereby obtains property worth 1,000 ZZ crowns or more commits fraud and is liable to "
            "imprisonment of up to five years.",
            ("fraud", "deceive", "deception", "诈骗"),
        ),
        Article(
            "Article 22",
            "Article 22 (Intentional injury). A person who intentionally and unlawfully causes bodily injury "
            "to "
            "another that "
            "a forensic examiner classifies as moderate or serious commits intentional injury and is liable "
            "to imprisonment of up to seven years.",
            ("injury", "assault", "punch", "故意伤害", "伤害"),
        ),
        Article(
            "Article 23",
            "Article 23 (Criminal damage). A person who intentionally destroys or damages property of "
            "another, "
            "causing loss of 2,000 ZZ crowns or more, commits criminal damage and is liable to imprisonment "
            "of up to two years.",
            ("damage", "destroy", "毁坏", "故意毁坏财物", "财物"),
        ),
    ]
    articles += [
        Article(
            "Article 24",
            "Article 24 (Payment card fraud). A person who uses a payment card issued to another, without "
            "that "
            "person's authorisation, to obtain money or goods worth 1,000 ZZ crowns or more commits payment "
            "card "
            "fraud and is liable to imprisonment of up to five years.",
            ("card", "payment card", "bank card", "信用卡", "银行卡", "盗刷"),
        ),
        Article(
            "Article 25",
            "Article 25 (Money laundering). A person who, knowing that funds are the proceeds of an offence, "
            "transfers or converts the funds in order to conceal or disguise their origin commits money "
            "laundering and is liable to imprisonment of up to five years.",
            ("laundering", "proceeds", "crypto", "洗钱", "犯罪所得", "转移"),
        ),
    ]
    if with_article_30:
        articles.append(
            Article(
                "Article 30",
                "Article 30 (Crypto-asset market manipulation). A person who places orders for crypto-assets "
                "without intending them to be executed, in order to mislead other traders about the price, "
                "commits crypto-asset market manipulation and is liable to imprisonment of up to three "
                "years.",
                ("crypto", "manipulation", "orders", "exchange", "加密资产", "操纵"),
            )
        )
    return articles


def _regulation_articles(*, alcohol_threshold: str) -> list[Article]:
    return [
        Article(
            "第一条",
            "第一条　本条例规定的犯罪，依照行为时有效的条文认定。",
            ("legality", "行为时"),
        ),
        Article(
            "第五条",
            f"第五条（醉酒驾驶）在道路上驾驶机动车，血液酒精含量达到每百毫升{alcohol_threshold}毫克以上的，"
            "构成醉酒驾驶罪，处六个月以下拘役。",
            ("drunk driving", "alcohol", "醉驾", "酒驾", "驾驶"),
        ),
        Article(
            "第六条",
            "第六条（职务侵占）公司、企业的工作人员利用职务上的便利，将本单位财物非法占为己有，"
            "数额在五千ZZ元以上的，构成职务侵占罪，处三年以下有期徒刑。",
            ("embezzlement", "employee", "职务侵占", "侵占"),
        ),
        Article(
            "第七条",
            "第七条（敲诈勒索）以威胁手段迫使他人交付财物，数额在二千ZZ元以上的，构成敲诈勒索罪，"
            "处三年以下有期徒刑。",
            ("extortion", "blackmail", "threat", "敲诈勒索", "威胁"),
        ),
        Article(
            "第八条",
            "第八条（伪造印章）伪造公司、企业印章，用于签订合同或者出具证明的，构成伪造印章罪，"
            "处二年以下有期徒刑。",
            ("forgery", "forged", "seal", "stamp", "伪造", "印章", "公章"),
        ),
        Article(
            "第九条",
            "第九条（非法吸收公众资金）未经金融监管部门批准，通过公开宣传，承诺在一定期限内还本付息或者给付回"
            "报，"
            "向社会不特定对象吸收资金的，构成非法吸收公众资金罪，处五年以下有期徒刑。",
            ("fundraising", "deposits", "investors", "public", "非法集资", "吸收资金", "集资", "公众"),
        ),
        Article(
            "第十条",
            "第十条（集资诈骗）以非法占有为目的，实施本条例第九条规定的行为的，构成集资诈骗罪，"
            "处三年以上十年以下有期徒刑。",
            ("fundraising fraud", "appropriate", "集资诈骗", "非法占有"),
        ),
    ]


@dataclass(frozen=True)
class LawLibrary:
    """Every fictional law document version, addressable by `doc_id` and `version_id`."""

    docs: tuple[LawDoc, ...]

    def get(self, doc_id: str, version_id: str) -> LawDoc:
        for doc in self.docs:
            if doc.document.doc_id == doc_id and doc.document.version_id == version_id:
                return doc
        raise KeyError(f"{doc_id}@{version_id}")

    def versions(self, doc_id: str) -> list[LawDoc]:
        return [d for d in self.docs if d.document.doc_id == doc_id]


def build_law_library() -> LawLibrary:
    penal_title = "ZZ Penal Code (SYNTHETIC)"
    regulation_title = "ZZ刑事特别条例（SYNTHETIC）"
    docs = (
        make_law_doc(
            doc_id=PENAL_CODE,
            version_id="2012",
            title=penal_title,
            jurisdiction="ZZ",
            doc_type=DocType.STATUTE,
            language="en",
            effective_from=date(2012, 1, 1),
            effective_to=date(2022, 1, 1),
            articles=_penal_articles(with_article_30=False, theft_max="two"),
        ),
        make_law_doc(
            doc_id=PENAL_CODE,
            version_id="2022",
            title=penal_title,
            jurisdiction="ZZ",
            doc_type=DocType.STATUTE,
            language="en",
            effective_from=date(2022, 1, 1),
            effective_to=None,
            articles=_penal_articles(with_article_30=True, theft_max="three"),
        ),
        make_law_doc(
            doc_id=SPECIAL_REGULATION,
            version_id="2016",
            title=regulation_title,
            jurisdiction="ZZ",
            doc_type=DocType.STATUTE,
            language="zh",
            effective_from=date(2016, 1, 1),
            effective_to=date(2023, 7, 1),
            articles=_regulation_articles(alcohol_threshold="一百二十"),
        ),
        make_law_doc(
            doc_id=SPECIAL_REGULATION,
            version_id="2023",
            title=regulation_title,
            jurisdiction="ZZ",
            doc_type=DocType.STATUTE,
            language="zh",
            effective_from=date(2023, 7, 1),
            effective_to=None,
            articles=_regulation_articles(alcohol_threshold="一百"),
        ),
        make_law_doc(
            doc_id=PROCEDURE_CODE,
            version_id="2015",
            title="ZZ Code of Criminal Procedure (SYNTHETIC)",
            jurisdiction="ZZ",
            doc_type=DocType.STATUTE,
            language="en",
            effective_from=date(2015, 1, 1),
            effective_to=None,
            articles=[
                Article(
                    "Article 10",
                    "Article 10 (Burden of proof). The prosecution bears the burden of proving every element "
                    "of the offence charged.",
                    ("burden", "proof", "举证责任", "证明责任"),
                ),
                Article(
                    "Article 11",
                    "Article 11 (Standard of proof). A defendant may be convicted only if the evidence, "
                    "taken "
                    "as a whole, proves every element of the offence beyond reasonable doubt.",
                    ("standard", "reasonable doubt", "证明标准", "合理怀疑"),
                ),
                Article(
                    "Article 12",
                    "Article 12 (Defences). Where the defence raises self-defence and points to evidence "
                    "supporting it, the prosecution must disprove the defence beyond reasonable doubt.",
                    ("self-defence", "defence", "正当防卫", "辩护"),
                ),
                Article(
                    "Article 13",
                    "Article 13 (Confessions). A conviction may not rest on the defendant's confession alone "
                    "without other evidence corroborating it.",
                    ("confession", "corroboration", "供述", "口供"),
                ),
                Article(
                    "Article 14",
                    "Article 14 (Forensic opinions). A forensic opinion is admissible only if it states the "
                    "examiner's name, the method used and the date of examination.",
                    ("forensic", "expert", "鉴定意见", "鉴定"),
                ),
            ],
        ),
        make_law_doc(
            doc_id=EVIDENCE_RULES,
            version_id="2019",
            title="ZZ刑事证据规则（SYNTHETIC）",
            jurisdiction="ZZ",
            doc_type=DocType.REGULATION,
            language="zh",
            effective_from=date(2019, 1, 1),
            effective_to=None,
            articles=[
                Article(
                    "第三条",
                    "第三条　在公诉案件中，被告人有罪的证明责任由ZZ检察署承担。",
                    ("burden", "证明责任", "举证"),
                ),
                Article(
                    "第四条",
                    "第四条　认定被告人有罪，每一项犯罪构成要件事实都应当有证据证明，"
                    "并且综合全案证据，对所认定事实已无合理怀疑。",
                    ("standard", "reasonable doubt", "证明标准", "合理怀疑"),
                ),
                Article(
                    "第五条",
                    "第五条　仅凭被告人本人的供述而无其他证据相互印证的，不得作出有罪认定。",
                    ("confession", "供述", "印证"),
                ),
                Article(
                    "第六条",
                    "第六条　鉴定意见应当载明鉴定人、鉴定方法和鉴定日期，否则不得作为定案根据。",
                    ("forensic", "鉴定意见", "鉴定"),
                ),
            ],
        ),
        make_law_doc(
            doc_id=NP_ORDINANCE,
            version_id="2019",
            title="Northern Province Public Order Ordinance (SYNTHETIC)",
            jurisdiction="ZZ-NP",
            doc_type=DocType.REGULATION,
            language="en",
            effective_from=date(2019, 1, 1),
            effective_to=None,
            articles=[
                Article(
                    "Article 1",
                    "Article 1 (Scope). This Ordinance applies only to conduct within the Northern Province "
                    "of ZZ.",
                    ("scope", "province"),
                ),
                Article(
                    "Article 2",
                    "Article 2 (Disorderly conduct). A person who intentionally causes a public disturbance "
                    "commits disorderly conduct.",
                    ("disorderly", "disturbance"),
                ),
            ],
        ),
    )
    return LawLibrary(docs=docs)
