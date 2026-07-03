#!/usr/bin/env python3
"""Claude CLI adapter for osint_qa: closed-book `claude -p`, tools disabled.

Usage:
  llm_claude_cli.py --model claude-fable-5 --prompt "<question>" [--max-tokens 4096]

Uses `claude -p` in print mode with the shared OSINT system prompt (--system-prompt,
which REPLACES the default Claude Code prompt) and NO tools (--allowed-tools ""). Verifies
from the JSON transcript that zero tool calls occurred; a run with any tool use fails so
the runner discards it (fairness contract). Prints the final answer to stdout.
"""
from __future__ import annotations
import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
from _llm_common import load_system_prompt, finish, emit_meta  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--max-tokens", type=int, default=4096)  # recorded, not enforced by CLI
    ap.add_argument("--timeout", type=int, default=280)
    args = ap.parse_args()

    system = load_system_prompt()
    cmd = [
        "claude", "-p", args.prompt,
        "--model", args.model,
        "--system-prompt", system,
        "--allowed-tools", "",              # empty allowlist => no tools usable
        "--output-format", "json",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=args.timeout)
    except subprocess.TimeoutExpired:
        sys.exit(f"claude -p timed out after {args.timeout}s for {args.model}")
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr[:600])
        sys.exit(f"claude -p exit {proc.returncode} for {args.model}")

    raw = proc.stdout.strip()
    answer = ""
    tool_calls = 0
    usage = {}
    try:
        obj = json.loads(raw)
        # print/json shape: {"type":"result","subtype":"success","result":"...","usage":{...},...}
        if isinstance(obj, dict):
            answer = obj.get("result") or obj.get("text") or ""
            usage = obj.get("usage", {}) or {}
            # detect any tool use anywhere in the transcript if present
            blob = json.dumps(obj)
            tool_calls = blob.count('"type":"tool_use"') + blob.count('"type": "tool_use"')
        elif isinstance(obj, list):
            for m in obj:
                blob = json.dumps(m)
                tool_calls += blob.count('"tool_use"')
                if m.get("type") == "result":
                    answer = m.get("result", "")
    except json.JSONDecodeError:
        answer = raw  # fall back to raw text

    emit_meta(model=args.model, route="claude_cli", tool_calls=tool_calls,
              input_tokens=usage.get("input_tokens"), output_tokens=usage.get("output_tokens"))
    if tool_calls > 0:
        sys.exit(f"fairness violation: {tool_calls} tool call(s) in {args.model} transcript")
    finish(answer)


if __name__ == "__main__":
    main()
