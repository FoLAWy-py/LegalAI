"""Build small synthetic PDFs in memory, for tests and the extractor comparison only.

Not part of the public API. The generated files mimic what office suites export for Chinese text:
a Type0 font with Identity-H encoding and a ToUnicode CMap (no font program is embedded, which does
not affect text extraction), plus Helvetica for Latin runs. Every document is synthetic; callers put
`SYNTHETIC` in the title.

Page text is described in reading order; `draw_order` lets a page draw its lines in a different
content-stream order so reading-order behaviour of extractors can be measured.
"""

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal

_PAD = bytes.fromhex("28BF4E5E4E758A4164004E56FFFA01082E2E00B6D0683E802F0CA9FE6453697A")

DrawMode = Literal["tj", "glyphs", "kerned"]


@dataclass(frozen=True)
class Run:
    """A span of text in one font. `latin=True` draws it in Helvetica (ASCII only)."""

    text: str
    latin: bool = False


@dataclass(frozen=True)
class Line:
    """One visual line. `mode` controls how glyphs are written to the content stream.

    - `tj`: one `Tj` per run, natural advance (typical office export).
    - `glyphs`: every glyph absolutely positioned with its own `Tm` (typical browser/print export).
    - `kerned`: one `TJ` array per run with `kern` thousandths of an em between glyphs (justified text).
    """

    runs: tuple[Run, ...]
    x: float
    y: float
    size: float = 12.0
    mode: DrawMode = "tj"
    kern: int = -60
    char_spacing: float = 0.0
    render_mode: int = 0

    @property
    def text(self) -> str:
        return "".join(r.text for r in self.runs)


@dataclass(frozen=True)
class Page:
    """One page. `images` are (x, y, width, height) placements of an image XObject; `path` draws a
    filled rectangle (vector graphics without text)."""

    lines: tuple[Line, ...] = ()
    images: tuple[tuple[float, float, float, float], ...] = ()
    path: bool = False
    draw_order: tuple[int, ...] | None = None
    width: float = 595.0
    height: float = 842.0


FULL_PAGE_IMAGE = (0.0, 0.0, 595.0, 842.0)


def line(text: str, x: float, y: float, **kw: object) -> Line:
    """Convenience: a single-run CJK-font line."""
    return Line(runs=(Run(text),), x=x, y=y, **kw)  # type: ignore[arg-type]


@dataclass
class _Writer:
    objects: list[bytes] = field(default_factory=list)

    def reserve(self) -> int:
        self.objects.append(b"")
        return len(self.objects)

    def set(self, num: int, body: bytes) -> None:
        self.objects[num - 1] = body


def _rc4(key: bytes, data: bytes) -> bytes:
    s = list(range(256))
    j = 0
    for i in range(256):
        j = (j + s[i] + key[i % len(key)]) % 256
        s[i], s[j] = s[j], s[i]
    out = bytearray()
    i = j = 0
    for byte in data:
        i = (i + 1) % 256
        j = (j + s[i]) % 256
        s[i], s[j] = s[j], s[i]
        out.append(byte ^ s[(s[i] + s[j]) % 256])
    return bytes(out)


def _utf16_hex(ch: str) -> str:
    return ch.encode("utf-16-be").hex().upper()


def _literal(text: str) -> bytes:
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return b"(" + escaped.encode("latin-1") + b")"


