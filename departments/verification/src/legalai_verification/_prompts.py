"""Loads verification's prompt files (code standard §3.7, documentation standard §5)."""

import re
from dataclasses import dataclass
from importlib import resources
from types import MappingProxyType

_HEADER = re.compile(r"\A---\n(?P<header>.*?)\n---\n(?P<body>.*)\Z", re.DOTALL)
_REQUIRED_KEYS = ("prompt_id", "version", "owner")

ELEMENT_PROMPT = "law_establishes_element.md"
LINK_PROMPT = "evidence_bears_on_element.md"
CLAIM_PROMPT = "claim_supported_by_sources.md"
INFERENCE_PROMPT = "inference_follows_from_premises.md"
ALL_PROMPTS = (ELEMENT_PROMPT, LINK_PROMPT, CLAIM_PROMPT, INFERENCE_PROMPT)


class PromptError(Exception):
    """A prompt file is missing or its header is invalid."""


@dataclass(frozen=True)
class Prompt:
    prompt_id: str
    version: str
    owner: str
    text: str

    @property
    def ref(self) -> str:
        return f"{self.prompt_id}@{self.version}"


def parse_prompt(raw: str) -> Prompt:
    match = _HEADER.match(raw)
    if match is None:
        raise PromptError("prompt file must start with a '---' header block")
    fields: dict[str, str] = {}
    for line in match.group("header").splitlines():
        key, sep, value = line.partition(":")
        if sep and not line.startswith((" ", "\t", "-")):
            fields[key.strip()] = value.strip()
    missing = [k for k in _REQUIRED_KEYS if not fields.get(k)]
    if missing:
        raise PromptError(f"prompt header missing {missing}")
    if "changelog" not in fields:
        raise PromptError("prompt header missing changelog")
    if fields["owner"] != "verification":
        raise PromptError("verification prompts must be owned by verification")
    body = match.group("body").strip()
    if not body:
        raise PromptError("prompt body is empty")
    return Prompt(prompt_id=fields["prompt_id"], version=fields["version"], owner=fields["owner"], text=body)


def load_prompts() -> MappingProxyType[str, Prompt]:
    """Read every prompt shipped in `legalai_verification/prompts/`. Fails loudly if any is broken."""
    folder = resources.files("legalai_verification").joinpath("prompts")
    loaded = {name: parse_prompt(folder.joinpath(name).read_text(encoding="utf-8")) for name in ALL_PROMPTS}
    return MappingProxyType(loaded)
