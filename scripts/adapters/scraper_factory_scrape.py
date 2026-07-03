"""Tow Center Scraper Factory adapter.

Generates a Playwright scraper for the case URL with the factory's LLM
loop (once per case; generated scrapers persist under
bin/scraper-factory/scrapers/), then executes it and prints the extracted
records. The LLM backend is OpenRouter via the OpenAI-compatible env vars.
Output is the factory's structured records (title/date/url per the stock
config.json), not full page text - scores reflect that design.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

FACTORY_ROOT = Path(__file__).resolve().parents[2] / "bin" / "scraper-factory"
DEFAULT_MODEL = "openai/gpt-4o-mini"


def run_factory(args: list[str], timeout: int) -> subprocess.CompletedProcess:
    key = os.environ.get("OPENROUTER_API_KEY", "")
    env = dict(os.environ)
    env.update(
        {
            "OPENAI_API_KEY": key,
            "OPENAI_BASE_URL": "https://openrouter.ai/api/v1",
            "LLM_MODEL": os.environ.get("SCRAPER_FACTORY_MODEL", DEFAULT_MODEL),
        }
    )
    return subprocess.run(
        [str(FACTORY_ROOT / ".venv" / "bin" / "python"), "cli.py", *args],
        cwd=FACTORY_ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )


def main() -> int:
    if len(sys.argv) != 4:
        print("usage: scraper_factory_scrape.py <url> <case_id> <timeout_seconds>", file=sys.stderr)
        return 2
    url, case_id, timeout_seconds = sys.argv[1:4]
    if not os.environ.get("OPENROUTER_API_KEY"):
        print("missing OPENROUTER_API_KEY", file=sys.stderr)
        return 2
    if not (FACTORY_ROOT / "cli.py").exists():
        print(f"scraper-factory not installed at {FACTORY_ROOT} (see README)", file=sys.stderr)
        return 2
    timeout = int(float(timeout_seconds))
    org = f"bench_{case_id}"
    scraper_path = FACTORY_ROOT / "scrapers" / org / "scraper.py"
    result_path = FACTORY_ROOT / "scrapers" / org / "result.json"

    if not scraper_path.exists():
        print(f"[scraper-factory] generating scraper for {org}", file=sys.stderr)
        gen = run_factory(["generate", "--url", url, "--org", org], timeout=max(120, timeout - 120))
        print(gen.stdout[-3000:], file=sys.stderr)
        print(gen.stderr[-2000:], file=sys.stderr)
        if not scraper_path.exists():
            print("generation produced no scraper.py", file=sys.stderr)
            return 1
    else:
        print(f"[scraper-factory] reusing generated scraper for {org}", file=sys.stderr)
        if result_path.exists():
            result_path.unlink()
        test = run_factory(["test", "--org", org], timeout=max(60, timeout - 60))
        print(test.stdout[-2000:], file=sys.stderr)
        print(test.stderr[-1000:], file=sys.stderr)

    if not result_path.exists():
        print("no result.json produced", file=sys.stderr)
        return 1
    try:
        records = json.loads(result_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"invalid result.json: {exc}", file=sys.stderr)
        return 1
    if not isinstance(records, list) or not records:
        print("result.json is empty", file=sys.stderr)
        return 1
    print(json.dumps(records, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
