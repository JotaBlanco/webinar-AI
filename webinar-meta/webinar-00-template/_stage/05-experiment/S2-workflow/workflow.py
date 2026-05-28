"""S2 — hand-decomposed workflow scaffold (TEMPLATE).

NC-6 tier 1 (workflow). Same question as S1, decomposed into 4-5 focused LLM
calls, each with a tight system prompt and exactly one tool. Deterministic
control flow; cheap; attributable per step.

This file is a stub — implement before rehearsal. Replace step bodies with
your domain's decomposition. Target ~150 LOC total.

Pattern: each step is one LLM call with a 5-10 line system prompt and one tool.
The final step produces the markdown answer.
"""
from __future__ import annotations

import sys
from pathlib import Path


def step_one(question: str) -> dict:
    """LLM call #1: parse the question, extract the named artifact, call the load tool."""
    raise NotImplementedError("implement before rehearsal")


def step_two(question: str, prior: dict) -> dict:
    """LLM call #2: build on step 1's output."""
    raise NotImplementedError("implement before rehearsal")


def step_three(prior: dict) -> dict:
    """LLM call #3: ..."""
    raise NotImplementedError("implement before rehearsal")


def step_four(question: str, prior: dict) -> dict:
    """LLM call #4: ..."""
    raise NotImplementedError("implement before rehearsal")


def step_write_report(question: str, *prior: dict) -> str:
    """Final LLM call: produce the markdown answer."""
    raise NotImplementedError("implement before rehearsal")


def run(question_path: Path) -> str:
    question = question_path.read_text()
    s1 = step_one(question)
    s2 = step_two(question, s1)
    s3 = step_three(s2)
    s4 = step_four(question, s3)
    return step_write_report(question, s1, s2, s3, s4)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: workflow.py <path-to-question.md>")
        sys.exit(2)
    print(run(Path(sys.argv[1])))