def build_pdf(
    pages: Sequence[Page],
    title: str,
    *,
    to_unicode: bool = True,
    user_password: str | None = None,
) -> bytes:
    """Return the bytes of a PDF containing `pages`.

    `to_unicode=False` omits the ToUnicode CMap, producing glyphs that cannot be mapped to text.
    `user_password` encrypts the file (Standard security handler, RC4 40-bit, revision 2).
    """
    cjk_chars: list[str] = []
    for page in pages:
        for ln in page.lines:
            for run in ln.runs:
                if run.latin:
                    if not run.text.isascii():
                        raise ValueError("latin runs must be ASCII")
                    continue
                for ch in run.text:
                    if ch not in cjk_chars:
                        cjk_chars.append(ch)
    cid_of = {ch: i + 1 for i, ch in enumerate(cjk_chars)}

    def width(ch: str) -> int:
        return 500 if ord(ch) < 0x2E80 and not 0xFF00 <= ord(ch) <= 0xFFEF else 1000

    w = _Writer()
    catalog, pages_obj, info = w.reserve(), w.reserve(), w.reserve()
    type0, cidfont, descriptor, tounicode, helv = (w.reserve() for _ in range(5))
    image_obj = w.reserve()
    page_nums: list[tuple[int, int]] = [(w.reserve(), w.reserve()) for _ in pages]

    file_id = hashlib.md5(title.encode("utf-8") + str(len(pages)).encode()).digest()
    key: bytes | None = None
    encrypt_obj: int | None = None
    if user_password is not None:
        encrypt_obj = w.reserve()
        owner_pw = (b"SYNTHETIC-owner" + _PAD)[:32]
        user_pw = (user_password.encode("latin-1") + _PAD)[:32]
        o_value = _rc4(hashlib.md5(owner_pw).digest()[:5], user_pw)
        perms = -44
        key = hashlib.md5(user_pw + o_value + perms.to_bytes(4, "little", signed=True) + file_id).digest()[:5]
        u_value = _rc4(key, _PAD)
        w.set(
            encrypt_obj,
            b"<< /Filter /Standard /V 1 /R 2 /Length 40 /O <"
            + o_value.hex().encode()
            + b"> /U <"
            + u_value.hex().encode()
            + b"> /P "
            + str(perms).encode()
            + b" >>",
        )

    def crypt(num: int, data: bytes) -> bytes:
        if key is None:
            return data
        obj_key = hashlib.md5(key + num.to_bytes(3, "little") + (0).to_bytes(2, "little")).digest()[:10]
        return _rc4(obj_key, data)

    def stream(num: int, dict_extra: bytes, data: bytes) -> None:
        data = crypt(num, data)
        w.set(
            num,
            b"<< "
            + dict_extra
            + b" /Length "
            + str(len(data)).encode()
            + b" >>\nstream\n"
            + data
            + b"\nendstream",
        )

    w.set(catalog, b"<< /Type /Catalog /Pages " + f"{pages_obj} 0 R".encode() + b" >>")
    kids = b" ".join(f"{p} 0 R".encode() for p, _ in page_nums)
    w.set(pages_obj, b"<< /Type /Pages /Kids [" + kids + b"] /Count " + str(len(pages)).encode() + b" >>")
    w.set(
        info,
        b"<< /Title <"
        + crypt(info, b"\xfe\xff" + title.encode("utf-16-be")).hex().encode()
        + b"> /Producer <"
        + crypt(info, b"SYNTHETIC").hex().encode()
        + b"> >>",
    )

    widths = b" ".join(f"{cid} [{width(ch)}]".encode() for ch, cid in cid_of.items())
    w.set(
        type0,
        f"<< /Type /Font /Subtype /Type0 /BaseFont /SyntheticCJK /Encoding /Identity-H "
        f"/DescendantFonts [{cidfont} 0 R]".encode()
        + (f" /ToUnicode {tounicode} 0 R".encode() if to_unicode else b"")
        + b" >>",
    )
    w.set(
        cidfont,
        f"<< /Type /Font /Subtype /CIDFontType2 /BaseFont /SyntheticCJK "
        f"/CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> "
        f"/FontDescriptor {descriptor} 0 R /DW 1000 /CIDToGIDMap /Identity /W [".encode()
        + widths
        + b"] >>",
    )
    w.set(
        descriptor,
        b"<< /Type /FontDescriptor /FontName /SyntheticCJK /Flags 4 /FontBBox [0 -200 1000 900] "
        b"/ItalicAngle 0 /Ascent 880 /Descent -120 /CapHeight 700 /StemV 80 >>",
    )
    entries = list(cid_of.items())
    cmap = [
        "/CIDInit /ProcSet findresource begin",
        "12 dict begin",
        "begincmap",
        "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def",
        "/CMapName /Adobe-Identity-UCS def",
        "/CMapType 2 def",
        "1 begincodespacerange",
        "<0000> <FFFF>",
        "endcodespacerange",
    ]
    for start in range(0, len(entries), 100):
        chunk = entries[start : start + 100]
        cmap.append(f"{len(chunk)} beginbfchar")
        cmap.extend(f"<{cid:04X}> <{_utf16_hex(ch)}>" for ch, cid in chunk)
        cmap.append("endbfchar")
    cmap += ["endcmap", "CMapName currentdict /CMap defineresource pop", "end", "end"]
    stream(tounicode, b"", "\n".join(cmap).encode("ascii"))
    w.set(helv, b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    stream(
        image_obj,
        b"/Type /XObject /Subtype /Image /Width 8 /Height 8 /ColorSpace /DeviceGray /BitsPerComponent 8",
        bytes((x * 31 + y * 17) % 256 for y in range(8) for x in range(8)),
    )

    def cid_hex(text: str) -> bytes:
        return b"<" + "".join(f"{cid_of[ch]:04X}" for ch in text).encode() + b">"

    for page, (page_num, content_num) in zip(pages, page_nums, strict=True):
        ops: list[bytes] = []
        for ix, iy, iw, ih in page.images:
            ops.append(f"q {iw:g} 0 0 {ih:g} {ix:g} {iy:g} cm /Im1 Do Q".encode())
        if page.path:
            ops.append(b"q 0 0 0 rg 100 100 200 50 re f Q")
        order = page.draw_order if page.draw_order is not None else tuple(range(len(page.lines)))
        if sorted(order) != list(range(len(page.lines))):
            raise ValueError("draw_order must be a permutation of the page's lines")
        for idx in order:
            ln = page.lines[idx]
            if ln.mode == "glyphs":
                x = ln.x
                for run in ln.runs:
                    if run.latin:
                        raise ValueError("glyph mode supports CJK-font runs only")
                    for ch in run.text:
                        ops.append(
                            f"BT /F1 {ln.size:g} Tf 1 0 0 1 {x:.2f} {ln.y:.2f} Tm ".encode()
                            + cid_hex(ch)
                            + b" Tj ET"
                        )
                        x += ln.size * width(ch) / 1000 + ln.char_spacing
                continue
            parts = [
                f"BT {ln.render_mode} Tr {ln.char_spacing:g} Tc 1 0 0 1 {ln.x:.2f} {ln.y:.2f} Tm".encode()
            ]
            for run in ln.runs:
                font = b"/F2" if run.latin else b"/F1"
                parts.append(font + f" {ln.size:g} Tf".encode())
                encoded = _literal(run.text) if run.latin else cid_hex(run.text)
                if ln.mode == "kerned" and not run.latin:
                    glyphs = [cid_hex(ch) for ch in run.text]
                    parts.append(b"[" + f" {ln.kern} ".encode().join(glyphs) + b"] TJ")
                else:
                    parts.append(encoded + b" Tj")
            parts.append(b"ET")
            ops.append(b" ".join(parts))
        stream(content_num, b"", b"\n".join(ops))
        resources = (
            f"<< /Font << /F1 {type0} 0 R /F2 {helv} 0 R >> /XObject << /Im1 {image_obj} 0 R >> >>".encode()
        )
        w.set(
            page_num,
            f"<< /Type /Page /Parent {pages_obj} 0 R /MediaBox [0 0 {page.width:g} {page.height:g}] ".encode()
            + b"/Resources "
            + resources
            + f" /Contents {content_num} 0 R >>".encode(),
        )

    out = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
    offsets: list[int] = []
    for num, body in enumerate(w.objects, start=1):
        offsets.append(len(out))
        out += f"{num} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_at = len(out)
    out += f"xref\n0 {len(w.objects) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{off:010d} 00000 n \n".encode() for off in offsets)
    trailer = f"<< /Size {len(w.objects) + 1} /Root {catalog} 0 R /Info {info} 0 R".encode()
    trailer += b" /ID [<" + file_id.hex().encode() + b"> <" + file_id.hex().encode() + b">]"
    if encrypt_obj is not None:
        trailer += f" /Encrypt {encrypt_obj} 0 R".encode()
    out += b"trailer\n" + trailer + b" >>\nstartxref\n" + str(xref_at).encode() + b"\n%%EOF\n"
    return bytes(out)
