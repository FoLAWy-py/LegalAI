"""Build small synthetic .docx files in memory, for tests only. Not part of the public API.

The XML mirrors what Word writes (transitional namespaces, runs, tables, markup-compatibility blocks).
"""

import io
import zipfile
from xml.sax.saxutils import escape

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_NS = (
    f'xmlns:w="{W_NS}" '
    'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
    'xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape" '
    'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
    'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture" '
    'xmlns:v="urn:schemas-microsoft-com:vml" '
    'xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math" '
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
)
_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/"
_PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"


def run(text: str) -> str:
    props = '<w:rPr><w:rFonts w:eastAsia="SimSun"/></w:rPr>'
    return f'<w:r>{props}<w:t xml:space="preserve">{escape(text)}</w:t></w:r>'


def para(*parts: str) -> str:
    """A paragraph; plain strings become runs, strings starting with '<' are inserted as XML."""
    inner = "".join(p if p.startswith("<") else run(p) for p in parts)
    return f'<w:p><w:pPr><w:jc w:val="both"/></w:pPr>{inner}</w:p>'


def table(rows: list[list[str]]) -> str:
    cells = "".join(
        "<w:tr>" + "".join(f"<w:tc><w:tcPr/>{para(c)}</w:tc>" for c in row) + "</w:tr>" for row in rows
    )
    return f"<w:tbl><w:tblPr/><w:tblGrid/>{cells}</w:tbl>"


def textbox(text: str) -> str:
    """A text box as Word writes it: the same content in mc:Choice and in the VML fallback."""
    content = f"<w:txbxContent>{para(text)}</w:txbxContent>"
    return (
        "<w:r><mc:AlternateContent>"
        f'<mc:Choice Requires="wps"><w:drawing><wps:txbx>{content}</wps:txbx></w:drawing></mc:Choice>'
        f"<mc:Fallback><w:pict><v:textbox>{content}</v:textbox></w:pict></mc:Fallback>"
        "</mc:AlternateContent></w:r>"
    )


IMAGE_RUN = (
    '<w:r><w:drawing><pic:pic><pic:blipFill><a:blip r:embed="rIdImg"/></pic:blipFill>'
    "</pic:pic></w:drawing></w:r>"
)


def build_docx(
    body: str,
    *,
    headers: tuple[str, ...] = (),
    footers: tuple[str, ...] = (),
    footnotes: tuple[str, ...] = (),
    comments: tuple[str, ...] = (),
    raw_document: bytes | None = None,
) -> bytes:
    """Return .docx bytes. `body` is the XML inside `w:body`; parts take paragraph XML."""
    files: dict[str, bytes] = {}
    rels: list[tuple[str, str]] = []
    for i, xml in enumerate(headers, start=1):
        files[f"word/header{i}.xml"] = f"<w:hdr {_NS}>{xml}</w:hdr>".encode()
        rels.append(("header", f"header{i}.xml"))
    for i, xml in enumerate(footers, start=1):
        files[f"word/footer{i}.xml"] = f"<w:ftr {_NS}>{xml}</w:ftr>".encode()
        rels.append(("footer", f"footer{i}.xml"))
    if footnotes:
        notes = '<w:footnote w:type="separator" w:id="-1"><w:p><w:r><w:separator/></w:r></w:p></w:footnote>'
        notes += "".join(f'<w:footnote w:id="{i}">{xml}</w:footnote>' for i, xml in enumerate(footnotes, 1))
        files["word/footnotes.xml"] = f"<w:footnotes {_NS}>{notes}</w:footnotes>".encode()
        rels.append(("footnotes", "footnotes.xml"))
    if comments:
        body_c = "".join(f'<w:comment w:id="{i}">{xml}</w:comment>' for i, xml in enumerate(comments))
        files["word/comments.xml"] = f"<w:comments {_NS}>{body_c}</w:comments>".encode()
        rels.append(("comments", "comments.xml"))
    document = (
        raw_document
        or (
            f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:document {_NS}><w:body>{body}'
            "<w:sectPr/></w:body></w:document>"
        ).encode()
    )
    rel_xml = "".join(
        f'<Relationship Id="rId{i}" Type="{_REL}{kind}" Target="{target}"/>'
        for i, (kind, target) in enumerate(rels, start=1)
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="xml" ContentType="application/xml"/></Types>',
        )
        zf.writestr(
            "_rels/.rels",
            f'<?xml version="1.0"?><Relationships xmlns="{_PKG_REL}">'
            f'<Relationship Id="rId1" Type="{_REL}officeDocument" Target="word/document.xml"/>'
            "</Relationships>",
        )
        zf.writestr("word/document.xml", document)
        zf.writestr(
            "word/_rels/document.xml.rels",
            f'<?xml version="1.0"?><Relationships xmlns="{_PKG_REL}">{rel_xml}</Relationships>',
        )
        for name, data in files.items():
            zf.writestr(name, data)
    return buf.getvalue()
