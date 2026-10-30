# ruff: noqa: RUF001 - full-width CJK punctuation is the data under test, not a typo.
"""Synthetic PDF fixture corpus (jurisdiction ZZ) shared by the tests and the extractor comparison.

Each fixture lists the true lines of every page in reading order. All text is invented; it is not
taken from any real contract, case or statute.
"""

from dataclasses import dataclass

from legalai_casefile._synthetic_pdf import DrawMode, Line, Page, Run, line

ZH_PAGES: tuple[tuple[str, ...], ...] = (
    (
        "SYNTHETIC 买卖合同（ZZ 法域测试样本）",
        "甲方（卖方）：示例甲有限公司；乙方（买方）：示例乙有限公司。",
        "第一条　标的物：“示例货物”一批，数量见附件《清单》。",
        "第二条　价款：人民币壹拾万元整（¥100,000.00），含税。",
    ),
    (
        "第三条　交付：甲方应于约定期限内交付，逾期的，按日支付违约金。",
        "第四条　验收：乙方收货后十日内提出书面异议【附照片】；否则视为合格。",
        "第五条　争议解决：协商不成的，提交合同签订地法院诉讼解决！",
    ),
    (
        "第六条　其他：本合同一式两份、双方各执一份，自签字盖章之日起生效？",
        "甲方（签章）：　　　　乙方（签章）：",
        "日期：２０２６年１０月３０日",
    ),
)


@dataclass(frozen=True)
class Fixture:
    name: str
    pages: tuple[Page, ...]
    truth: tuple[tuple[str, ...], ...]
    """True lines per page, in reading order."""


def zh_pages(mode: DrawMode = "tj", *, kern: int = -60, char_spacing: float = 0.0) -> tuple[Page, ...]:
    return tuple(
        Page(
            lines=tuple(
                line(t, 72, 770 - 24 * i, mode=mode, kern=kern, char_spacing=char_spacing)
                for i, t in enumerate(texts)
            )
        )
        for texts in ZH_PAGES
    )


def _mixed_line(y: float, *parts: tuple[str, bool]) -> Line:
    return Line(runs=tuple(Run(t, latin) for t, latin in parts), x=72, y=y)


def mixed_pages() -> tuple[Page, ...]:
    """Mixed zh/en receipt: Latin runs in Helvetica, Chinese in the CJK font, on the same line."""
    return (
        Page(
            lines=(
                _mixed_line(770, ("Email ", True), ("回执", False), (" / Receipt No. ZZ-2026-001", True)),
                _mixed_line(
                    746, ("付款人：", False), ("SYNTHETIC Trading Co., Ltd.", True), ("（简称“甲方”）", False)
                ),
                _mixed_line(722, ("金额：", False), ("USD 1,234.56", True), ("，即人民币捌仟元。", False)),
            )
        ),
        Page(
            lines=(
                _mixed_line(
                    770,
                    ("Clause 7.2 ", True),
                    ("约定：", False),
                    ("Seller shall deliver by 2026-11-30.", True),
                ),
                _mixed_line(746, ("全角字母ＡＢＣ与半角ABC并存；", False), ("end.", True)),
            )
        ),
    )


def reversed_stream_pages() -> tuple[Page, ...]:
    """Lines drawn bottom-to-top in the content stream (visual order top-to-bottom)."""
    return tuple(Page(lines=p.lines, draw_order=tuple(reversed(range(len(p.lines))))) for p in zh_pages())


TWO_COLUMN_LEFT = ("左栏第一行：甲方义务。", "左栏第二行：按期交货。", "左栏第三行：保证质量。")
TWO_COLUMN_RIGHT = ("右栏第一行：乙方义务。", "右栏第二行：按期付款。", "右栏第三行：及时验收。")


def two_column_pages() -> tuple[Page, ...]:
    lines = tuple(line(t, 60, 770 - 20 * i) for i, t in enumerate(TWO_COLUMN_LEFT)) + tuple(
        line(t, 320, 770 - 20 * i) for i, t in enumerate(TWO_COLUMN_RIGHT)
    )
    return (Page(lines=lines),)


TABLE_ROWS = (
    ("品名", "数量", "单价"),
    ("示例货物A", "10件", "¥1,000.00"),
    ("示例货物B", "２０件", "¥2,000.00"),
)


def table_pages() -> tuple[Page, ...]:
    """A receipt table: every cell its own text object, drawn row by row."""
    return (
        Page(
            lines=tuple(
                line(cell, 72 + 150 * j, 700 - 20 * i)
                for i, row in enumerate(TABLE_ROWS)
                for j, cell in enumerate(row)
            )
        ),
    )


ASTRAL_LINES = ("当事人：张𠀀、李𪚥（扩展B区汉字）。", "第二行。")


def astral_pages() -> tuple[Page, ...]:
    return (Page(lines=tuple(line(t, 72, 770 - 24 * i) for i, t in enumerate(ASTRAL_LINES))),)


def _truth(pages: tuple[Page, ...]) -> tuple[tuple[str, ...], ...]:
    return tuple(tuple(ln.text for ln in p.lines) for p in pages)


def corpus() -> tuple[Fixture, ...]:
    """Positive fixtures. For the table the truth joins cells with one space (the PDF defines no
    whitespace between cells; only the non-whitespace order is meaningful there)."""
    fixtures = [
        ("zh_tj_3pages", zh_pages()),
        ("zh_glyph_positioned", zh_pages("glyphs")),
        ("zh_kerned_small(-60)", zh_pages("kerned", kern=-60)),
        ("zh_kerned_wide(-250)", zh_pages("kerned", kern=-250)),
        ("zh_char_spacing(Tc=3)", zh_pages(char_spacing=3.0)),
        ("mixed_zh_en_fonts", mixed_pages()),
        ("zh_reverse_stream_order", reversed_stream_pages()),
        ("zh_two_column", two_column_pages()),
        ("zh_table_rows", table_pages()),
        ("zh_astral_ext_b", astral_pages()),
    ]
    out = []
    for name, pages in fixtures:
        truth = _truth(pages)
        if name == "zh_table_rows":
            truth = (tuple(" ".join(row) for row in TABLE_ROWS),)
        out.append(Fixture(name, pages, truth))
    return tuple(out)
