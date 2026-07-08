#!/usr/bin/env python3
"""Exa /search adapter for the search benchmark category.

Usage: exa_search.py "<query>"

Prints a normalized result list to stdout (rank, title, URL, date, snippet) so
the harness `contains` probes can score whether the expected authoritative
sources appear. Prints `[search metrics] cost=<dollars> dated=<n>/<total>` to
stderr; cost comes from Exa's costDollars.total.
"""
import json
import os
import sys
import urllib.request

EXA_URL = "https://api.exa.ai/search"
NUM_RESULTS = 10


def main() -> int:
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print("usage: exa_search.py <query>", file=sys.stderr)
        return 2
    query = sys.argv[1]
    key = os.environ.get("EXA_API_KEY")
    if not key:
        print("EXA_API_KEY not set", file=sys.stderr)
        return 2

    body = {
        "query": query,
        "type": "auto",
        "numResults": NUM_RESULTS,
        "contents": {
            "text": {"maxCharacters": 400, "verbosity": "compact"},
            "highlights": True,
        },
    }
    req = urllib.request.Request(
        EXA_URL,
        data=json.dumps(body).encode(),
        headers={"x-api-key": key, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        raw = urllib.request.urlopen(req, timeout=60).read()
    except Exception as exc:  # noqa: BLE001 - surface any failure to the harness
        print(f"exa search failed: {exc}", file=sys.stderr)
        return 1
    data = json.loads(raw)
    results = data.get("results", []) or []
    dated = 0
    for i, r in enumerate(results, 1):
        url = r.get("url", "")
        title = r.get("title") or ""
        date = r.get("publishedDate") or ""
        if date:
            dated += 1
        snippet = (r.get("text") or "").replace("\n", " ").strip()[:240]
        print(f"#{i} {title}\n{url}\n{date}\n{snippet}\n")
    cost = (data.get("costDollars") or {}).get("total")
    cost_str = f"{cost:.4f}" if isinstance(cost, (int, float)) else "0"
    print(f"[search metrics] cost={cost_str} dated={dated}/{len(results)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
