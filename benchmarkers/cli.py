from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from string import Formatter
from typing import Any, Optional


ROOT = Path(__file__).resolve().parents[1]
TOOLS_PATH = ROOT / "configs" / "tools.json"
CASES_DIR = ROOT / "cases"
RESULTS_DIR = ROOT / "results"
PUBLIC_DIR = ROOT / "public"
DEFAULT_ENV_PATH = ROOT / ".env"


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")


def load_env_file(path_value: Optional[str]) -> None:
    if path_value:
        path = Path(path_value).expanduser()
    else:
        path = DEFAULT_ENV_PATH
        if not path.exists():
            return
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        raise FileNotFoundError(f"env file not found: {path}")
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path)


def load_tools() -> list[dict[str, Any]]:
    return load_json(TOOLS_PATH)["tools"]


def load_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for path in sorted(CASES_DIR.glob("*.json")):
        payload = load_json(path)
        for case in payload["cases"]:
            case.setdefault("category", payload["category"])
            case.setdefault("source_file", rel(path))
            cases.append(case)
    return cases


def stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def format_value(value: str, variables: dict[str, str]) -> str:
    return value.format(**variables)


def referenced_fields(template: str) -> set[str]:
    fields: set[str] = set()
    for _, field_name, _, _ in Formatter().parse(template):
        if field_name:
            fields.add(field_name)
    return fields


def build_variables(
    case: dict[str, Any],
    tool: dict[str, Any],
    run_dir: Path,
    timeout_seconds: int,
) -> dict[str, str]:
    input_data = case.get("input", {})
    artifact_extension = str(tool.get("artifact_extension", "artifact")).lstrip(".")
    artifact_path = run_dir / f"{case['id']}--{tool['id']}.{artifact_extension}"
    script_path = run_dir / f"{case['id']}--{tool['id']}.script"
    variables = {
        "case_id": case["id"],
        "tool_id": tool["id"],
        "category": case["category"],
        "prompt": case.get("prompt", ""),
        "timeout_seconds": str(timeout_seconds),
        "output_dir": str(run_dir),
        "artifact_path": str(artifact_path),
        "script_path": str(script_path),
    }
    for key, value in input_data.items():
        if key == "path":
            variables[key] = str((ROOT / value).resolve())
        else:
            variables[key] = str(value)
    return variables


def tool_status(
    tool: dict[str, Any],
    allow_network: bool,
    allow_paid: bool,
    include_unconfigured: bool,
) -> tuple[bool, str]:
    if tool.get("unconfigured") and not include_unconfigured:
        return False, "unconfigured adapter"
    if tool.get("network") and not allow_network:
        return False, "requires --allow-network"
    if tool.get("paid") and not allow_paid:
        return False, "requires --allow-paid"
    for exe in tool.get("requires_executables", []):
        if shutil.which(exe) is None:
            return False, f"missing executable: {exe}"
    for file_value in tool.get("requires_files", []):
        path = Path(file_value)
        if not path.is_absolute():
            path = ROOT / path
        if not path.exists():
            return False, f"missing file: {file_value}"
    for env_name in tool.get("requires_env", []):
        if not os.environ.get(env_name):
            return False, f"missing env: {env_name}"
    return True, "ready"


def command_for(
    case: dict[str, Any],
    tool: dict[str, Any],
    run_dir: Path,
    timeout_seconds: int,
) -> tuple[list[str], dict[str, str], Optional[str]]:
    variables = build_variables(case, tool, run_dir, timeout_seconds)
    script_template = tool.get("script_template")
    if script_template:
        script_path = Path(variables["script_path"])
        script_path.write_text(script_template.format(**variables), encoding="utf-8")
    command = [format_value(part, variables) for part in tool["command"]]
    stdin_template = tool.get("stdin_template")
    stdin = stdin_template.format(**variables) if stdin_template else None
    return command, variables, stdin


def missing_template_fields(tool: dict[str, Any], variables: dict[str, str]) -> list[str]:
    fields: set[str] = set()
    for part in tool.get("command", []):
        fields.update(referenced_fields(part))
    script_template = tool.get("script_template")
    if script_template:
        fields.update(referenced_fields(script_template))
    stdin_template = tool.get("stdin_template")
    if stdin_template:
        fields.update(referenced_fields(stdin_template))
    return sorted(field for field in fields if field not in variables)


def score_output(
    case: dict[str, Any],
    stdout: str,
    stderr: str,
    variables: dict[str, str],
    elapsed_ms: int,
) -> dict[str, Any]:
    metrics = text_metrics(stdout)
    probes = case.get("probes", [])
    matched = 0.0
    possible = 0.0
    details = []
    for probe in probes:
        weight = float(probe.get("weight", 1.0))
        possible += weight
        kind = probe["kind"]
        ok = False
        if kind == "contains":
            ok = probe["value"].lower() in stdout.lower()
        elif kind == "regex":
            ok = re.search(probe["value"], stdout, flags=re.I | re.M) is not None
        elif kind == "min_chars":
            ok = len(stdout.strip()) >= int(probe["value"])
        elif kind == "max_seconds":
            ok = elapsed_ms <= int(float(probe["value"]) * 1000)
        elif kind == "artifact_nonempty":
            path = Path(format_value(probe["value"], variables))
            ok = path.exists() and path.stat().st_size > 0
        elif kind == "max_control_char_ratio":
            ok = metrics["control_char_ratio"] <= float(probe["value"])
        elif kind == "max_replacement_char_ratio":
            ok = metrics["replacement_char_ratio"] <= float(probe["value"])
        else:
            details.append({"probe": probe, "ok": False, "error": f"unknown probe kind {kind}"})
            continue
        if ok:
            matched += weight
        details.append({"probe": probe, "ok": ok})
    score = matched / possible if possible else None
    return {
        "score": score,
        "matched_weight": matched,
        "possible_weight": possible,
        "metrics": metrics,
        "details": details,
    }


