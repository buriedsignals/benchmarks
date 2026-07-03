#!/usr/bin/env python3
"""Runpod (vLLM OpenAI-compatible) adapter for osint_qa: tuned models + their true bases.

The pod/endpoint URL is dynamic, so it is NOT hardcoded in tools.json. The pod manager
(scripts/runpod_serve.py) writes results/osint_qa/runpod_endpoints.json mapping the HF repo
to a live base URL. This adapter looks the model up there and does a closed-book chat
completion with the shared system prompt.

Usage:
  llm_runpod.py --model tomvaillant/qwen3.5-9b-abliterated-journalist-merged --prompt "..."
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from _llm_common import load_system_prompt, finish, emit_meta, strip_reasoning  # noqa: E402

ENDPOINTS = Path(__file__).resolve().parents[2] / "results" / "osint_qa" / "runpod_endpoints.json"


def resolve_base_url(model: str) -> tuple[str, str]:
    if not ENDPOINTS.exists():
        sys.exit(f"no runpod endpoints registry at {ENDPOINTS}; bring a pod up first")
    reg = json.loads(ENDPOINTS.read_text())
    ent = reg.get(model)
    if not ent:
        sys.exit(f"model {model} not registered in {ENDPOINTS} (available: {list(reg)})")
    if isinstance(ent, str):
        return ent.rstrip("/"), model
    return ent["base_url"].rstrip("/"), ent.get("served_model", model)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="HF repo id (registry key)")
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--temperature", type=float, default=None)
    ap.add_argument("--top-p", type=float, default=None)
    ap.add_argument("--top-k", type=int, default=None)
    ap.add_argument("--max-tokens", type=int, default=4096)
    ap.add_argument("--no-think", action="store_true",
                    help="append Qwen /no_think and set enable_thinking=false via chat template kwargs")
    ap.add_argument("--retries", type=int, default=3)
    args = ap.parse_args()

    base_url, served = resolve_base_url(args.model)
    system = load_system_prompt()
    user = args.prompt
    body = {
        "model": served,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": args.max_tokens,
    }
    if args.temperature is not None: body["temperature"] = args.temperature
    if args.top_p is not None: body["top_p"] = args.top_p
    if args.top_k is not None: body["top_k"] = args.top_k
    # vLLM: disable Qwen/Gemma thinking via chat-template kwarg when requested
    if args.no_think:
        body["chat_template_kwargs"] = {"enable_thinking": False}

    data = json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json", "Authorization": "Bearer x"}
    url = base_url + "/v1/chat/completions"

    last = None
    for attempt in range(1, args.retries + 1):
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            t0 = time.time()
            with urllib.request.urlopen(req, timeout=300) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            elapsed = int((time.time() - t0) * 1000)
            choice = (payload.get("choices") or [{}])[0]
            msg = choice.get("message", {}) or {}
            content = msg.get("content") or ""
            usage = payload.get("usage", {}) or {}
            answer = strip_reasoning(content)
            emit_meta(model=args.model, route="runpod", base_url=base_url, elapsed_ms=elapsed,
                      finish_reason=choice.get("finish_reason"),
                      prompt_tokens=usage.get("prompt_tokens"),
                      completion_tokens=usage.get("completion_tokens"),
                      empty_content=(not content.strip()), max_tokens=args.max_tokens,
                      no_think=args.no_think)
            if not answer.strip():
                sys.stderr.write(f"empty content (finish={choice.get('finish_reason')})\n")
                sys.exit(4)
            finish(answer)
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}: {e.read().decode('utf-8','replace')[:300]}"
            if e.code in (429, 500, 502, 503) and attempt < args.retries:
                time.sleep(3 * attempt); continue
            break
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            last = f"{type(e).__name__}: {e}"
            if attempt < args.retries:
                time.sleep(3 * attempt); continue
            break
    sys.exit(f"runpod adapter failed for {args.model}: {last}")


if __name__ == "__main__":
    main()
