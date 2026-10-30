"""Regenerate the externally generated fixtures for REQ-PMO-0009 (macOS only).

    uv run python departments/casefile/tools/make_external_fixtures.py

Writes synthetic ZZ Chinese text to `tests/fixtures/external/zz-radicals-source.txt` and converts it with
macOS `cupsfilter` (text -> PDF, embeds a subset system CJK font) and `textutil` (text -> DOCX).
Every line is invented and unique (it carries its own line number); no real contract, case or statute
is used. Many lines contain ideographs that have Kangxi-radical twins (人 入 月 言 日 一 口 心 手 水 ...),
which is what exposes font maps that point glyphs at radical code points.
"""

import subprocess
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "external"

SUBJECTS = ("出借人", "借款人", "担保人", "投资人", "证人", "代理人", "收款人", "承租人")
ACTIONS = (
    "应于每月十日前支付本月利息",
    "收入的款项应当入账并出具收据",
    "提供的证言须与书面记录一致",
    "不得以口头方式变更本合同",
    "应当尽心履行告知义务",
    "可以用手写方式签字确认",
    "支付水电费及物业服务费",
    "在山区项目中承担运输工作",
)
TAILS = ("。", "；", "，并书面通知对方。", "（详见附件一）。", "，逾期按日计息！", "？")


def source_lines() -> list[str]:
    lines = ["SYNTHETIC ZZ 测试文本：借款与担保（仅供测试）"]
    n = 1
    while len(lines) < 120:
        subj = SUBJECTS[n % len(SUBJECTS)]
        act = ACTIONS[(n * 3) % len(ACTIONS)]
        tail = TAILS[n % len(TAILS)]
        lines.append(f"第{n:03d}行　ZZ{subj}{act}{tail}")
        n += 1
    return lines


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    src = OUT / "zz-radicals-source.txt"
    src.write_text("\n".join(source_lines()) + "\n", encoding="utf-8")
    pdf = subprocess.run(
        ["cupsfilter", "-i", "text/plain", "-m", "application/pdf", str(src)],
        check=True,
        capture_output=True,
    ).stdout
    (OUT / "zz-radicals-cupsfilter.pdf").write_bytes(pdf)
    subprocess.run(
        ["textutil", "-convert", "docx", "-output", str(OUT / "zz-radicals-textutil.docx"), str(src)],
        check=True,
    )
    # Page truth from an independent extractor (PDFKit), so page_of is not checked against pypdf itself.
    truth = subprocess.run(
        [
            "osascript",
            "-l",
            "JavaScript",
            str(Path(__file__).with_name("pdfkit_page_numbers.js")),
            str(OUT / "zz-radicals-cupsfilter.pdf"),
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    (OUT / "zz-radicals-cupsfilter.pages.json").write_text(truth.strip() + "\n", encoding="utf-8")
    print(
        f"wrote {src.name}, zz-radicals-cupsfilter.pdf ({len(pdf)} bytes), "
        "zz-radicals-cupsfilter.pages.json, zz-radicals-textutil.docx"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