def text_metrics(text: str) -> dict[str, Any]:
    total = len(text)
    control_chars = sum(
        1
        for char in text
        if ord(char) < 32 and char not in "\n\r\t\f"
    )
    replacement_chars = text.count("\ufffd") + text.count("\x02")
    return {
        "chars": total,
        "control_chars": control_chars,
        "control_char_ratio": control_chars / total if total else 0,
        "replacement_chars": replacement_chars,
        "replacement_char_ratio": replacement_chars / total if total else 0,
    }


INVALID_SOURCE_PATTERNS = [
    r"\b(?:error|erreur|fehler)\s*404\b",
    r"\b404\s*(?:not\s*found|error)\b",
    r"dokument nicht auffindbar",
    r"seite nicht gefunden",
    r"page not found",
    r"page recherch\S+e est introuvable",
    r"pagina non trovata",
]


def detect_invalid_source(stdout: str) -> Optional[str]:
    """Flag output that is an error page rather than the requested source.

    Guards against the June 2026 failure mode where two rotted case URLs
    served 404 pages for a month and substring probes kept scoring them.
    Conservative by design: only small outputs are considered (a real page
    that merely mentions a 404 stays scoreable) and only the head is
    searched. Empty output is a tool failure, not a liveness verdict.
    """
    text = stdout.strip()
    if not text or len(text) > 20_000:
        return None
    head = text[:4_000].lower()
    for pattern in INVALID_SOURCE_PATTERNS:
        if re.search(pattern, head):
            return f"source looks like an error page (matched {pattern!r})"
    return None


def adapter_metrics(stderr: str) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    extend_match = re.search(
        r"\[extend metrics\]\s+pages=(\d+|None)\s+processing_ms=(\d+|None)\s+credits=(\d+|None)",
        stderr,
    )
    if extend_match:
        pages, processing_ms, credits = extend_match.groups()
        if pages != "None":
            metrics["pages"] = int(pages)
        if processing_ms != "None":
            metrics["processing_ms"] = int(processing_ms)
        if credits != "None":
            metrics["credits"] = int(credits)
    exa_match = re.search(r"\[exa metrics\]\s+cost=([0-9.]+)", stderr)
    if exa_match:
        metrics["cost_dollars"] = float(exa_match.group(1))
    return metrics


def run_one(
    case: dict[str, Any],
    tool: dict[str, Any],
    run_dir: Path,
    timeout_seconds: int,
) -> dict[str, Any]:
    command, variables, stdin = command_for(case, tool, run_dir, timeout_seconds)
    started = time.perf_counter()
    try:
        proc = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            capture_output=True,
            input=stdin,
            timeout=timeout_seconds,
            check=False,
        )
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        score = (
            score_output(case, stdout, stderr, variables, elapsed_ms)
            if tool.get("content_output", True)
            else {
                "score": None,
                "matched_weight": 0,
                "possible_weight": 0,
                "metrics": text_metrics(stdout),
                "details": [],
            }
        )
        status = "pass" if proc.returncode == 0 else "fail"
        invalid_reason = detect_invalid_source(stdout)
        if invalid_reason:
            status = "invalid_source"
            score["score"] = None
            score["invalid_source"] = invalid_reason
        return {
            "status": status,
            "exit_code": proc.returncode,
            "elapsed_ms": elapsed_ms,
            "stdout_bytes": len(stdout.encode("utf-8")),
            "stderr_bytes": len(stderr.encode("utf-8")),
            "stdout_preview": stdout[:4000],
            "stderr_preview": stderr[:2000],
            "score": score,
            "adapter_metrics": adapter_metrics(stderr),
            "command": command,
        }
    except subprocess.TimeoutExpired as exc:
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        score = (
            score_output(case, stdout, stderr, variables, elapsed_ms)
            if tool.get("content_output", True)
            else {
                "score": None,
                "matched_weight": 0,
                "possible_weight": 0,
                "metrics": text_metrics(stdout),
                "details": [],
            }
        )
        return {
            "status": "timeout",
            "exit_code": None,
            "elapsed_ms": elapsed_ms,
            "stdout_bytes": len(stdout.encode("utf-8")),
            "stderr_bytes": len(stderr.encode("utf-8")),
            "stdout_preview": stdout[:4000],
            "stderr_preview": stderr[:2000],
            "score": score,
            "adapter_metrics": adapter_metrics(stderr),
            "command": command,
        }


