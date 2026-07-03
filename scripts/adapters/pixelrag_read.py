"""PixelRAG pixel-native scraping adapter.

Renders the page to screenshot tiles with pixelshot, then has a vision
model (via OpenRouter) read the images and extract the task-relevant text.
This mirrors PixelRAG's intended usage: retrieval/reading happens over
rendered pixels, not parsed HTML. The extraction prompt uses only the
case prompt, never probe values.
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

MAX_TILES = 8
DEFAULT_MODEL = "google/gemini-2.5-flash"


def main() -> int:
    if len(sys.argv) != 6:
        print(
            "usage: pixelrag_read.py <url> <output_dir> <timeout_seconds> <case_id> <prompt>",
            file=sys.stderr,
        )
        return 2
    url, output_dir, timeout_seconds, case_id, prompt = sys.argv[1:6]
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        print("missing OPENROUTER_API_KEY", file=sys.stderr)
        return 2
    model = os.environ.get("PIXELRAG_VLM_MODEL", DEFAULT_MODEL)

    tiles_root = Path(output_dir) / f"pixelrag-tiles-{case_id}"
    render = subprocess.run(
        ["uvx", "--from", "pixelrag", "pixelshot", url, "--output", str(tiles_root)],
        capture_output=True,
        text=True,
        timeout=max(30, int(float(timeout_seconds)) - 60),
    )
    if render.stderr:
        print(render.stderr[-2000:], file=sys.stderr)
    tiles = sorted(tiles_root.glob("**/tile_*.jpg")) + sorted(tiles_root.glob("**/tile_*.png"))
    if render.returncode != 0 or not tiles:
        print(f"pixelshot failed (exit {render.returncode}, {len(tiles)} tiles)", file=sys.stderr)
        return 1
    if len(tiles) > MAX_TILES:
        print(
            f"[pixelrag] truncating {len(tiles)} tiles to first {MAX_TILES}",
            file=sys.stderr,
        )
        tiles = tiles[:MAX_TILES]

    content: list[dict] = [
        {
            "type": "text",
            "text": (
                "You are reading a web page rendered as screenshot images, in order. "
                f"Task: {prompt} "
                "Faithfully transcribe all text content relevant to the task - headings, "
                "names, numbers, dates, labels, table rows, and link texts - as plain text. "
                "Do not summarize away specifics; preserve exact wording where visible."
            ),
        }
    ]
    for tile in tiles:
        encoded = base64.b64encode(tile.read_bytes()).decode("ascii")
        suffix = "png" if tile.suffix == ".png" else "jpeg"
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/{suffix};base64,{encoded}"},
            }
        )

    payload = json.dumps(
        {"model": model, "messages": [{"role": "user", "content": content}]}
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as res:
            body = json.loads(res.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        print(exc.read().decode("utf-8", errors="replace")[:2000], file=sys.stderr)
        return 1
    usage = body.get("usage") or {}
    print(
        f"[pixelrag metrics] model={model} tiles={len(tiles)} "
        f"prompt_tokens={usage.get('prompt_tokens')} completion_tokens={usage.get('completion_tokens')}",
        file=sys.stderr,
    )
    choices = body.get("choices") or []
    text = (choices[0].get("message") or {}).get("content") if choices else None
    if not text:
        print(f"no completion returned: {json.dumps(body)[:800]}", file=sys.stderr)
        return 1
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
