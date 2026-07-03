#!/usr/bin/env python3
"""Layer B: URL/tool hallucination rate.

For each model answer, extract cited URLs, reduce to registrable domains, and classify:
  in_db      domain matches a tool in the osint-tool-database snapshot (definitely real)
  live       domain not in DB but resolves + returns any HTTP response (real, just uncatalogued)
  dead       domain does not resolve / no response (hallucinated)

hallucination_rate = dead / (in_db + live + dead), per model and per subset.
A tool present in the DB but status!=active is NOT penalised (tool-rot rule) — but the
snapshot is all-active, so that path is moot here.

Usage:
  python3 scripts/score_hallucination.py --run-dir results/osint_qa/runs/<ts> [--no-liveness]
"""
from __future__ import annotations
import argparse
import json
import re
import socket
import ssl
import urllib.request
import urllib.error
import concurrent.futures as cf
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "osint-tool-db" / "osint_tools.jsonl"
CACHE = ROOT / "results" / "osint_qa" / "liveness_cache.json"

URL_RE = re.compile(r"https?://[^\s\)\]\}<>\"'`|]+", re.I)
BARE_DOMAIN_RE = re.compile(r"\b(?:www\.)?([a-z0-9][a-z0-9-]{1,}\.(?:com|org|net|io|ai|co|gov|edu|info|me|app|dev|ru|de|uk|eu|ch|tools|xyz|us|ca))\b", re.I)

# domains that are infrastructure/generic, not "OSINT tools" — don't score as tool citations
GENERIC = {
    "github.com", "gitlab.com", "google.com", "google.co.uk", "wikipedia.org",
    "en.wikipedia.org", "youtube.com", "twitter.com", "x.com", "facebook.com",
    "reddit.com", "medium.com", "archive.org", "web.archive.org", "example.com",
    "linkedin.com", "t.me", "telegram.org", "apple.com", "microsoft.com",
}


def registrable(host: str) -> str:
    host = host.lower().strip().strip(".")
    if host.startswith("www."):
        host = host[4:]
    parts = host.split(".")
    if len(parts) <= 2:
        return host
    # crude eTLD+1 for common two-part suffixes
    two = {"co.uk", "org.uk", "gov.uk", "com.au", "co.jp", "com.br", "co.in"}
    if ".".join(parts[-2:]) in two:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def load_db_domains() -> set[str]:
    doms = set()
    for line in open(DB, encoding="utf-8"):
        try:
            r = json.loads(line)
        except Exception:
            continue
        u = r.get("tool_url") or ""
        m = re.search(r"https?://([^/\s]+)", u)
        host = m.group(1) if m else u
        if host:
            doms.add(registrable(host))
    return doms


def extract_domains(text: str) -> list[str]:
    doms = []
    for u in URL_RE.findall(text):
        m = re.match(r"https?://([^/\s]+)", u)
        if m:
            doms.append(registrable(m.group(1)))
    for m in BARE_DOMAIN_RE.finditer(text):
        doms.append(registrable(m.group(1)))
    # dedupe, drop generic infra
    out = []
    seen = set()
    for d in doms:
        if d in seen or d in GENERIC:
            continue
        seen.add(d)
        out.append(d)
    return out


