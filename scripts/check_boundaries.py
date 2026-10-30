"""Enforce department dependency rules (docs/ORGANIZATION.md §4).

1. A department package may import only the internal packages listed in ALLOWED.
2. Imports of another department must use its top-level package (public API), never a submodule.
"""

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORE = {
    "legalai_casefile",
    "legalai_corpus",
    "legalai_retrieval",
    "legalai_reasoning",
    "legalai_verification",
}

ALLOWED: dict[str, set[str]] = {
    "legalai_contracts": set(),
    **{pkg: {"legalai_contracts"} for pkg in CORE},
    "legalai_interface": {"legalai_contracts"} | CORE,
    "legalai_evaluation": {"legalai_contracts", "legalai_interface"} | CORE,
}


def imported_modules(tree: ast.AST) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.append((node.lineno, node.module))
    return found


def check() -> list[str]:
    errors: list[str] = []
    for dept_dir in sorted((ROOT / "departments").iterdir()):
        for py in sorted(dept_dir.rglob("*.py")):
            rel = py.relative_to(ROOT)
            own = f"legalai_{dept_dir.name}"
            for lineno, module in imported_modules(ast.parse(py.read_text(), str(py))):
                top = module.split(".")[0]
                if not top.startswith("legalai_") or top == own:
                    continue
                if top not in ALLOWED.get(own, set()):
                    errors.append(f"{rel}:{lineno}: {own} may not import {top}")
                elif top != "legalai_contracts" and module != top:
                    errors.append(f"{rel}:{lineno}: import public API '{top}', not submodule '{module}'")
    return errors


if __name__ == "__main__":
    problems = check()
    for p in problems:
        print(p)
    print(f"boundaries: {'FAIL' if problems else 'OK'} ({len(problems)} violation(s))")
    sys.exit(1 if problems else 0)
