#!/usr/bin/env python3
"""SearXNG adapter for the search benchmark category.

Usage: searxng_search.py "<query>"

Queries a local SearXNG JSON endpoint (SEARXNG_URL, default
http://localhost:8899). Prints a normalized result list to stdout and
`[search metrics] cost=0 dated=<n>/<total> engines=<...>` to stderr. SearXNG is
self-hosted, so marginal cost is zero.
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from collections import Counter

BASE = os.environ.get("SEARXNG_URL", "http://localhost:8899").rstrip("/")
NUM_RESULTS = 10


def main() -> int:
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print("usage: searxng_search.py <query>", file=sys.stderr)
        return 2
    query = sys.argv[1]
    url = f"{BASE}/search?" + urllib.parse.urlencode({"q": query, "format": "json"})
    req = urllib.request.Request(url, headers={"User-Agent": "bs-bench/1.0"})
    try:
        raw = urllib.request.urlopen(req, timeout=60).read()
    except Exception as exc:  # noqa: BLE001 - surface any failure to the harness
        print(f"searxng search failed ({BASE}): {exc}", file=sys.stderr)
        return 1
    data = json.loads(raw)
    results = (data.get("results") or [])[:NUM_RESULTS]
    dated = 0
    for i, r in enumerate(results, 1):
        url_ = r.get("url", "")
        title = r.get("title") or ""
        date = r.get("publishedDate") or ""
        if date:
            dated += 1
        snippet = (r.get("content") or "").replace("\n", " ").strip()[:240]
        print(f"#{i} {title}\n{url_}\n{date}\n{snippet}\n")
    engines = Counter(r.get("engine") for r in results)
    eng = ",".join(f"{k}:{v}" for k, v in engines.items())
    print(f"[search metrics] cost=0 dated={dated}/{len(results)} engines={eng}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
