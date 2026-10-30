# ruff: noqa: RUF001
# (Synthetic CN-structured fixtures must use CJK full-width punctuation such as the full-width
#  parentheses, colon and comma, which the extractor and structure parser handle.)
"""Extraction (normalization.md rules) and structure derivation on synthetic ZZ text."""

import pytest

from legalai_corpus.extract import (
    ExtractionError,
    HtmlRule,
    PdfRule,
    extract_html,
    extract_pdf,
    map_compat_to_unified,
    scan_compat,
)
from legalai_corpus.structure import StructureError, derive_units

RULE = HtmlRule(("id", "content"))


def test_html_container_only_whitespace_rules_and_entities(zz) -> None:
    raw = zz.page(
        "<p>　　SYNTHETIC ZZ 示例法</p>"
        "<p>　　第一条　本条\n   仅用于  测试&amp;演示。&nbsp;</p>"
        "<script>var x='第二条 noise';</script>"
        "<p></p><div>第二条　<span>内联</span><b>文字</b>保持。<br>第二款文字。</div>"
    )
    text = extract_html(raw, RULE)
    assert (
        text == "SYNTHETIC ZZ 示例法\n第一条　本条 仅用于 测试&演示。\n第二条　内联文字保持。\n第二款文字。"
    )
    assert "noise" not in text and "footer" not in text and "首页" not in text


def test_internal_fullwidth_and_nbsp_spaces_preserved(zz) -> None:
    text = extract_html(zz.page("<p>第一条　甲 乙　丙</p>"), RULE)
    assert text == "第一条　甲 乙　丙"


def test_class_container_and_markers(zz) -> None:
    raw = zz.page("<p>编者按 SYNTHETIC</p><p>START 第一条　内容。</p><p>（完）END</p><p>责任编辑</p>")
    rule = HtmlRule(("class", "main"), start_marker="START", end_marker="END")
    assert extract_html(raw, rule) == "START 第一条　内容。\n（完）END"


def test_ambiguous_or_missing_markers_and_container_fail_closed(zz) -> None:
    raw = zz.page("<p>A 第一条 A</p>")
    with pytest.raises(ExtractionError):
        extract_html(raw, HtmlRule(("id", "content"), start_marker="A"))
    with pytest.raises(ExtractionError):
        extract_html(raw, HtmlRule(("id", "content"), end_marker="ZZZ"))
    with pytest.raises(ExtractionError):
        extract_html(raw, HtmlRule(("id", "nope")))


def test_wrong_encoding_fails_closed(zz) -> None:
    raw = zz.page("<p>第一条　内容</p>")
    with pytest.raises(ExtractionError):
        extract_html(raw, HtmlRule(("id", "content"), encoding="ascii"))


def test_compat_codepoints_detected_and_mapped_one_for_one() -> None:
    text = "第一条　⼈民⽉份"  # KANGXI RADICAL MAN / MOON look like 人 / 月
    assert scan_compat(text) == {"U+2F08": 1, "U+2F49": 1}
    mapped, changes = map_compat_to_unified(text)
    assert mapped == "第一条　人民月份"
    assert len(mapped) == len(text)
    assert [c["offset"] for c in changes] == [4, 6]
    assert scan_compat("第一条　人民") == {}


def test_pdf_paragraphs_by_indentation(zz) -> None:
    pdf = zz.pdf(
        [
            (72, 720, "SYNTHETIC ZZ CODE"),
            (96, 700, "Article 1 First line of"),
            (72, 686, "the same paragraph."),
            (96, 672, "Article 2 Another one."),
            (300, 40, "- 1 -"),
        ]
    )
    text = extract_pdf(pdf, PdfRule(drop_line_patterns=(r"- \d+ -",)))
    assert text.split("\n") == [
        "SYNTHETIC ZZ CODE",
        "Article 1 First line ofthe same paragraph.",  # CJK rule: wrapped lines join without a space
        "Article 2 Another one.",
    ]


SYNTH = "\n".join(
    [
        "SYNTHETIC ZZ 示例法典",
        "第一编　总则",
        "第一章　一般规定",
        "第一条　SYNTHETIC 第一款内容。",
        "第二款内容，有下列情形之一的：",
        "（一）第一项；",
        "（二）第二项。",
        "第三款内容。",
        "第二条　内容。",
        "第二条之一　插入条文。",
        "第二章　其他",
        "第一节　小节",
        "第三条　内容。",
        "第二编　分则",
        "第四条　内容。",
    ]
)


def test_cn_law_units_and_pinpoints() -> None:
    units = {u.pinpoint: u for u in derive_units(SYNTH, "cn-law")}
    art1 = units["第一条"]
    assert SYNTH[art1.start : art1.end].startswith("第一条　SYNTHETIC")
    assert SYNTH[art1.start : art1.end].endswith("第三款内容。")
    assert SYNTH[units["第一条第二款"].start : units["第一条第二款"].end] == (
        "第二款内容，有下列情形之一的：\n（一）第一项；\n（二）第二项。"
    )
    assert SYNTH[units["第一条第二款（二）"].start : units["第一条第二款（二）"].end] == "（二）第二项。"
    assert SYNTH[units["第一条第三款"].start : units["第一条第三款"].end] == "第三款内容。"
    assert "第二条之一" in units
    part1 = units["第一编"]
    assert SYNTH[part1.start : part1.end].endswith("第三条　内容。")  # until the next 编
    chapter1 = units["第一章"]
    assert SYNTH[chapter1.start : chapter1.end].endswith("第二条之一　插入条文。")
    for u in units.values():
        assert 0 <= u.start < u.end <= len(SYNTH)


def test_amendment_items() -> None:
    text = "SYNTHETIC ZZ 修正案\n一、将第一条修改为：\n“第一条　新内容。”\n二、本修正案自2099年1月1日起施行。"
    units = {u.pinpoint: u for u in derive_units(text, "cn-amendment")}
    assert text[units["一、"].start : units["一、"].end] == "一、将第一条修改为：\n“第一条　新内容。”"
    assert text[units["二、"].start : units["二、"].end].endswith("起施行。")


def test_duplicate_article_fails_closed() -> None:
    with pytest.raises(StructureError):
        derive_units("第一条　甲。\n第一条　乙。", "cn-law")
    with pytest.raises(StructureError):
        derive_units("x", "no-such-profile")
