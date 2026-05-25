"""Context-window inspector — centrepiece prop for angle 02.

Tails a Claude Code session log, tokenises each turn's context with the official
anthropic tokenizer, and renders a live stacked bar in a terminal — system
prompt / AGENTS.md / skill metadata / tool definitions / codebase chunks /
conversation — with a percentage gauge against the working ceiling and coloured
bands at the smart→warm (~30%) and warm→dumb (~40%) thresholds.

This file is a stub. Implement before rehearsal. Target ~150 LOC total.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


WORKING_CEILING_TOKENS = 200_000
SMART_THRESHOLD = 0.30  # below this: full capability
WARM_THRESHOLD = 0.40  # above this: measurable degradation


@dataclass
class TurnComposition:
    """One turn's context, broken down by source."""

    system_prompt: int
    agents_md: int
    skill_metadata: int
    tool_definitions: int
    codebase_chunks: int
    conversation: int

    @property
    def total(self) -> int:
        return (
            self.system_prompt + self.agents_md + self.skill_metadata
            + self.tool_definitions + self.codebase_chunks + self.conversation
        )

    @property
    def fill_fraction(self) -> float:
        return self.total / WORKING_CEILING_TOKENS

    def zone(self) -> str:
        f = self.fill_fraction
        if f < SMART_THRESHOLD:
            return "smart"
        if f < WARM_THRESHOLD:
            return "warm"
        return "dumb"


def model_fingerprint() -> dict[str, str]:
    """Read model ID + version + temperature + max-tokens from the active session.

    TODO: read from Claude Code's session metadata. Hardcode from env or config
    until then.
    """
    return {
        "model": "claude-sonnet-4-6",
        "version": "TODO",
        "temperature": "0.0",
        "max_tokens": str(WORKING_CEILING_TOKENS),
    }


def tail_session_log(log_path: Path) -> Iterator[dict]:
    """Yield each new turn record as it appears in the session log.

    TODO: implement against Claude Code's actual session log format. Either tail
    the local JSONL log or wrap a Claude Agent SDK loop directly.
    """
    raise NotImplementedError("hook up to Claude Code session log before rehearsal")


def tokenise_turn(turn: dict) -> TurnComposition:
    """Use the official anthropic tokenizer to count tokens per source within a turn.

    TODO: call anthropic.tokenize or equivalent on each of the six source slices.
    """
    raise NotImplementedError("hook up to anthropic.tokenize before rehearsal")


def render_stacked_bar(composition: TurnComposition, width: int = 60) -> str:
    """ASCII stacked bar with single-character glyphs per source."""
    total = composition.total
    if total == 0:
        return "[" + " " * width + "]"
    sources = [
        ("system", composition.system_prompt, "S"),
        ("agents_md", composition.agents_md, "A"),
        ("skill_metadata", composition.skill_metadata, "K"),
        ("tool_definitions", composition.tool_definitions, "T"),
        ("codebase_chunks", composition.codebase_chunks, "C"),
        ("conversation", composition.conversation, "M"),
    ]
    chars = []
    for _, count, glyph in sources:
        chars.extend([glyph] * round((count / total) * width))
    chars = chars[:width] + [" "] * (width - len(chars))
    return "[" + "".join(chars) + "]"


def render_gauge(composition: TurnComposition) -> str:
    pct = composition.fill_fraction * 100
    zone = composition.zone()
    colour = {"smart": "\033[32m", "warm": "\033[33m", "dumb": "\033[31m"}[zone]
    return f"{colour}{pct:5.1f}%  [{zone}]\033[0m"


def render_header() -> str:
    fp = model_fingerprint()
    return (
        f"model={fp['model']}  version={fp['version']}  "
        f"temp={fp['temperature']}  ceiling={WORKING_CEILING_TOKENS}"
    )


def run(log_path: Path) -> None:
    """Main loop. Render header once, then bar+gauge on each new turn."""
    print(render_header())
    print("-" * 80)
    for turn in tail_session_log(log_path):
        composition = tokenise_turn(turn)
        print(f"{render_stacked_bar(composition)}  {render_gauge(composition)}")
        time.sleep(0.05)


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("usage: context_window_inspector.py <claude-code-session.jsonl>")
        sys.exit(2)
    run(Path(sys.argv[1]))
