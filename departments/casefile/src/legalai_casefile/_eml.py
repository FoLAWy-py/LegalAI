"""E-mail (.eml, RFC 5322 / MIME) text extraction with the standard library.

Stored text: one line `Name: value` for each From, To, Cc, Date, Subject header present (values as
decoded and rendered by Python's `email` package, RFC 2047 encoded words decoded), one empty line,
then every inline text/plain body part, joined by "\\n". In a multipart/alternative the text/plain
alternative is used. Body bytes are decoded strictly with the declared charset; GB2312/GBK labels are
decoded as GB18030 (their superset, as browsers do).

Refused: HTML-only bodies (no exact text conversion in v1), inline forwarded messages, MIME defects,
undecodable charsets. Attachments and inline images are separate documents: reported as warnings.
"""

from email import policy
from email.message import EmailMessage, Message
from email.parser import BytesParser

from legalai_casefile._common import Extraction, single_page
from legalai_casefile.errors import (
    CorruptDocumentError,
    FormatMismatchError,
    UndecodableTextError,
    UnsupportedContentError,
)

MEDIA_TYPE = "message/rfc822"
HEADERS = ("From", "To", "Cc", "Date", "Subject")
_GB_ALIASES = frozenset({"gb2312", "gbk", "x-gbk", "cp936", "euc-cn", "gb_2312-80", "csgb2312"})


def _charset(part: Message) -> str:
    charset = (part.get_content_charset() or "utf-8").lower()
    return "gb18030" if charset in _GB_ALIASES else charset


def _decode(part: Message) -> str:
    payload = part.get_payload(decode=True)
    if part.defects:
        raise CorruptDocumentError(f"malformed MIME body part ({len(part.defects)} defect(s))")
    if not isinstance(payload, bytes):
        raise CorruptDocumentError("text part has no decodable payload")
    charset = _charset(part)
    try:
        return payload.decode(charset, errors="strict")
    except LookupError as exc:
        raise UndecodableTextError("unknown charset in e-mail body") from exc
    except UnicodeDecodeError as exc:
        raise UndecodableTextError(f"e-mail body is not valid {charset} at offset {exc.start}") from exc


class _Collector:
    def __init__(self) -> None:
        self.bodies: list[str] = []
        self.attachments = 0
        self.inline_other = 0

    def visit(self, part: Message) -> None:
        if part.defects:
            raise CorruptDocumentError(f"malformed MIME structure ({len(part.defects)} defect(s))")
        ctype = part.get_content_type()
        if part.get_content_disposition() == "attachment":
            self.attachments += 1
            return
        if ctype == "message/rfc822":
            raise UnsupportedContentError("inline forwarded message; save it as its own .eml")
        if part.is_multipart():
            payload = part.get_payload()
            if not isinstance(payload, list):
                raise CorruptDocumentError("multipart without parts")
            children: list[Message] = []
            for child in payload:
                if not isinstance(child, Message):
                    raise CorruptDocumentError("multipart with a non-message part")
                children.append(child)
            if ctype == "multipart/alternative":
                plain = [c for c in children if c.get_content_type() == "text/plain"]
                chosen = plain[:1] or children[-1:]
                for c in chosen:
                    self.visit(c)
                return
            for c in children:
                self.visit(c)
            return
        if ctype == "text/plain":
            self.bodies.append(_decode(part))
        elif ctype == "text/html":
            raise UnsupportedContentError("HTML-only e-mail body; no exact plain-text version")
        else:
            self.inline_other += 1


def extract_eml(data: bytes) -> Extraction:
    msg = BytesParser(policy=policy.default).parsebytes(data)
    if not isinstance(msg, EmailMessage) or not any(msg.get(h) is not None for h in ("From", "Date")):
        raise FormatMismatchError("not an RFC 5322 e-mail (no From or Date header)")
    lines = [f"{name}: {value}\n" for name in HEADERS for value in (msg.get_all(name) or [])]
    collector = _Collector()
    collector.visit(msg)
    if not collector.bodies:
        raise UnsupportedContentError("e-mail has no inline text/plain body")
    text = "".join(lines) + "\n" + "\n".join(collector.bodies)
    warnings = []
    if collector.attachments:
        warnings.append(f"{collector.attachments} attachment(s) not extracted; ingest them separately")
    if collector.inline_other:
        warnings.append(f"{collector.inline_other} inline non-text part(s) (e.g. images) not extracted")
    return single_page(text, MEDIA_TYPE, "email-stdlib", warnings)
