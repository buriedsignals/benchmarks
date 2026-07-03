"""browser-use CLI adapter (2026 redesign: direct CDP control, Python-on-stdin).

Launches a dedicated headless Chromium (Playwright's headless shell) with a
CDP port, points the browser-use daemon at it via BU_CDP_URL, and drives the
generic form workflow through the CLI's pre-imported helpers (new_tab,
wait_for_load, js). Each navigation-triggering step is its own synchronous
js() call so the CDP execution context is never awaited across a navigation.
No personal Chrome is touched and no LLM is involved. The case prompt is
deliberately NOT passed anywhere near scored stdout.
"""
from __future__ import annotations

import glob
import json
import os
import subprocess
import sys
import time
import urllib.request

CDP_PORT = 9243


def find_headless_shell() -> str | None:
    pattern = os.path.expanduser(
        "~/Library/Caches/ms-playwright/chromium_headless_shell-*/chrome-*/headless_shell"
    )
    matches = sorted(glob.glob(pattern))
    return matches[-1] if matches else None


def cdp_alive() -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json/version", timeout=2):
            return True
    except Exception:
        return False


def ensure_browser(profile_dir: str) -> subprocess.Popen | None:
    if cdp_alive():
        print("[browser-use adapter] reusing CDP browser", file=sys.stderr)
        return None
    shell = find_headless_shell()
    if not shell:
        print(
            "no Playwright chromium_headless_shell found; run: uvx --from playwright playwright install chromium",
            file=sys.stderr,
        )
        raise SystemExit(2)
    proc = subprocess.Popen(
        [
            shell,
            f"--remote-debugging-port={CDP_PORT}",
            f"--user-data-dir={profile_dir}",
            "--no-first-run",
            "--disable-gpu",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(50):
        if cdp_alive():
            return proc
        time.sleep(0.2)
    proc.terminate()
    print("headless shell did not expose CDP in time", file=sys.stderr)
    raise SystemExit(1)


def build_script(
    url: str,
    search_selector: str,
    search_value: str,
    submit_selector: str,
    result_selector: str,
    follow_selector: str,
) -> str:
    j = json.dumps  # embeds Python strings as JS string literals
    submit_js = (
        "(() => {"
        f"const i = document.querySelector({j(search_selector)});"
        "if (!i) return 'missing-input';"
        "i.focus();"
        f"i.value = {j(search_value)};"
        "i.dispatchEvent(new Event('input', {bubbles: true}));"
        "i.dispatchEvent(new Event('change', {bubbles: true}));"
        f"const s = {j(submit_selector)} ? document.querySelector({j(submit_selector)}) : null;"
        "if (s) { s.click(); return 'clicked-submit'; }"
        "if (i.form && i.form.requestSubmit) { i.form.requestSubmit(); return 'form-submit'; }"
        "i.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', code: 'Enter', bubbles: true}));"
        "return 'enter-key';"
        "})()"
    )

    def click_js(selector: str) -> str:
        return (
            "(() => {"
            f"const el = document.querySelector({j(selector)});"
            "if (!el) return 'missing';"
            "el.click();"
            "return 'clicked';"
            "})()"
        )

    extract_js = (
        "(() => {"
        "const links = Array.from(document.querySelectorAll('a')).slice(0, 80)"
        ".map(a => ({text: a.innerText, href: a.href}));"
        "return JSON.stringify({url: location.href, title: document.title,"
        " text: document.body ? document.body.innerText.slice(0, 18000) : '', links});"
        "})()"
    )

    lines = [
        "import json, sys, time",
        f"new_tab({j(url)})",
        "wait_for_load(20)",
        "time.sleep(1)",
        f"print('step submit:', js({j(submit_js)}), file=sys.stderr)",
        "time.sleep(4)",
        "wait_for_load(15)",
    ]
    if result_selector:
        lines += [
            f"print('step result:', js({j(click_js(result_selector))}), file=sys.stderr)",
            "time.sleep(4)",
            "wait_for_load(15)",
        ]
    if follow_selector:
        lines += [
            f"print('step follow:', js({j(click_js(follow_selector))}), file=sys.stderr)",
            "time.sleep(4)",
            "wait_for_load(15)",
        ]
    lines += [
        f"data = js({j(extract_js)})",
        "print(data if isinstance(data, str) else json.dumps(data, indent=2))",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    if len(sys.argv) != 9:
        print(
            "usage: browser_use_stdin.py <url> <output_dir> <timeout_seconds> "
            "<search_selector> <search_value> <submit_selector> <result_selector> <follow_selector>",
            file=sys.stderr,
        )
        return 2
    url, output_dir, timeout_seconds = sys.argv[1], sys.argv[2], sys.argv[3]
    search_selector, search_value, submit_selector, result_selector, follow_selector = sys.argv[4:9]

    profile_dir = os.path.join(output_dir, "browser-use-profile")
    started = ensure_browser(profile_dir)
    try:
        stdin_script = build_script(
            url, search_selector, search_value, submit_selector, result_selector, follow_selector
        )
        env = dict(os.environ)
        env["BU_CDP_URL"] = f"http://127.0.0.1:{CDP_PORT}"
        proc = subprocess.run(
            ["uvx", "browser-use"],
            input=stdin_script,
            capture_output=True,
            text=True,
            timeout=max(60, int(float(timeout_seconds)) - 30),
            env=env,
        )
        if proc.stderr:
            print(proc.stderr[-2000:], file=sys.stderr)
        if proc.stdout:
            print(proc.stdout)
        return proc.returncode
    finally:
        if started is not None:
            started.terminate()


if __name__ == "__main__":
    raise SystemExit(main())
