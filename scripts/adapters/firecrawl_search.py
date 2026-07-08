#!/usr/bin/env python3
"""Firecrawl /search adapter for the search benchmark category.

Usage: firecrawl_search.py "<query>"

Shells out to the `firecrawl` CLI (`firecrawl search <q> --limit 10 --json`),
prints a normalized result list to stdout, and reports
`[search metrics] credits=<n> dated=<n>/<total>` to stderr. Firecrawl search
(discovery only, no --scrape) bills ~2 credits per 10-result query (measured
2026-07-08); no per-call credit field is returned in the JSON, so it is
recorded as the observed constant.
"""
import json
import subprocess
import sys

CREDITS_PER_SEARCH = 2  # measured: 12 credits / 6 searches at --limit 10


def main() -> int:
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print("usage: firecrawl_search.py <query>", file=sys.stderr)
        return 2
    query = sys.argv[1]
    try:
        proc = subprocess.run(
            ["firecrawl", "search", query, "--limit", "10", "--json"],
            capture_output=True, text=True, timeout=80,
        )
    except Exception as exc:  # noqa: BLE001 - surface any failure to the harness
        print(f"firecrawl search failed: {exc}", file=sys.stderr)
        return 1
    if proc.returncode != 0:
        print(proc.stderr[-500:] or "firecrawl non-zero exit", file=sys.stderr)
        return 1
    data = json.loads(proc.stdout)
    web = (data.get("data") or {}).get("web", []) or []
    dated = 0
    for i, r in enumerate(web, 1):
        url = r.get("url", "")
        title = r.get("title") or ""
        date = r.get("date") or ""
        if date:
            dated += 1
        snippet = (r.get("description") or "").replace("\n", " ").strip()[:240]
        print(f"#{i} {title}\n{url}\n{date}\n{snippet}\n")
    print(f"[search metrics] credits={CREDITS_PER_SEARCH} dated={dated}/{len(web)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
