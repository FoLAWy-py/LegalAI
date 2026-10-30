"""Plain text, Markdown and e-mail intake: strict decoding, exact text, fail-closed cases."""

import codecs
from email.message import EmailMessage

import pytest

from legalai_casefile import (
    CorruptDocumentError,
    EmptyDocumentError,
    FormatMismatchError,
    PartialExtractionError,
    UndecodableTextError,
    UnsupportedContentError,
    extract_document,
)

ZH = (
    "SYNTHETIC 收据\r\n"
    "今收到示例乙交来货款人民币捌仟元整（¥8,000.00）。\r\n"
    "收款人：示例甲；日期：２０２６年１０月３０日\r\n"
)
EN = "SYNTHETIC Notice of Default\nThe Buyer has not paid invoice ZZ-001 by 2026-10-01.\n"
MIXED = (
    "# SYNTHETIC 会议纪要 Minutes\n\n- 甲方 (Party A) agreed to 延期交付 until 2026-12-01；\n- 张𠀀 signed.\n"
)


@pytest.mark.parametrize(("name", "text"), [("a.txt", ZH), ("b.txt", EN), ("c.md", MIXED)])
def test_utf8_text_is_exact_including_crlf(name: str, text: str) -> None:
    ex = extract_document(f"SYNTHETIC-{name}", text.encode("utf-8"))
    assert ex.text == text
    assert ex.page_starts == (0,)
    assert ex.media_type == ("text/markdown" if name.endswith(".md") else "text/plain")


@pytest.mark.parametrize(
    ("bom", "codec"),
    [(codecs.BOM_UTF8, "utf-8"), (codecs.BOM_UTF16_LE, "utf-16-le"), (codecs.BOM_UTF16_BE, "utf-16-be")],
)
def test_bom_selects_encoding_and_is_removed(bom: bytes, codec: str) -> None:
    ex = extract_document("SYNTHETIC.txt", bom + ZH.encode(codec))
    assert ex.text == ZH


def test_gb18030_needs_explicit_encoding() -> None:
    data = ZH.encode("gb18030")
    with pytest.raises(UndecodableTextError) as err:
        extract_document("SYNTHETIC.txt", data)
    assert "gb18030" in str(err.value)
    assert extract_document("SYNTHETIC.txt", data, encoding="gb18030").text == ZH


def test_binary_or_container_in_text_file() -> None:
    with pytest.raises(FormatMismatchError):
        extract_document("SYNTHETIC.txt", b"abc\x00def")
    with pytest.raises(FormatMismatchError):
        extract_document("SYNTHETIC.txt", b"%PDF-1.7 ...")


def test_control_and_replacement_characters_refused() -> None:
    with pytest.raises(PartialExtractionError):
        extract_document("SYNTHETIC.txt", "坏字符�".encode())
    with pytest.raises(PartialExtractionError):
        extract_document("SYNTHETIC.txt", "控制\x1b字符".encode())


def test_whitespace_only_is_empty() -> None:
    with pytest.raises(EmptyDocumentError):
        extract_document("SYNTHETIC.txt", " \n　\n".encode())


# ---- e-mail -----------------------------------------------------------------------------------


def _mail(**headers: str) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = headers.get("From", "示例甲 <a@example.zz>")
    msg["To"] = "示例乙 <b@example.zz>"
    msg["Date"] = "Fri, 30 Oct 2026 09:00:00 +0800"
    msg["Subject"] = headers.get("Subject", "SYNTHETIC 关于逾期付款的通知")
    return msg


BODY = "示例乙：\n贵方尚欠货款¥8,000.00（捌仟元整），请于十日内支付。\nRegards, Party A\n"


def test_chinese_email_with_encoded_subject_and_base64_body() -> None:
    msg = _mail()
    msg.set_content(BODY, charset="utf-8", cte="base64")
    raw = msg.as_bytes()
    assert b"=?utf-8?" in raw.lower()  # the subject really is RFC 2047 encoded
    ex = extract_document("SYNTHETIC.eml", raw)
    assert ex.text == (
        "From: 示例甲 <a@example.zz>\n"
        "To: 示例乙 <b@example.zz>\n"
        "Date: Fri, 30 Oct 2026 09:00:00 +0800\n"
        "Subject: SYNTHETIC 关于逾期付款的通知\n"
        "\n" + BODY
    )
    assert ex.media_type == "message/rfc822"


def test_gb2312_label_with_gbk_only_character_decodes_as_gb18030() -> None:
    body = "经办人：朱镕（镕 不在 GB2312 中）\n".encode("gb18030")
    raw = (
        b"From: a@example.zz\nDate: Fri, 30 Oct 2026 09:00:00 +0800\nSubject: SYNTHETIC\n"
        b"MIME-Version: 1.0\nContent-Type: text/plain; charset=gb2312\nContent-Transfer-Encoding: 8bit\n\n"
        + body
    )
    ex = extract_document("SYNTHETIC.eml", raw)
    assert ex.text.endswith("经办人：朱镕（镕 不在 GB2312 中）\n")


def test_alternative_uses_plain_and_attachment_is_warning() -> None:
    msg = _mail()
    msg.set_content(BODY)
    msg.add_alternative("<p>HTML 版本不应出现</p>", subtype="html")
    msg.add_attachment(
        "附件内容不应出现".encode(), maintype="application", subtype="octet-stream", filename="a.bin"
    )
    ex = extract_document("SYNTHETIC.eml", msg.as_bytes())
    assert ex.text.endswith("\n\n" + BODY)
    assert "HTML" not in ex.text and "附件内容" not in ex.text
    assert any("attachment" in w for w in ex.warnings)


def test_html_only_email_refused() -> None:
    msg = _mail()
    msg.set_content("<p>仅有HTML</p>", subtype="html")
    with pytest.raises(UnsupportedContentError):
        extract_document("SYNTHETIC.eml", msg.as_bytes())


def test_inline_forwarded_message_refused() -> None:
    inner = _mail(Subject="SYNTHETIC inner")
    inner.set_content("被转发的内容\n")
    outer = _mail()
    outer.set_content("请见下方转发。\n")
    outer.add_related(inner, disposition="inline")
    with pytest.raises(UnsupportedContentError):
        extract_document("SYNTHETIC.eml", outer.as_bytes())


def test_wrong_charset_bytes_refused() -> None:
    raw = (
        b"From: a@example.zz\nDate: Fri, 30 Oct 2026 09:00:00 +0800\n"
        b"Content-Type: text/plain; charset=utf-8\nContent-Transfer-Encoding: 8bit\n\n"
        + "错误编码".encode("gb18030")
    )
    with pytest.raises(UndecodableTextError):
        extract_document("SYNTHETIC.eml", raw)


def test_broken_base64_refused() -> None:
    raw = (
        b"From: a@example.zz\nDate: Fri, 30 Oct 2026 09:00:00 +0800\n"
        b"Content-Type: text/plain; charset=utf-8\nContent-Transfer-Encoding: base64\n\n5Lit5paH!!!\n"
    )
    with pytest.raises((CorruptDocumentError, UndecodableTextError)):
        extract_document("SYNTHETIC.eml", raw)


def test_not_an_email() -> None:
    with pytest.raises(FormatMismatchError):
        extract_document("SYNTHETIC.eml", "只是一段文字".encode())