def is_live(domain: str, timeout: float = 6.0) -> bool:
    # DNS first
    try:
        socket.gethostbyname(domain)
    except Exception:
        return False
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    for scheme in ("https", "http"):
        try:
            req = urllib.request.Request(f"{scheme}://{domain}", method="HEAD",
                                        headers={"User-Agent": "Mozilla/5.0 osint-bench-liveness"})
            urllib.request.urlopen(req, timeout=timeout, context=ctx)
            return True
        except urllib.error.HTTPError:
            return True  # any HTTP status => host exists
        except Exception:
            continue
    return False


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--no-liveness", action="store_true", help="skip network liveness; unknown=dead")
    ap.add_argument("--concurrency", type=int, default=16)
    args = ap.parse_args()

    run_dir = Path(args.run_dir)
    recs = [json.loads(l) for l in open(run_dir / "records.jsonl") if l.strip()]
    recs = [r for r in recs if r.get("repeat", 0) == 0]
    db = load_db_domains()
    print(f"[hallucination] DB domains={len(db)}  records={len(recs)}")

    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    # gather all non-DB domains needing a liveness check
    all_doms = set()
    per_rec = {}
    for r in recs:
        ds = extract_domains(r.get("answer", ""))
        per_rec[(r["tool"], r["case"])] = ds
        for d in ds:
            if d not in db:
                all_doms.add(d)
    to_check = [d for d in all_doms if d not in cache]
    if not args.no_liveness and to_check:
        print(f"[hallucination] liveness-checking {len(to_check)} uncatalogued domains...")
        with cf.ThreadPoolExecutor(max_workers=args.concurrency) as ex:
            for d, live in zip(to_check, ex.map(is_live, to_check)):
                cache[d] = live
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(cache, indent=0))

    def classify(d: str) -> str:
        if d in db:
            return "in_db"
        if args.no_liveness:
            return "dead"
        return "live" if cache.get(d) else "dead"

    by_tool = {}
    detail = []
    for r in recs:
        ds = per_rec[(r["tool"], r["case"])]
        cls = [classify(d) for d in ds]
        row = {"tool": r["tool"], "case": r["case"], "subset": r.get("subset"),
               "domains": ds, "classes": cls,
               "in_db": cls.count("in_db"), "live": cls.count("live"), "dead": cls.count("dead"),
               "dead_domains": [d for d, c in zip(ds, cls) if c == "dead"]}
        detail.append(row)
        t = by_tool.setdefault(r["tool"], {"label": r.get("tool_label"), "meta": r.get("tool_meta", {}),
                                           "in_db": 0, "live": 0, "dead": 0, "answers": 0, "answers_with_url": 0,
                                           "by_subset": {}})
        t["in_db"] += row["in_db"]; t["live"] += row["live"]; t["dead"] += row["dead"]
        t["answers"] += 1
        if ds: t["answers_with_url"] += 1
        ss = t["by_subset"].setdefault(r.get("subset"), {"in_db": 0, "live": 0, "dead": 0})
        ss["in_db"] += row["in_db"]; ss["live"] += row["live"]; ss["dead"] += row["dead"]

    for tid, t in by_tool.items():
        tot = t["in_db"] + t["live"] + t["dead"]
        t["total_cited"] = tot
        t["hallucination_rate"] = round(t["dead"] / tot, 4) if tot else None
        t["real_rate"] = round((t["in_db"] + t["live"]) / tot, 4) if tot else None
        t["in_db_rate"] = round(t["in_db"] / tot, 4) if tot else None
        for ss, s in t["by_subset"].items():
            st = s["in_db"] + s["live"] + s["dead"]
            s["hallucination_rate"] = round(s["dead"] / st, 4) if st else None
            s["total"] = st

    out = {"run_dir": str(run_dir), "db_domains": len(db), "by_tool": by_tool}
    json.dump(out, open(run_dir / "hallucination.json", "w"), indent=2)
    json.dump(detail, open(run_dir / "hallucination_detail.json", "w"), indent=2)
    print(f"[hallucination] wrote {run_dir/'hallucination.json'}\n")
    board = sorted(by_tool.items(), key=lambda kv: (kv[1]["hallucination_rate"] is not None, kv[1]["hallucination_rate"] or 1))
    print("  hallucination rate (lower=better)  [dead/total cited]:")
    for tid, t in board:
        print(f"   {t['hallucination_rate']}  {tid:20s} dead={t['dead']:3d}/{t['total_cited']:3d}  in_db={t['in_db_rate']}")


if __name__ == "__main__":
    main()
