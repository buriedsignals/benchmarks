#!/usr/bin/env python3
"""Parallel orchestrator for the osint_qa benchmark.

Reuses the harness (command_for + score_output) but runs (model x question) cells
concurrently and stores ONE consolidated run file with the FULL answer text (run_one only
keeps a 4000-char preview, which would truncate long answers before judging).

Output: results/osint_qa/runs/<timestamp>/
  - records.jsonl   one row per (tool, case): full answer, score, probe details, meta
  - answers/<tool>__<case>.txt   raw model answer (for the blind judge)
  - summary.json    per-tool aggregates (facet score by subset, latency)

Usage:
  python3 scripts/run_osint_qa.py --tools m_glm_5_2,m_fable_5 --concurrency 8 --timeout 300
  python3 scripts/run_osint_qa.py --all-api            # every osint_qa tool that is env-ready
"""
from __future__ import annotations
import argparse
import concurrent.futures as cf
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmarkers.cli import load_cases, load_tools, command_for, score_output, build_variables  # noqa: E402


def env_ready(tool: dict) -> tuple[bool, str]:
    for e in tool.get("requires_env", []):
        if not os.environ.get(e):
            return False, f"missing env {e}"
    import shutil
    for ex in tool.get("requires_executables", []):
        if shutil.which(ex) is None:
            return False, f"missing exe {ex}"
    return True, "ready"


def run_cell(case: dict, tool: dict, run_dir: Path, timeout: int) -> dict:
    command, variables, stdin = command_for(case, tool, run_dir, timeout)
    t0 = time.perf_counter()
    try:
        proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True,
                              input=stdin, timeout=timeout, check=False)
        elapsed = round((time.perf_counter() - t0) * 1000)
        stdout, stderr = proc.stdout or "", proc.stderr or ""
        rc = proc.returncode
        status = "pass" if rc == 0 else "fail"
    except subprocess.TimeoutExpired as e:
        elapsed = round((time.perf_counter() - t0) * 1000)
        stdout = (e.stdout if isinstance(e.stdout, str) else "") or ""
        stderr = (e.stderr if isinstance(e.stderr, str) else "") or ""
        rc, status = None, "timeout"
    score = score_output(case, stdout, stderr, variables, elapsed)
    # pull LLM_META line from stderr if present
    meta = {}
    for line in stderr.splitlines():
        if line.startswith("LLM_META "):
            try: meta = json.loads(line[len("LLM_META "):])
            except Exception: pass
    return {
        "tool": tool["id"], "tool_label": tool.get("label"),
        "tool_meta": tool.get("meta", {}),
        "case": case["id"], "subset": case.get("subset"), "case_category": case.get("category"),
        "status": status, "exit_code": rc, "elapsed_ms": elapsed,
        "score": score.get("score"), "matched_weight": score.get("matched_weight"),
        "possible_weight": score.get("possible_weight"),
        "probe_details": [{"value": d["probe"].get("value"), "weight": d["probe"].get("weight"),
                           "kind": d["probe"].get("kind"), "ok": d["ok"]} for d in score.get("details", [])],
        "answer": stdout,
        "answer_chars": len(stdout),
        "stderr_tail": stderr[-500:],
        "llm_meta": meta,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tools", help="comma-separated tool ids; default = all osint_qa tools")
    ap.add_argument("--all-api", action="store_true", help="all env-ready osint_qa tools")
    ap.add_argument("--cases", help="comma-separated case ids; default = all")
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--run-dir", help="reuse/append into an existing run dir")
    ap.add_argument("--repeats", type=int, default=1, help="n runs per cell (variance probe)")
    args = ap.parse_args()

    cases = [c for c in load_cases() if c["category"] == "osint_qa"]
    if args.cases:
        want = set(args.cases.split(","))
        cases = [c for c in cases if c["id"] in want]
    all_tools = {t["id"]: t for t in load_tools() if "osint_qa" in t.get("categories", [])}
    if args.tools:
        tools = [all_tools[t] for t in args.tools.split(",") if t in all_tools]
    else:
        tools = list(all_tools.values())
    if args.all_api:
        tools = [t for t in tools if env_ready(t)[0]]

    ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    run_dir = Path(args.run_dir) if args.run_dir else (ROOT / "results" / "osint_qa" / "runs" / ts)
    (run_dir / "answers").mkdir(parents=True, exist_ok=True)
    (run_dir / "scratch").mkdir(parents=True, exist_ok=True)

    cells = [(c, t, r) for t in tools for c in cases for r in range(args.repeats)]
    print(f"[run] {len(tools)} tools x {len(cases)} cases x {args.repeats} = {len(cells)} cells "
          f"-> {run_dir}  (concurrency {args.concurrency})")
    for t in tools:
        ok, why = env_ready(t)
        if not ok: print(f"  WARN {t['id']}: {why} (will run and likely fail)")

    records = []
    def work(cell):
        c, t, rep = cell
        return rep, run_cell(c, t, run_dir / "scratch", args.timeout)
    with cf.ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futs = {ex.submit(work, cell): cell for cell in cells}
        done = 0
        for fut in cf.as_completed(futs):
            rep, rec = fut.result()
            rec["repeat"] = rep
            records.append(rec)
            done += 1
            st = rec["status"]; sc = rec["score"]
            tag = f"{rec['tool']}/{rec['case']}" + (f"#{rep}" if args.repeats > 1 else "")
            print(f"  [{done}/{len(cells)}] {tag:52s} {st:8s} score={sc if sc is not None else '-'}")
            # persist the answer text for the judge
            if rep == 0:
                (run_dir / "answers" / f"{rec['tool']}__{rec['case']}.txt").write_text(rec["answer"], encoding="utf-8")

    # write consolidated records
    with open(run_dir / "records.jsonl", "a", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

    # per-tool summary
    summary = {}
    for r in records:
        if r["repeat"] != 0:
            continue
        s = summary.setdefault(r["tool"], {"label": r["tool_label"], "meta": r["tool_meta"],
                                           "n": 0, "pass": 0, "scores": [], "by_subset": {}, "elapsed": []})
        s["n"] += 1
        if r["status"] == "pass": s["pass"] += 1
        if r["score"] is not None:
            s["scores"].append(r["score"])
            s["by_subset"].setdefault(r["subset"], []).append(r["score"])
        s["elapsed"].append(r["elapsed_ms"])
    for tid, s in summary.items():
        s["facet_mean"] = round(sum(s["scores"]) / len(s["scores"]), 4) if s["scores"] else None
        s["facet_by_subset"] = {k: round(sum(v)/len(v), 4) for k, v in s["by_subset"].items()}
        s["elapsed_median_ms"] = sorted(s["elapsed"])[len(s["elapsed"])//2] if s["elapsed"] else None
        del s["scores"], s["by_subset"], s["elapsed"]
    json.dump(summary, open(run_dir / "summary.json", "w"), indent=2)
    print(f"[done] records={len(records)}  summary -> {run_dir/'summary.json'}")
    # quick leaderboard
    board = sorted(summary.items(), key=lambda kv: (kv[1]["facet_mean"] is not None, kv[1]["facet_mean"] or -1), reverse=True)
    print("\n  facet leaderboard (this run):")
    for tid, s in board:
        print(f"   {s['facet_mean']}  {tid:20s} {s['label']}")
    print(f"\nRUN_DIR={run_dir}")


if __name__ == "__main__":
    main()
