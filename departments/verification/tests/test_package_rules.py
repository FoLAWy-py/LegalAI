"""Package-level rules: no env reads (REQ-PMO-0004 §2.4), Phase A has no model access, prompts are valid."""

import ast
from pathlib import Path

import pytest

import legalai_verification
from legalai_contracts import Verifier
from legalai_verification import IndependentVerifier
from legalai_verification._prompts import ALL_PROMPTS, PromptError, load_prompts, parse_prompt
from legalai_verification._testkit import ExplodingModel, build_world

PACKAGE = Path(legalai_verification.__file__).parent
SOURCES = sorted(PACKAGE.rglob("*.py"))


def _tree(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"), str(path))


def test_public_api() -> None:
    assert set(legalai_verification.__all__) == {
        "VERIFIER_VERSION",
        "IndependentVerifier",
        "JsonChatModel",
        "ModelCallError",
        "OpenAICompatibleChatModel",
        "VerificationModelConfig",
    }
    for name in legalai_verification.__all__:
        assert getattr(legalai_verification, name).__doc__ or name == "VERIFIER_VERSION"


def test_implements_verifier_port() -> None:
    world = build_world()
    verifier = IndependentVerifier(source_store=world.sources, case_store=world.cases, model=ExplodingModel())
    assert isinstance(verifier, Verifier)


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: p.name)
def test_package_reads_no_environment_variables(path: Path) -> None:
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Attribute):
            assert node.attr not in {"environ", "getenv", "environb", "putenv"}, f"{path.name}:{node.lineno}"
        if isinstance(node, ast.ImportFrom):
            assert node.module not in {"dotenv"}, path.name
            if node.module == "os":
                assert not {a.name for a in node.names} & {"environ", "getenv", "environb"}, path.name
        if isinstance(node, ast.Import):
            assert all(a.name != "dotenv" for a in node.names), path.name


def test_phase_a_module_has_no_model_access() -> None:
    tree = _tree(PACKAGE / "_phase_a.py")
    imported = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module} | {
        a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names
    }
    assert imported <= {"collections.abc", "dataclasses", "legalai_contracts"}


def test_all_prompts_load_with_headers() -> None:
    prompts = load_prompts()
    assert set(prompts) == set(ALL_PROMPTS)
    ids = {p.prompt_id for p in prompts.values()}
    assert len(ids) == len(ALL_PROMPTS)
    for prompt in prompts.values():
        assert prompt.prompt_id.startswith("verification.")
        assert prompt.owner == "verification"
        assert prompt.version == "1.0.0"
        assert "JSON" in prompt.text  # required by OpenAI-compatible JSON mode
        assert "---" not in prompt.text.splitlines()[0]


@pytest.mark.parametrize(
    "raw",
    [
        "no header",
        "---\nprompt_id: x\nversion: 1\nowner: verification\n---\nbody",  # no changelog
        "---\nprompt_id: x\nversion: 1\nowner: reasoning\nchangelog:\n  - 1\n---\nbody",
        "---\nprompt_id: x\nowner: verification\nchangelog:\n  - 1\n---\nbody",
        "---\nprompt_id: x\nversion: 1\nowner: verification\nchangelog:\n  - 1\n---\n   ",
    ],
)
def test_broken_prompt_headers_are_rejected(raw: str) -> None:
    with pytest.raises(PromptError):
        parse_prompt(raw)
