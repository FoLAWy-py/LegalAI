"""Plain text and Markdown: strict decoding, no other change.

Rules: a byte-order mark selects UTF-8 / UTF-16 / UTF-32 and is removed (it is not text). Without a
BOM the bytes MUST be valid UTF-8, unless the caller names the encoding (e.g. `gb18030`). Line
endings are kept exactly as in the file. Guessing legacy encodings is refused because a wrong guess
silently produces different characters.
"""

import codecs

from legalai_casefile._common import Extraction, single_page
from legalai_casefile.errors import FormatMismatchError, UndecodableTextError

MEDIA_TYPES = {".txt": "text/plain", ".md": "text/markdown"}

_BOMS = (
    (codecs.BOM_UTF32_LE, "utf-32-le"),
    (codecs.BOM_UTF32_BE, "utf-32-be"),
    (codecs.BOM_UTF8, "utf-8"),
    (codecs.BOM_UTF16_LE, "utf-16-le"),
    (codecs.BOM_UTF16_BE, "utf-16-be"),
)


def decode_strict(data: bytes, encoding: str | None) -> tuple[str, str]:
    """Return (text, encoding used). Raises `UndecodableTextError`; never substitutes characters."""
    body, used = data, encoding
    for bom, name in _BOMS:
        if data.startswith(bom):
            if encoding is not None and codecs.lookup(encoding).name != codecs.lookup(name).name:
                raise UndecodableTextError(f"byte-order mark says {name} but caller passed {encoding}")
            body, used = data[len(bom) :], name
            break
    if used is None:
        if b"\x00" in data:
            raise FormatMismatchError("binary content (NUL bytes) in a text file; UTF-16 needs a BOM")
        used = "utf-8"
    try:
        return body.decode(used, errors="strict"), used
    except LookupError as exc:
        raise UndecodableTextError(f"unknown encoding {used!r}") from exc
    except UnicodeDecodeError as exc:
        hint = "" if encoding else "; pass encoding= explicitly (e.g. 'gb18030')"
        raise UndecodableTextError(f"bytes are not valid {used} at offset {exc.start}{hint}") from exc


def extract_text_file(data: bytes, suffix: str, encoding: str | None) -> Extraction:
    if data.startswith(b"%PDF-") or data.startswith(b"PK\x03\x04"):
        raise FormatMismatchError("content is a PDF or ZIP container, not text")
    text, used = decode_strict(data, encoding)
    return single_page(text, MEDIA_TYPES[suffix], f"text-decoder {used}")
