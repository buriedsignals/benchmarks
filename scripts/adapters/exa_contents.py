from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


def cost_total(value: object) -> object:
    if isinstance(value, dict):
        if "total" in value:
            return value["total"]
        return value
    return value


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: exa_contents.py <url>", file=sys.stderr)
        return 2
    key = os.environ.get("EXA_API_KEY")
    if not key:
        print("missing EXA_API_KEY", file=sys.stderr)
        return 2
    target_url = sys.argv[1]
    payload = json.dumps(
        {
            "urls": [target_url],
            "text": True,
            "maxAgeHours": 0,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://api.exa.ai/contents",
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "x-api-key": key,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=75) as res:
            body = res.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        print(exc.read().decode("utf-8", errors="replace"), file=sys.stderr)
        return 1
    data = json.loads(body)
    cost = cost_total(data.get("costDollars") or data.get("cost"))
    if cost is not None:
        print(f"[exa metrics] cost={cost}", file=sys.stderr)
    statuses = data.get("statuses", [])
    for status in statuses:
        status_id = status.get("id") or status.get("url") or ""
        status_value = status.get("status") or ""
        source = status.get("source") or ""
        if status_value != "success":
            print(f"status: {status_value} {status_id} {source}".strip(), file=sys.stderr)
        else:
            print(f"status: {status_value} {status_id} {source}".strip())
    results = data.get("results", [])
    if not results:
        print("no Exa contents results returned", file=sys.stderr)
        return 1
    for result in results:
        print(result.get("title") or "")
        print(result.get("url") or result.get("id") or target_url)
        if result.get("publishedDate"):
            print(f"publishedDate: {result['publishedDate']}")
        if result.get("author"):
            print(f"author: {result['author']}")
        text = result.get("text") or ""
        if text:
            print(text[:30_000])
        extras = result.get("extras") or {}
        links = extras.get("links") or []
        if links:
            print("links:")
            for link in links[:80]:
                if isinstance(link, dict):
                    print(f"- {link.get('text') or ''} {link.get('url') or link.get('href') or ''}".strip())
                else:
                    print(f"- {link}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