def select_items(
    categories: list[str] | None,
    case_ids: list[str] | None,
    tool_ids: list[str] | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cases = load_cases()
    tools = load_tools()
    if categories:
        wanted = set(categories)
        cases = [case for case in cases if case["category"] in wanted]
        tools = [tool for tool in tools if wanted.intersection(tool.get("categories", []))]
    if case_ids:
        wanted_cases = set(case_ids)
        cases = [case for case in cases if case["id"] in wanted_cases]
    if tool_ids:
        wanted_tools = set(tool_ids)
        tools = [tool for tool in tools if tool["id"] in wanted_tools]
    return cases, tools


def cmd_list(args: argparse.Namespace) -> int:
    cases, tools = select_items(args.category, None, None)
    print("Categories:")
    for category in sorted({case["category"] for case in cases}):
        print(f"  {category}")
    print("\nCases:")
    for case in cases:
        print(f"  {case['category']}/{case['id']}: {case['title']}")
    print("\nTools:")
    for tool in tools:
        cats = ", ".join(tool.get("categories", []))
        print(f"  {tool['id']}: {tool['label']} [{cats}]")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    load_env_file(args.env_file)
    _, tools = select_items(args.category, None, args.tool)
    for tool in tools:
        ready, reason = tool_status(
            tool,
            allow_network=args.allow_network,
            allow_paid=args.allow_paid,
            include_unconfigured=args.include_unconfigured,
        )
        state = "ready" if ready else "skip"
        print(f"{state:5} {tool['id']}: {reason}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    load_env_file(args.env_file)
    cases, tools = select_items(args.category, args.case, args.tool)
    run_dir = RESULTS_DIR / stamp()
    run_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for case in cases:
        for tool in tools:
            if case["category"] not in tool.get("categories", []):
                continue
            ready, reason = tool_status(
                tool,
                allow_network=args.allow_network,
                allow_paid=args.allow_paid,
                include_unconfigured=args.include_unconfigured,
            )
            if not ready:
                results.append({
                    "case": case,
                    "tool": tool_summary(tool),
                    "status": "skip",
                    "skip_reason": reason,
                })
                print(f"skip {case['id']} / {tool['id']}: {reason}")
                continue
            variables = build_variables(case, tool, run_dir, args.timeout)
            missing_fields = missing_template_fields(tool, variables)
            if missing_fields:
                reason = f"case missing template fields: {', '.join(missing_fields)}"
                results.append({
                    "case": case,
                    "tool": tool_summary(tool),
                    "status": "skip",
                    "skip_reason": reason,
                })
                print(f"skip {case['id']} / {tool['id']}: {reason}")
                continue
            print(f"run  {case['id']} / {tool['id']}")
            outcome = run_one(case, tool, run_dir, args.timeout)
            outcome.update({"case": case, "tool": tool_summary(tool)})
            results.append(outcome)
    report = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "run_dir": rel(run_dir),
        "args": serializable_args(args),
        "results": results,
    }
    out_path = run_dir / "results.json"
    write_json(out_path, report)
    latest = RESULTS_DIR / "latest.json"
    write_json(latest, report)
    print(f"\nWrote {rel(out_path)}")
    print(f"Wrote {rel(latest)}")
    return 0


def serializable_args(args: argparse.Namespace) -> dict[str, Any]:
    return {
        key: value
        for key, value in vars(args).items()
        if key != "func" and isinstance(value, (str, int, float, bool, list, type(None)))
    }


def tool_summary(tool: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": tool["id"],
        "label": tool["label"],
        "categories": tool.get("categories", []),
        "paid": bool(tool.get("paid")),
        "network": bool(tool.get("network")),
    }


def cmd_report(args: argparse.Namespace) -> int:
    input_path = Path(args.input)
    if not input_path.is_absolute():
        input_path = ROOT / input_path
    payload = load_json(input_path)
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = ROOT / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_html(payload), encoding="utf-8")
    print(f"Wrote {rel(output_path)}")
    return 0


