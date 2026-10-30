"""Validate document front matter and filenames (docs/standards/documentation.md §3)."""

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DEPARTMENTS = {
    "architecture",
    "casefile",
    "corpus",
    "retrieval",
    "reasoning",
    "verification",
    "evaluation",
    "interface",
    "pmo",
}
REQ_PREFIX = {d: ("ARCH" if d == "architecture" else d.upper()) for d in DEPARTMENTS}
STATUS = {
    "REQ": {"draft", "open", "accepted", "rejected", "in-progress", "delivered", "verified", "closed"},
    "ADR": {"proposed", "accepted", "rejected", "superseded"},
    "OTHER": {"draft", "active", "deprecated"},
}
BASE_KEYS = {"id", "owner", "status", "updated"}
EXTRA_KEYS = {
    "REQ": {"title", "from", "to", "priority", "created", "depends_on"},
    "ADR": {"title", "deciders"},
    "OTHER": set(),
}


def front_matter(path: Path) -> dict[str, object] | None:
    text = path.read_text()
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    return yaml.safe_load(match.group(1)) if match else None


def kind_of(path: Path) -> str:
    if path.parent.name == "requirements" and path.name.startswith("REQ-"):
        return "REQ"
    if path.parent.name == "adr":
        return "ADR"
    return "OTHER"


def check_file(path: Path) -> list[str]:
    rel = path.relative_to(ROOT)
    meta = front_matter(path)
    if meta is None:
        return [f"{rel}: missing YAML front matter"]
    kind = kind_of(path)
    errors = [f"{rel}: missing key '{k}'" for k in sorted(BASE_KEYS | EXTRA_KEYS[kind]) if k not in meta]
    if meta.get("status") not in STATUS[kind]:
        errors.append(f"{rel}: status '{meta.get('status')}' not in {sorted(STATUS[kind])}")
    doc_id = str(meta.get("id", ""))
    if kind in {"REQ", "ADR"} and not path.name.startswith(doc_id + "-"):
        errors.append(f"{rel}: filename must start with id '{doc_id}-'")
    if kind == "REQ":
        for key in ("from", "to", "owner"):
            if meta.get(key) not in DEPARTMENTS:
                errors.append(f"{rel}: '{key}' must be one of {sorted(DEPARTMENTS)}")
        issuer = meta.get("from")
        if issuer in REQ_PREFIX and not re.fullmatch(rf"REQ-{REQ_PREFIX[issuer]}-\d{{4}}", doc_id):
            errors.append(f"{rel}: id must be REQ-{REQ_PREFIX[issuer]}-NNNN for issuer '{issuer}'")
        if meta.get("priority") not in {"P0", "P1", "P2", "P3"}:
            errors.append(f"{rel}: priority must be P0-P3")
    if kind == "ADR" and not re.fullmatch(r"ADR-\d{4}", doc_id):
        errors.append(f"{rel}: id must be ADR-NNNN")
    return errors


def check_claude_shims() -> list[str]:
    """CLAUDE.md files may only import other files; rules live in AGENTS.md."""
    errors = []
    for shim in [ROOT / "CLAUDE.md", *sorted((ROOT / "departments").glob("*/CLAUDE.md"))]:
        rel = shim.relative_to(ROOT)
        if not (shim.parent / "AGENTS.md").is_file():
            errors.append(f"{rel}: sibling AGENTS.md missing")
        lines = [ln for ln in shim.read_text().splitlines() if ln.strip()]
        if "@AGENTS.md" not in lines or any(not ln.startswith("@") for ln in lines):
            errors.append(f"{rel}: must contain only @import lines, including @AGENTS.md")
    return errors


def targets() -> list[Path]:
    docs = [p for p in (ROOT / "docs").rglob("*.md") if "templates" not in p.parts]
    return sorted(docs + list((ROOT / "departments").glob("*/CHARTER.md")))


if __name__ == "__main__":
    problems = [e for p in targets() for e in check_file(p)] + check_claude_shims()
    for p in problems:
        print(p)
    print(f"docs: {'FAIL' if problems else 'OK'} ({len(problems)} problem(s))")
    sys.exit(1 if problems else 0)
