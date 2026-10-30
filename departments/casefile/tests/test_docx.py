# ruff: noqa: RUF001 - full-width CJK punctuation is the data under test, not a typo.
""".docx intake: exact text for Chinese / English / mixed content and fail-closed constructs."""

import pytest

from legalai_casefile import (
    EmptyDocumentError,
    EncryptedDocumentError,
    FormatMismatchError,
    UnsupportedContentError,
    UnsupportedFormatError,
    extract_document,
)
from legalai_casefile._synthetic_docs import IMAGE_RUN, build_docx, para, run, table, textbox

MEDIA = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def test_chinese_contract_with_table_header_footer_footnote_textbox() -> None:
    body = "".join(
        [
            para("SYNTHETIC 借款合同（ZZ 测试）"),
            para("出借人：示例甲；", "借款人：示例乙。"),
            para("第一条　借款金额：人民币伍万元整（¥50,000.00）", "<w:r><w:tab/></w:r>", "附表如下："),
            table([["期次", "还款日", "金额"], ["1", "２０２６年１１月３０日", "¥25,000.00"]]),
            para("第二条　利息：年利率4.35%", "<w:r><w:br/></w:r>", "逾期另计。"),
            para("见边框：", textbox("文本框内容：仅供测试。")),
            para("签字：", IMAGE_RUN),
        ]
    )
    data = build_docx(
        body,
        headers=(para("合同编号：ZZ-JK-0001"),),
        footers=(para("第 1 页"),),
        footnotes=(para("注：本合同为合成样本。"),),
        comments=(para("批注不应出现在正文中"),),
    )
    ex = extract_document("SYNTHETIC-借款合同.docx", data)
    assert ex.text == (
        "SYNTHETIC 借款合同（ZZ 测试）\n"
        "出借人：示例甲；借款人：示例乙。\n"
        "第一条　借款金额：人民币伍万元整（¥50,000.00）\t附表如下：\n"
        "期次\n还款日\n金额\n1\n２０２６年１１月３０日\n¥25,000.00\n"
        "第二条　利息：年利率4.35%\n逾期另计。\n"
        "见边框：文本框内容：仅供测试。\n\n"
        "签字：\n"
        "合同编号：ZZ-JK-0001\n"
        "第 1 页\n"
        "注：本合同为合成样本。\n"
    )
    assert ex.page_starts == (0,)
    assert ex.media_type == MEDIA
    assert "批注" not in ex.text
    assert any("image" in w for w in ex.warnings)
    assert any("comments" in w for w in ex.warnings)


def test_english_and_mixed_runs() -> None:
    body = para(
        "SYNTHETIC Services Agreement. ", "The Supplier (", "供应方", ") shall deliver by 2026-11-30."
    )
    ex = extract_document("SYNTHETIC.docx", build_docx(body))
    assert ex.text == "SYNTHETIC Services Agreement. The Supplier (供应方) shall deliver by 2026-11-30.\n"


def test_field_result_kept_field_code_dropped() -> None:
    field = (
        '<w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText> PAGE </w:instrText></w:r>'
        '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
        + run("3")
        + '<w:r><w:fldChar w:fldCharType="end"/></w:r>'
    )
    ex = extract_document("SYNTHETIC.docx", build_docx(para("第", field, "页")))
    assert ex.text == "第3页\n"


def test_special_characters_map_as_documented() -> None:
    xml = para("A", "<w:r><w:noBreakHyphen/><w:softHyphen/><w:cr/></w:r>", "B")
    assert extract_document("SYNTHETIC.docx", build_docx(xml)).text == "A‑­\nB\n"


def test_astral_characters() -> None:
    ex = extract_document("SYNTHETIC.docx", build_docx(para("当事人：张𠀀")))
    assert ex.text == "当事人：张𠀀\n"
    assert len(ex.text) == 7


@pytest.mark.parametrize(
    "xml",
    [
        '<w:p><w:ins w:id="1" w:author="SYNTHETIC">' + run("新增条款") + "</w:ins></w:p>",
        '<w:p><w:del w:id="1" w:author="SYNTHETIC"><w:r><w:delText>删除条款</w:delText></w:r></w:del></w:p>',
        '<w:p><w:r><w:sym w:font="Wingdings" w:char="F0FE"/></w:r></w:p>',
        "<w:p><w:r><w:object/></w:r></w:p>",
        para(" 已勾选"),
    ],
    ids=["insertion", "deletion", "symbol", "ole-object", "private-use-char"],
)
def test_ambiguous_constructs_are_refused(xml: str) -> None:
    with pytest.raises(UnsupportedContentError):
        extract_document("SYNTHETIC.docx", build_docx(xml))


def test_doctype_is_refused() -> None:
    raw = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]><w:document/>'
    with pytest.raises(UnsupportedContentError):
        extract_document("SYNTHETIC.docx", build_docx("", raw_document=raw))


def test_encrypted_word_file_is_refused() -> None:
    ole = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 64 + "EncryptedPackage".encode("utf-16-le")
    with pytest.raises(EncryptedDocumentError):
        extract_document("SYNTHETIC.docx", ole)


def test_legacy_doc_is_unsupported() -> None:
    with pytest.raises(UnsupportedFormatError):
        extract_document("SYNTHETIC.docx", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 64)
    with pytest.raises(UnsupportedFormatError):
        extract_document("SYNTHETIC.doc", b"anything")


def test_not_a_zip() -> None:
    with pytest.raises(FormatMismatchError):
        extract_document("SYNTHETIC.docx", "纯文本".encode())


def test_empty_document() -> None:
    with pytest.raises(EmptyDocumentError):
        extract_document("SYNTHETIC.docx", build_docx(para("") + para("　")))
