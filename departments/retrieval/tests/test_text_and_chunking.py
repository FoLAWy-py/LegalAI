"""Tokenisation (Chinese first), glossary expansion and structural chunking."""

import pytest

from legalai_retrieval.chunking import chunk_case, chunk_law
from legalai_retrieval.glossary import Glossary, _parse
from legalai_retrieval.text import cn_to_int, int_to_cn, stem, tokenize


@pytest.mark.parametrize(
    ("numeral", "value"),
    [
        ("五百七十七", 577),
        ("一百零五", 105),
        ("十二", 12),
        ("二十", 20),
        ("一千二百六十", 1260),
        ("577", 577),
    ],
)
def test_chinese_numerals(numeral: str, value: int) -> None:
    assert cn_to_int(numeral) == value


def test_int_to_cn_for_paragraph_pinpoints() -> None:
    assert [int_to_cn(n) for n in (1, 2, 10, 11, 21)] == ["一", "二", "十", "十一", "二十一"]


def test_cjk_bigrams_without_whitespace() -> None:
    tokens = tokenize("非法吸收公众存款")
    assert {"非法", "吸收", "公众", "存款"} <= set(tokens)


def test_article_reference_token_matches_across_scripts() -> None:
    ref = "§101"
    assert ref in tokenize("第一百零一条　违反金融管理规定")
    assert ref in tokenize("依照第101条的规定")
    assert ref in tokenize("see Section 101 of the Act")
    assert "§103-1" in tokenize("第一百零三条之一　实施金融犯罪后")


def test_light_stemmer_is_consistent() -> None:
    assert stem("delivered") == stem("delivers") == stem("deliver")
    assert stem("terminate") == stem("termination") == stem("terminated")
    assert stem("parties") == "party"


def test_coverage_ignores_question_fillers_and_uses_glossary() -> None:
    glossary = Glossary.default()
    analysis = glossary.analyze("非法吸收公众存款什么时候构成犯罪")
    zh_doc = set(tokenize("向社会公众吸收存款构成非法吸收公众存款罪"))
    assert analysis.coverage(zh_doc) == pytest.approx(1.0)
    en_doc = set(tokenize("Unauthorised deposit-taking from the general public is a crime."))
    assert analysis.coverage(en_doc) >= 0.6
    assert analysis.coverage(set(tokenize("宇宙飞船燃料"))) == 0.0


def test_glossary_rejects_malformed_lines() -> None:
    with pytest.raises(ValueError, match="expected"):
        _parse("only-one-column\n")


CN_LAW = """ZZ国刑法【SYNTHETIC】
第一章　犯罪和刑事责任
第十条　明知自己的行为会发生危害社会的结果、构成犯罪的、是故意犯罪。
第三章　破坏金融管理秩序罪
第一百零一条　违反金融管理规定、向社会公众吸收资金、数额较大的、处三年以下有期徒刑。
有前款行为、在提起公诉前积极退赃退赔的、可以从轻处罚。
第一百零三条之一　实施金融犯罪后、本人掩饰犯罪所得来源的、依照前条的规定处罚。
"""


def test_cn_law_units_align_to_articles_with_exact_offsets() -> None:
    units = chunk_law(CN_LAW, max_chars=800)
    assert [u.pinpoint for u in units] == ["preamble", "第十条", "第一百零一条", "第一百零三条之一"]
    art101 = units[2]
    assert CN_LAW[art101.start : art101.end].startswith("第一百零一条")
    assert CN_LAW[art101.start : art101.end].endswith("可以从轻处罚。")
    assert art101.context == "第三章　破坏金融管理秩序罪"
    for u in units:
        span = CN_LAW[u.start : u.end]
        assert span == span.strip()


def test_long_cn_article_splits_into_paragraph_pinpoints() -> None:
    units = chunk_law(CN_LAW, max_chars=60)
    pins = [u.pinpoint for u in units]
    assert "第一百零一条第一款" in pins and "第一百零一条第二款" in pins


def test_en_law_units_and_headings() -> None:
    text = (
        "ZZ Act (SYNTHETIC)\nPART I OFFENCES\nSection 1. A person who solicits deposits commits an offence.\n"
    )
    units = chunk_law(text, 800)
    assert [u.pinpoint for u in units] == ["preamble", "Section 1"]
    assert units[1].context == "PART I OFFENCES"


def test_unstructured_law_falls_back_to_paragraphs() -> None:
    text = (
        "A first paragraph that is long enough to stand alone as a unit.\n"
        "A second one, also long enough here."
    )
    assert [u.pinpoint for u in chunk_law(text, 800)] == ["para. 1", "para. 2"]


def test_case_units_never_cross_pages() -> None:
    page1 = "第一条　交货时间　卖方应当于2025年3月1日前交付全部货物至买方仓库。\n"
    page2 = "第二条　违约责任　卖方逾期交货的、每日按照总价款的千分之五支付违约金。\n"
    text = page1 + page2
    units = chunk_case(text, (0, len(page1)), 800, context="合同")
    assert [(u.pinpoint, text[u.start : u.end][:3]) for u in units] == [
        ("p. 1", "第一条"),
        ("p. 2", "第二条"),
    ]


def test_short_case_lines_are_merged_forward() -> None:
    text = "问　你投了多少钱\n答　我先后投了二十万元、签了借款合同、钱转到了公司账户。\n"
    units = chunk_case(text, (0,), 800, context="")
    assert len(units) == 1 and text[units[0].start : units[0].end].startswith("问　")
