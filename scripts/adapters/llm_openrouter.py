#!/usr/bin/env python3
"""OpenRouter adapter for osint_qa: closed-book chat completion, one shared system prompt.

Usage:
  llm_openrouter.py --model z-ai/glm-5.2 --prompt "<question>" \
      [--temperature 1.0 --top-p 0.95 --top-k 20 --max-tokens 4096]

Requires env OPENROUTER_API_KEY. Prints the final answer (reasoning stripped) to stdout.
No tools are offered to the model; reasoning is returned in a separate field and excluded
from the scored answer.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error

sys.path.insert(0, os.path.dirname(__file__))
from _llm_common import load_system_prompt, finish, emit_meta, strip_reasoning  # noqa: E402

API_URL = "https://openrouter.ai/api/v1/chat/completions"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--temperature", type=float, default=None)
    ap.add_argument("--top-p", type=float, default=None)
    ap.add_argument("--top-k", type=int, default=None)
    ap.add_argument("--max-tokens", type=int, default=4096)
    ap.add_argument("--reasoning", default="off",
                    help="off|low|medium|high|<int max_tokens>|default (omit). "
                         "Default 'off' forces a direct answer (task is direct OSINT Q&A; "
                         "prevents thinking-model loops per fine-tuning LEARNINGS).")
    ap.add_argument("--retries", type=int, default=3)
    args = ap.parse_args()

    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        sys.exit("OPENROUTER_API_KEY missing")

    body = {
        "model": args.model,
        "messages": [
            {"role": "system", "content": load_system_prompt()},
            {"role": "user", "content": args.prompt},
        ],
        "max_tokens": args.max_tokens,
    }
    if args.temperature is not None:
        body["temperature"] = args.temperature
    if args.top_p is not None:
        body["top_p"] = args.top_p
    if args.top_k is not None:
        body["top_k"] = args.top_k

    r = (args.reasoning or "").strip().lower()
    if r == "off":
        body["reasoning"] = {"enabled": False}
    elif r in ("low", "medium", "high"):
        body["reasoning"] = {"effort": r}
    elif r.isdigit():
        body["reasoning"] = {"max_tokens": int(r)}
    # "default"/"" -> omit reasoning key entirely

    data = json.dumps(body).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://buriedsignals.com",
        "X-Title": "osint-qa-benchmark",
    }

    last_err = None
    for attempt in range(1, args.retries + 1):
        try:
            req = urllib.request.Request(API_URL, data=data, headers=headers, method="POST")
            t0 = time.time()
            with urllib.request.urlopen(req, timeout=300) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            elapsed = int((time.time() - t0) * 1000)
            choice = (payload.get("choices") or [{}])[0]
            msg = choice.get("message", {}) or {}
            content = msg.get("content") or ""
            reasoning = msg.get("reasoning") or ""
            usage = payload.get("usage", {}) or {}
            # if the model spent its whole budget reasoning and returned no content,
            # surface that clearly (Phase 3 dry-run should catch and bump max-tokens)
            answer = strip_reasoning(content)
            emit_meta(model=args.model, route="openrouter", elapsed_ms=elapsed,
                      finish_reason=choice.get("finish_reason"),
                      prompt_tokens=usage.get("prompt_tokens"),
                      completion_tokens=usage.get("completion_tokens"),
                      reasoning_tokens=(usage.get("completion_tokens_details") or {}).get("reasoning_tokens"),
                      had_reasoning=bool(reasoning), empty_content=(not content.strip()),
                      temperature=args.temperature, top_p=args.top_p, top_k=args.top_k,
                      max_tokens=args.max_tokens)
            if not answer.strip():
                sys.stderr.write(f"empty content (finish={choice.get('finish_reason')}, "
                                 f"reasoning_len={len(reasoning)})\n")
                sys.exit(4)
            finish(answer)
        except urllib.error.HTTPError as e:
            errbody = e.read().decode("utf-8", "replace")[:400]
            last_err = f"HTTP {e.code}: {errbody}"
            if e.code in (429, 500, 502, 503, 520, 524) and attempt < args.retries:
                time.sleep(2 * attempt)
                continue
            break
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            last_err = f"{type(e).__name__}: {e}"
            if attempt < args.retries:
                time.sleep(2 * attempt)
                continue
            break
    sys.exit(f"openrouter failed for {args.model}: {last_err}")


if __name__ == "__main__":
    main()
