"""Shared helpers for the osint_qa model adapters.

Every adapter: takes a --prompt (the question), prepends the SAME system prompt
(../fine-tuning/system-prompt.md) for fairness, calls its backend closed-book (no
tools/network for the model itself), strips reasoning traces, prints the final answer to
stdout, and exits nonzero on failure. Sampling params and token counts are emitted to
stderr as a JSON line so the runner/report can record them.
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

# benchmarks/ is parents[2] of scripts/adapters/_llm_common.py
BENCH_ROOT = Path(__file__).resolve().parents[2]
SYSTEM_PROMPT_PATH = (BENCH_ROOT.parent / "fine-tuning" / "system-prompt.md")


def load_system_prompt() -> str:
    txt = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip()
    if not txt:
        raise SystemExit("system prompt is empty: " + str(SYSTEM_PROMPT_PATH))
    return txt


_THINK = re.compile(r"<(think|thinking|reasoning)>.*?</\1>", re.S | re.I)
_OPEN_THINK = re.compile(r"<(think|thinking|reasoning)>.*\Z", re.S | re.I)


def strip_reasoning(text: str) -> str:
    """Remove inline chain-of-thought blocks; keep only the final answer."""
    if not text:
        return text
    out = _THINK.sub("", text)
    # a lone unterminated <think> (truncated) — drop everything from it on
    out = _OPEN_THINK.sub("", out)
    return out.strip()


def emit_meta(**kwargs) -> None:
    """One JSON line to stderr with run metadata (model, params, token counts)."""
    sys.stderr.write("LLM_META " + json.dumps(kwargs, default=str) + "\n")
    sys.stderr.flush()


def finish(answer: str) -> None:
    answer = strip_reasoning(answer or "")
    if not answer.strip():
        # empty answer is a failure the runner should see
        sys.stderr.write("empty answer after reasoning strip\n")
        sys.exit(3)
    sys.stdout.write(answer)
    sys.stdout.flush()
    sys.exit(0)