def dedupe_results(
    results: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Collapse duplicate (category, case, tool) rows from combined runs.

    Later inputs win, except a skip row never replaces an executed result;
    a skip survives only when no executed row exists for the same pair.
    Without this, combining a fresh gated run with an older paid run would
    average stale and fresh rows together in the report.
    """
    winners: dict[tuple[Any, Any, Any], dict[str, Any]] = {}
    order: list[tuple[Any, Any, Any]] = []
    dropped: list[dict[str, Any]] = []
    for item in results:
        case = item.get("case", {})
        key = (case.get("category"), case.get("id"), item.get("tool", {}).get("id"))
        if key not in winners:
            winners[key] = item
            order.append(key)
            continue
        current = winners[key]
        item_wins = item.get("status") != "skip" or current.get("status") == "skip"
        if item_wins:
            dropped.append(current)
            winners[key] = item
        else:
            dropped.append(item)
    return [winners[key] for key in order], dropped


def cmd_combine(args: argparse.Namespace) -> int:
    inputs = []
    results = []
    for input_value in args.inputs:
        path = Path(input_value)
        if not path.is_absolute():
            path = ROOT / path
        payload = load_json(path)
        inputs.append(rel(path))
        results.extend(payload.get("results", []))
    results, dropped = dedupe_results(results)
    if dropped:
        print(f"Dropped {len(dropped)} duplicate row(s); newest executed results win.")
    combined = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "combined_from": inputs,
        "results": results,
    }
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = ROOT / output_path
    write_json(output_path, combined)
    if args.update_latest:
        write_json(RESULTS_DIR / "latest.json", combined)
    print(f"Wrote {rel(output_path)}")
    if args.update_latest:
        print(f"Wrote {rel(RESULTS_DIR / 'latest.json')}")
    return 0


def cmd_export_site(args: argparse.Namespace) -> int:
    input_path = Path(args.input)
    if not input_path.is_absolute():
        input_path = ROOT / input_path
    html_path = Path(args.html)
    if not html_path.is_absolute():
        html_path = ROOT / html_path
    target_dir = Path(args.target).expanduser()
    if not target_dir.is_absolute():
        target_dir = ROOT / target_dir
    payload = load_json(input_path)
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "latest.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    if not html_path.exists():
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text(render_html(payload), encoding="utf-8")
    (target_dir / "index.html").write_text(
        html_path.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    print(f"Wrote {target_dir / 'latest.json'}")
    print(f"Wrote {target_dir / 'index.html'}")
    return 0


def pct(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{float(value) * 100:.0f}%"


def render_html(payload: dict[str, Any]) -> str:
    summary: dict[str, dict[str, dict[str, Any]]] = {}
    category_cases: dict[str, set[str]] = {}
    case_runs: dict[str, dict[str, dict[str, Any]]] = {}
    canonical_cases = {
        (case["category"], case["id"]): case
        for case in load_cases()
    }

    def failure_note(item: dict[str, Any]) -> str:
        if item.get("skip_reason"):
            return str(item["skip_reason"])
        if item.get("status") == "pass":
            return "no target evidence returned"
        stderr = item.get("stderr_preview") or ""
        lines = [line.strip() for line in stderr.splitlines() if line.strip()]
        for line in reversed(lines):
            if "keepalive ping timeout" in line:
                return "CDP keepalive ping timeout"
            if "Timeout" in line or "Error" in line or "failed" in line.lower():
                return line[:180]
        return lines[-1][:180] if lines else str(item.get("status", "failed"))

    for item in payload.get("results", []):
        raw_case = item["case"]
        case = canonical_cases.get(
            (raw_case.get("category"), raw_case.get("id")),
            raw_case,
        )
        tool = item["tool"]
        category = case["category"]
        tool_label = tool["label"]
        score = item.get("score", {}).get("score") if isinstance(item.get("score"), dict) else None
        extra_metrics = dict(item.get("adapter_metrics") or {})
        if not extra_metrics:
            extra_metrics = adapter_metrics(item.get("stderr_preview", ""))
        category_cases.setdefault(category, set()).add(case["id"])
        case_group = case_runs.setdefault(category, {}).setdefault(
            case["id"],
            {"case": case, "runs": []},
        )
        case_group["runs"].append(item)
        group = summary.setdefault(category, {}).setdefault(
            tool_label,
            {
                "runs": 0,
                "statuses": {},
                "scores": [],
                "elapsed": [],
                "credits": [],
                "costs": [],
                "notes": [],
            },
        )
        group["runs"] += 1
        status = item["status"]
        group["statuses"][status] = group["statuses"].get(status, 0) + 1
        if score is not None:
            group["scores"].append(float(score))
        if item.get("elapsed_ms") is not None:
            group["elapsed"].append(float(item["elapsed_ms"]))
        if extra_metrics.get("credits") is not None:
            group["credits"].append(float(extra_metrics["credits"]))
        if extra_metrics.get("cost_dollars") is not None:
            group["costs"].append(float(extra_metrics["cost_dollars"]))
        if score == 0:
            group["notes"].append(failure_note(item))

    def avg(values: list[float]) -> float | None:
        return sum(values) / len(values) if values else None

    def whole(value: float | None) -> str:
        if value is None:
            return "n/a"
        return f"{round(value):,}"

    def evidence_label(score: float | None) -> str:
        if score is None:
            return "not scored"
        if score >= 0.75:
            return "complete"
        if score > 0:
            return "partial"
        return "missed"

    def evidence_class(score: float | None) -> str:
        if score is None:
            return "evidence-unknown"
        if score >= 0.75:
            return "evidence-complete"
        if score > 0:
            return "evidence-partial"
        return "evidence-missed"

    def category_title(category: str) -> str:
        titles = {
            "pdf_extraction": "PDF Extraction / OCR",
            "browser_automation": "Browser Automation",
            "scraping": "Scraping",
        }
        return titles.get(category, category.replace("_", " ").title())

    def case_workflow(case: dict[str, Any]) -> str:
        category = case["category"]
        input_data = case.get("input", {})
        if category == "pdf_extraction":
            if input_data.get("url"):
                return "Parse a known investigative PDF from local cache, with a source URL available for remote parsers."
            return "Parse a local investigative PDF from the fine-tuning corpus and preserve structure, names, and domain terms."
        if category == "browser_automation":
            return case.get(
                "task",
                "Use a browser to search a public OSINT source and return target evidence.",
            )
        if category == "scraping":
            return case.get(
                "task",
                "Retrieve a public source and preserve source-linked evidence.",
            )
        return "Run the configured source task and score against relevance probes."

    def input_html(case: dict[str, Any]) -> str:
        input_data = case.get("input", {})
        bits = []
        if input_data.get("url"):
            url = str(input_data["url"])
            bits.append(
                f"<dt>URL</dt><dd><a href='{html.escape(url)}'>{html.escape(url)}</a></dd>"
            )
        if input_data.get("path") and not input_data.get("url"):
            raw_path = str(input_data["path"])
            path = (ROOT / raw_path).resolve()
            bits.append(
                "<dt>PDF</dt>"
                f"<dd><a href='file://{html.escape(str(path))}'>{html.escape(raw_path)}</a></dd>"
            )
        if input_data.get("query"):
            bits.append(f"<dt>Query</dt><dd>{html.escape(str(input_data['query']))}</dd>")
        if input_data.get("page_range"):
            bits.append(f"<dt>Page range</dt><dd>{html.escape(str(input_data['page_range']))}</dd>")
        if input_data.get("search_value"):
            bits.append(f"<dt>Search</dt><dd>{html.escape(str(input_data['search_value']))}</dd>")
        return "<dl class='case-meta'>" + "".join(bits) + "</dl>" if bits else ""

    def probes_html(case: dict[str, Any]) -> str:
        probes = case.get("probes", [])
        labels = []
        for probe in probes[:6]:
            kind = probe.get("kind", "")
            value = str(probe.get("value", ""))
            if kind == "contains":
                labels.append(f"must contain: {value}")
            elif kind == "regex":
                labels.append(f"pattern: {value}")
            elif kind == "min_chars":
                labels.append(f"min chars: {value}")
            elif kind == "max_seconds":
                labels.append(f"max seconds: {value}")
            elif kind == "max_replacement_char_ratio":
                labels.append("low mojibake")
            else:
                labels.append(f"{kind}: {value}")
        if len(probes) > 6:
            labels.append(f"+{len(probes) - 6} more")
        return "".join(f"<span>{html.escape(label)}</span>" for label in labels)

    def task_brief_html(category: str) -> str:
        items = []
        for case_id, case_group in sorted(case_runs.get(category, {}).items()):
            case = case_group["case"]
            source = input_html(case)
            items.append(
                "<article class='task-item'>"
                f"<h3>{html.escape(case.get('title', case_id))}</h3>"
                f"<p>{html.escape(case_workflow(case))}</p>"
                f"{source}"
                "<div class='probe-list'>"
                f"{probes_html(case)}"
                "</div>"
                "</article>"
            )
        return (
            "<details class='task-brief'>"
            "<summary>"
            "<span>Task brief</span>"
            f"<strong>{len(items)} investigative cases</strong>"
            "</summary>"
            "<div class='task-grid'>"
            + "".join(items)
            + "</div>"
            "</details>"
        )

    def score_sort(group: dict[str, Any]) -> tuple[float, float, int]:
        avg_score = avg(group["scores"])
        pass_rate = group["statuses"].get("pass", 0) / group["runs"] if group["runs"] else 0
        return (avg_score if avg_score is not None else -1.0, pass_rate, -group["runs"])

    total_cases = sum(len(cases) for cases in category_cases.values())
    total_probes = sum(
        len(case_group["case"].get("probes", []))
        for groups in case_runs.values()
        for case_group in groups.values()
    )
    overview_rows = []
    category_sections = []

    for category in sorted(summary):
        groups = summary[category]
        ordered = sorted(groups.items(), key=lambda item: score_sort(item[1]), reverse=True)
        category_scores = [
            score
            for group in groups.values()
            for score in group["scores"]
        ]
        overview_rows.append(
            "<tr>"
            f"<td>{html.escape(category_title(category))}</td>"
            f"<td>{len(category_cases.get(category, set()))}</td>"
            f"<td>{pct(avg(category_scores))}</td>"
            f"<td>{evidence_label(avg(category_scores))}</td>"
            "</tr>"
        )

        table_rows = []
        chart_rows = []
        for tool_label, group in ordered:
            avg_score = avg(group["scores"])
            score_width = max(0, min(100, round((avg_score or 0) * 100)))
            avg_elapsed = avg(group["elapsed"])
            credits = round(sum(group["credits"])) if group["credits"] else None
            costs = sum(group["costs"]) if group["costs"] else None
            status_notes = [
                f"{count} {status}"
                for status, count in sorted(group["statuses"].items())
                if status != "pass"
            ]
            notes = []
            for note_value in group["notes"]:
                if note_value not in notes:
                    notes.append(note_value)
            if notes:
                note = "; ".join(notes[:2])
            elif status_notes:
                note = ", ".join(status_notes)
            else:
                note = "executed"
            spend_bits = []
            if credits is not None:
                spend_bits.append(f"{credits:,} credits")
            if costs is not None:
                spend_bits.append(f"${costs:.4f}")
            spend = ", ".join(spend_bits) if spend_bits else "n/a"
            table_rows.append(
                "<tr>"
                f"<td>{html.escape(tool_label)}</td>"
                f"<td class='{evidence_class(avg_score)}'>{evidence_label(avg_score)}</td>"
                f"<td class='mono'>{pct(avg_score)}</td>"
                f"<td class='mono'>{whole(avg_elapsed)} ms</td>"
                f"<td>{html.escape(spend)}</td>"
                f"<td>{html.escape(note)}</td>"
                + "</tr>"
            )
            chart_rows.append(
                "<div class='bar-row'>"
                f"<span>{html.escape(tool_label)}</span>"
                "<div class='bar-track'>"
                f"<div class='bar-fill' style='width:{score_width}%'></div>"
                "</div>"
                f"<strong>{pct(avg_score)}</strong>"
                "</div>"
            )

        fairness_notes = {
            "scraping": (
                "Scores measure preserved page evidence. Extraction-style tools "
                "(PixelRAG, Scraper Factory, Trafilatura) intentionally return less "
                "than the full page - read their scores as preservation, not quality."
            ),
            "pdf_extraction": (
                "Page-capped OCR (Surya, Marker) and extraction tools (LangExtract) "
                "trade the min-chars probes for speed or precision by design."
            ),
        }
        fairness_html = (
            f"<p class='meta'>{html.escape(fairness_notes[category])}</p>"
            if category in fairness_notes
            else ""
        )
        category_sections.append(
            "<section class='category'>"
            "<div class='section-head'>"
            f"<h2>{html.escape(category_title(category))}</h2>"
            f"<p>Open the task brief to inspect sources, search flows, and expected evidence.</p>"
            f"{fairness_html}"
            "</div>"
            f"{task_brief_html(category)}"
            "<div class='chart' aria-label='Average score by tool'>"
            + "\n".join(chart_rows)
            + "</div>"
            "<div class='table-wrap'>"
            "<table>"
            "<thead><tr>"
            "<th>Tool</th>"
            "<th>Evidence</th>"
            "<th>Coverage</th>"
            "<th>Speed</th>"
            "<th>Spend</th>"
            "<th>Note</th>"
            "</tr></thead><tbody>"
            + "\n".join(table_rows)
            + "</tbody></table></div>"
            "</section>"
        )

    overview_html = "\n".join(overview_rows) or "<tr><td colspan='4'>No benchmark results yet.</td></tr>"
    category_html = "\n".join(category_sections)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Tooling Benchmarks - Buried Signals</title>
  <script>
    if (new URLSearchParams(window.location.search).has("embed")) {{
      document.documentElement.classList.add("is-embedded");
    }}
  </script>
  <style>
    :root {{
      color-scheme: dark;
      --primary: #D4A853;
      --secondary: #5B8A8A;
      --neutral: #F5F2ED;
      --background: #16191B;
      --muted: #7A7873;
      --dim: #33342E;
      --panel: #202326;
      --paper: #E8DCC8;
    }}
    body {{
      margin: 0;
      font: 16px/1.55 "Space Grotesk", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--neutral);
      background:
        linear-gradient(rgba(232, 220, 200, 0.018) 1px, transparent 1px),
        linear-gradient(90deg, rgba(212, 168, 83, 0.016) 1px, transparent 1px),
        var(--background);
      background-size: 88px 88px;
    }}
    html.is-embedded,
    html.is-embedded body {{
      background: var(--background);
      background-image: none;
    }}
    body::before {{
      content: "";
      position: fixed;
      inset: 0 0 auto;
      height: 5px;
      background: linear-gradient(90deg, var(--primary), var(--secondary));
      opacity: 0.85;
      pointer-events: none;
      z-index: 10;
    }}
    html.is-embedded body::before {{
      display: none;
    }}
    main {{
      max-width: 1160px;
      margin: 0 auto;
      padding: 56px 24px 72px;
    }}
    html.is-embedded main {{
      padding-top: 0;
    }}
    .hero {{
      display: grid;
      grid-template-columns: minmax(0, 1.15fr) minmax(280px, 0.85fr);
      gap: 48px;
      align-items: end;
      min-height: 320px;
      border-bottom: 1px solid var(--dim);
      padding-bottom: 40px;
      margin-bottom: 40px;
    }}
    html.is-embedded .hero {{
      display: none;
    }}
    h1 {{
      font-size: clamp(44px, 7vw, 92px);
      line-height: 0.95;
      margin: 0 0 20px;
      letter-spacing: 0;
    }}
    .lead {{
      max-width: 680px;
      font-size: 20px;
      margin: 0;
      color: var(--paper);
    }}
    .meta, .section-head p {{
      color: var(--muted);
      margin: 0;
    }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 1px;
      background: var(--dim);
      border: 1px solid var(--dim);
      border-radius: 10px;
      overflow: hidden;
    }}
    .stat {{
      background: var(--panel);
      padding: 18px;
    }}
    .stat strong {{
      display: block;
      color: var(--primary);
      font: 700 32px/1 "Space Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
    }}
    .stat span {{
      display: block;
      margin-top: 8px;
      color: var(--muted);
      font: 700 10px/1.2 "Space Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }}
    .overview, .category {{
      margin-top: 44px;
    }}
    .section-head {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(240px, 0.55fr);
      gap: 32px;
      align-items: end;
      margin-bottom: 16px;
    }}
    .section-head p:last-child {{
      grid-column: 2;
      grid-row: 1;
      align-self: end;
      justify-self: end;
      max-width: 420px;
      text-align: right;
    }}
    h2 {{
      font-size: clamp(30px, 4vw, 48px);
      line-height: 1;
      margin: 0;
      letter-spacing: 0;
    }}
    .table-wrap {{
      overflow-x: auto;
      border: 1px solid var(--dim);
      border-radius: 10px;
      background: var(--panel);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: var(--panel);
    }}
    th, td {{
      padding: 13px 14px;
      border-bottom: 1px solid var(--dim);
      text-align: left;
      vertical-align: top;
    }}
    th {{
      color: var(--primary);
      background: rgba(212, 168, 83, 0.06);
      font: 700 10px/1.2 "Space Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }}
    tr:last-child td {{
      border-bottom: 0;
    }}
    td {{
      color: var(--paper);
    }}
    a {{
      color: var(--primary);
      text-decoration: none;
      overflow-wrap: anywhere;
    }}
    a:hover {{
      text-decoration: underline;
    }}
    .mono {{
      font-family: "Space Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
      color: var(--neutral);
    }}
    .evidence-complete {{
      color: var(--primary);
      font-weight: 700;
    }}
    .evidence-partial {{
      color: var(--paper);
      font-weight: 700;
    }}
    .evidence-missed, .evidence-unknown {{
      color: var(--muted);
      font-weight: 700;
    }}
    .task-brief {{
      margin: 0 0 18px;
      border: 1px solid var(--dim);
      border-radius: 10px;
      background: rgba(32, 35, 38, 0.78);
      overflow: hidden;
    }}
    .task-brief summary {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 18px;
      cursor: pointer;
      padding: 16px 18px;
      list-style: none;
    }}
    .task-brief summary::-webkit-details-marker {{
      display: none;
    }}
    .task-brief summary::before {{
      content: "+";
      color: var(--primary);
      font: 700 18px/1 "Space Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
    }}
    .task-brief[open] summary::before {{
      content: "-";
    }}
    .task-brief summary span {{
      flex: 1;
      color: var(--neutral);
      font-weight: 700;
    }}
    .task-brief summary strong {{
      color: var(--primary);
      font: 700 11px/1.3 "Space Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      white-space: nowrap;
    }}
    .task-grid {{
      display: grid;
      gap: 0;
      border-top: 1px solid var(--dim);
    }}
    .task-item {{
      padding: 18px;
      border-bottom: 1px solid var(--dim);
      background: rgba(22, 25, 27, 0.25);
    }}
    .task-item:last-child {{
      border-bottom: 0;
    }}
    .task-item h3 {{
      margin: 0 0 6px;
      color: var(--neutral);
      font-size: 17px;
      line-height: 1.25;
    }}
    .task-item p {{
      margin: 0 0 14px;
      max-width: 860px;
      color: var(--muted);
      font-size: 14px;
    }}
    .case-list {{
      display: grid;
      gap: 10px;
      margin: 0 0 18px;
    }}
    .case-card {{
      border: 1px solid var(--dim);
      border-radius: 10px;
      background: rgba(32, 35, 38, 0.78);
      overflow: hidden;
    }}
    .case-card summary {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 20px;
      align-items: center;
      cursor: pointer;
      padding: 16px 18px;
      list-style: none;
    }}
    .case-card summary::-webkit-details-marker {{
      display: none;
    }}
    .case-card summary::before {{
      content: "+";
      color: var(--primary);
      font: 700 18px/1 "Space Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
      margin-right: 10px;
      grid-column: 1;
      grid-row: 1;
      align-self: start;
    }}
    .case-card[open] summary::before {{
      content: "-";
    }}
    .case-card summary > span {{
      display: grid;
      gap: 5px;
      min-width: 0;
      padding-left: 26px;
    }}
    .case-card strong {{
      color: var(--neutral);
      font-size: 16px;
      line-height: 1.25;
    }}
    .case-card em {{
      color: var(--muted);
      font-style: normal;
      font-size: 13px;
      line-height: 1.4;
    }}
    .case-card b {{
      color: var(--primary);
      font: 700 11px/1.3 "Space Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
      letter-spacing: 0.05em;
      white-space: nowrap;
      text-transform: uppercase;
    }}
    .case-detail {{
      border-top: 1px solid var(--dim);
      padding: 16px 18px 18px 44px;
    }}
    .case-detail p {{
      margin: 0 0 14px;
      max-width: 860px;
      color: var(--paper);
    }}
    .case-meta {{
      display: grid;
      grid-template-columns: 92px minmax(0, 1fr);
      gap: 8px 14px;
      margin: 0 0 14px;
    }}
    .case-meta dt {{
      color: var(--primary);
      font: 700 10px/1.4 "Space Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }}
    .case-meta dd {{
      margin: 0;
      color: var(--paper);
      overflow-wrap: anywhere;
    }}
    .probe-list {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin: 0 0 14px;
    }}
    .probe-list span {{
      border: 1px solid var(--dim);
      border-radius: 999px;
      padding: 5px 9px;
      color: var(--muted);
      font: 700 10px/1.2 "Space Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
    }}
    .mini-table {{
      max-width: 640px;
      font-size: 13px;
      border: 1px solid var(--dim);
      border-radius: 8px;
      overflow: hidden;
    }}
    .mini-table th, .mini-table td {{
      padding: 8px 10px;
    }}
    .chart {{
      display: grid;
      gap: 10px;
      margin: 0 0 18px;
      padding: 18px;
      border: 1px solid var(--dim);
      border-radius: 10px;
      background: rgba(32, 35, 38, 0.82);
    }}
    .bar-row {{
      display: grid;
      grid-template-columns: minmax(160px, 240px) minmax(140px, 1fr) 56px;
      gap: 14px;
      align-items: center;
    }}
    .bar-row span {{
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }}
    .bar-track {{
      height: 12px;
      border-radius: 999px;
      background: var(--dim);
      overflow: hidden;
    }}
    .bar-fill {{
      height: 100%;
      min-width: 2px;
      border-radius: inherit;
      background: linear-gradient(90deg, var(--primary), var(--secondary));
    }}
    .bar-row strong {{
      color: var(--neutral);
      font: 700 13px/1 "Space Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
      text-align: right;
    }}
    @media (max-width: 760px) {{
      main {{
        padding: 34px 16px 48px;
      }}
      .hero, .section-head {{
        grid-template-columns: 1fr;
      }}
      .section-head h2, .section-head p:last-child {{
        grid-column: 1;
        grid-row: auto;
        justify-self: start;
        text-align: left;
      }}
      .bar-row {{
        grid-template-columns: 1fr;
        gap: 7px;
      }}
      .case-card summary {{
        grid-template-columns: 1fr;
        gap: 10px;
      }}
      .task-brief summary {{
        align-items: flex-start;
      }}
      .task-brief summary strong {{
        white-space: normal;
      }}
      .case-card b {{
        white-space: normal;
        padding-left: 26px;
      }}
      .case-detail {{
        padding-left: 18px;
      }}
      .case-meta {{
        grid-template-columns: 1fr;
      }}
      .bar-row strong {{
        text-align: left;
      }}
    }}
  </style>
</head>
<body>
  <main>
    <header class="hero">
      <div>
        <h1>Tooling benchmarks</h1>
        <p class="lead">A compact readout of OSINT-oriented tasks. Browser scores require completing a search workflow and returning target evidence; output volume is not treated as quality.</p>
      </div>
      <div class="stats" aria-label="Benchmark totals">
        <div class="stat"><strong>{len(summary)}</strong><span>Categories</span></div>
        <div class="stat"><strong>{total_cases}</strong><span>Cases</span></div>
        <div class="stat"><strong>{total_probes}</strong><span>Evidence probes</span></div>
      </div>
    </header>

    <section class="overview">
      <div class="section-head">
        <h2>Category readout</h2>
        <p class="meta">Coverage by task category.</p>
      </div>
      <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Category</th>
            <th>Cases</th>
            <th>Coverage</th>
            <th>Evidence</th>
          </tr>
        </thead>
        <tbody>
          {overview_html}
        </tbody>
      </table>
      </div>
    </section>

    {category_html}
  </main>
  <script>
    (() => {{
      const params = new URLSearchParams(window.location.search);
      if (params.has("embed")) {{
        document.documentElement.classList.add("is-embedded");
      }}

      if (window.parent === window) return;

      const sendHeight = () => {{
        const height = Math.max(
          document.body.scrollHeight,
          document.documentElement.scrollHeight,
          document.body.offsetHeight,
          document.documentElement.offsetHeight
        );
        window.parent.postMessage({{
          type: "buriedsignals:benchmarks-height",
          height
        }}, "*");
      }};

      window.addEventListener("load", sendHeight);
      document.addEventListener("toggle", sendHeight, true);
      new ResizeObserver(sendHeight).observe(document.body);
      requestAnimationFrame(sendHeight);
      setTimeout(sendHeight, 250);
    }})();
  </script>
</body>
</html>
"""


def ratio(value: Any) -> str:
    if value is None or value == "":
        return "n/a"
    return f"{float(value):.6f}"


def cmd_pdf_audit(args: argparse.Namespace) -> int:
    pdfs = [Path(p) for p in args.paths]
    if not pdfs:
        pdfs = sorted((ROOT.parent / "fine-tuning" / "source-pdfs").glob("*.pdf"))
    rows = []
    for pdf in pdfs:
        if not pdf.exists():
            continue
        raw = pdf.read_bytes()
        pages = len(re.findall(rb"/Type\s*/Page\b", raw))
        images = len(re.findall(rb"/Subtype\s*/Image\b", raw))
        text_ops = raw.count(b"BT")
        size_mb = pdf.stat().st_size / 1_000_000
        rows.append((images, pages, text_ops, size_mb, pdf))
    rows.sort(reverse=True)
    for images, pages, text_ops, size_mb, pdf in rows:
        print(
            f"{pdf} pages={pages} images={images} text_ops={text_ops} size_mb={size_mb:.1f}"
        )
    return 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="bs-bench")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="List benchmark cases and tools.")
    p_list.add_argument("--category", action="append")
    p_list.set_defaults(func=cmd_list)

    p_doctor = sub.add_parser("doctor", help="Show which tools are runnable.")
    p_doctor.add_argument("--category", action="append")
    p_doctor.add_argument("--tool", action="append")
    p_doctor.add_argument("--allow-network", action="store_true")
    p_doctor.add_argument("--allow-paid", action="store_true")
    p_doctor.add_argument("--include-unconfigured", action="store_true")
    p_doctor.add_argument("--env-file")
    p_doctor.set_defaults(func=cmd_doctor)

    p_run = sub.add_parser("run", help="Run selected benchmarks.")
    p_run.add_argument("--category", action="append")
    p_run.add_argument("--case", action="append")
    p_run.add_argument("--tool", action="append")
    p_run.add_argument("--timeout", type=int, default=90)
    p_run.add_argument("--allow-network", action="store_true")
    p_run.add_argument("--allow-paid", action="store_true")
    p_run.add_argument("--include-unconfigured", action="store_true")
    p_run.add_argument("--env-file")
    p_run.set_defaults(func=cmd_run)

    p_report = sub.add_parser("report", help="Render an HTML report.")
    p_report.add_argument("--input", default="results/latest.json")
    p_report.add_argument("--output", default="public/index.html")
    p_report.set_defaults(func=cmd_report)

    p_combine = sub.add_parser(
        "combine",
        help="Combine multiple result JSON files into one report payload.",
    )
    p_combine.add_argument("inputs", nargs="+")
    p_combine.add_argument("--output", default=f"results/combined-{stamp()}.json")
    p_combine.add_argument("--update-latest", action="store_true")
    p_combine.set_defaults(func=cmd_combine)

    p_export = sub.add_parser(
        "export-site",
        help="Copy the latest static report and JSON to another static directory.",
    )
    p_export.add_argument("--input", default="results/latest.json")
    p_export.add_argument("--html", default="public/index.html")
    p_export.add_argument(
        "--target",
        default="site-static/benchmarks",
    )
    p_export.set_defaults(func=cmd_export_site)

    p_pdf = sub.add_parser("pdf-audit", help="Rank local PDFs by rough OCR/layout difficulty.")
    p_pdf.add_argument("paths", nargs="*")
    p_pdf.set_defaults(func=cmd_pdf_audit)
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
