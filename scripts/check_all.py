"""Run every repository check. Exit non-zero if any fails. This is the definition of 'green'."""

import subprocess
import sys

DEPARTMENTS = [
    "contracts",
    "casefile",
    "corpus",
    "retrieval",
    "reasoning",
    "verification",
    "evaluation",
    "interface",
]

CHECKS = [
    ["python", "scripts/check_boundaries.py"],
    ["python", "scripts/check_docs.py"],
    ["ruff", "check", "."],
    ["ruff", "format", "--check", "."],
    ["mypy", *(f"-p=legalai_{d}" for d in DEPARTMENTS)],
    ["mypy", "scripts"],
    ["pytest", "-q"],
]

if __name__ == "__main__":
    failed = []
    for cmd in CHECKS:
        print(f"\n$ {' '.join(cmd)}", flush=True)
        if subprocess.run(cmd).returncode != 0:
            failed.append(" ".join(cmd))
    print("\n" + ("ALL CHECKS PASSED" if not failed else "FAILED:\n  " + "\n  ".join(failed)))
    sys.exit(1 if failed else 0)
