from __future__ import annotations

import subprocess
import sys


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uvx", "--from", "browser-use", "browser-use", *args],
        text=True,
        capture_output=True,
        check=False,
    )


def main() -> int:
    if len(sys.argv) != 10:
        print(
            "usage: browser_use_cli.py <case-id> <url> <timeout-seconds> "
            "<search-selector> <search-value> <submit-selector> "
            "<result-selector> <follow-selector> <prompt>",
            file=sys.stderr,
        )
        return 2
    (
        case_id,
        url,
        _timeout,
        search_selector,
        search_value,
        submit_selector,
        result_selector,
        follow_selector,
        prompt,
    ) = sys.argv[1:]
    session = f"bs-bench-{case_id}"
    opened = run(["--session", session, "--json", "open", url])
    if opened.stderr:
        print(opened.stderr, file=sys.stderr, end="")
    if opened.returncode != 0:
        print(opened.stdout, end="")
        return opened.returncode
    script = f"""
(async () => {{
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const pick = sel => sel ? document.querySelector(sel) : null;
  const input = pick({search_selector!r});
  if (!input) {{
    return {{ error: 'missing search input', url: location.href, title: document.title, text: document.body ? document.body.innerText.slice(0, 18000) : '' }};
  }}
  input.focus();
  input.value = {search_value!r};
  input.dispatchEvent(new Event('input', {{ bubbles: true }}));
  input.dispatchEvent(new Event('change', {{ bubbles: true }}));
  const submit = pick({submit_selector!r});
  if (submit) submit.click();
  else if (input.form && input.form.requestSubmit) input.form.requestSubmit();
  else input.dispatchEvent(new KeyboardEvent('keydown', {{ key: 'Enter', code: 'Enter', bubbles: true }}));
  await sleep(2500);
  const result = pick({result_selector!r});
  if (result) {{ result.click(); await sleep(2500); }}
  const follow = pick({follow_selector!r});
  if (follow) {{ follow.click(); await sleep(2500); }}
  const links = Array.from(document.querySelectorAll('a')).slice(0, 80).map(a => ({{ text: a.innerText, href: a.href }}));
  return {{ url: location.href, title: document.title, task: {prompt!r}, text: document.body ? document.body.innerText.slice(0, 18000) : '', links }};
}})()
"""
    evaluated = run(["--session", session, "--json", "eval", script])
    if evaluated.stderr:
        print(evaluated.stderr, file=sys.stderr, end="")
    print(evaluated.stdout, end="")
    close = run(["--session", session, "--json", "close"])
    if close.stderr:
        print(close.stderr, file=sys.stderr, end="")
    return evaluated.returncode


if __name__ == "__main__":
    raise SystemExit(main())
