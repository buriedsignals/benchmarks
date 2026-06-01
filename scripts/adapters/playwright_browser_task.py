from __future__ import annotations

import json
import sys

from playwright.sync_api import sync_playwright


def main() -> int:
    if len(sys.argv) != 9:
        print(
            "usage: playwright_browser_task.py <url> <timeout-seconds> "
            "<search-selector> <search-value> <submit-selector> "
            "<result-selector> <follow-selector> <prompt>",
            file=sys.stderr,
        )
        return 2
    (
        url,
        timeout_seconds,
        search_selector,
        search_value,
        submit_selector,
        result_selector,
        follow_selector,
        prompt,
    ) = sys.argv[1:]
    timeout_ms = int(float(timeout_seconds) * 1000)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        page.locator(search_selector).first.fill(search_value, timeout=8_000)
        if submit_selector:
            page.locator(submit_selector).first.click(timeout=8_000)
        else:
            page.locator(search_selector).first.press("Enter")
        page.wait_for_timeout(2_500)
        if result_selector:
            try:
                page.locator(result_selector).first.click(timeout=10_000)
                page.wait_for_timeout(2_500)
            except Exception as exc:
                print(f"result click failed: {exc}", file=sys.stderr)
        if follow_selector:
            try:
                page.locator(follow_selector).first.click(timeout=10_000)
                page.wait_for_timeout(2_500)
            except Exception as exc:
                print(f"follow click failed: {exc}", file=sys.stderr)
        text = page.locator("body").inner_text(timeout=8_000)
        links = page.locator("a").evaluate_all(
            "(els) => els.slice(0, 80).map((a) => ({ text: a.innerText, href: a.href }))"
        )
        print(
            json.dumps(
                {
                    "url": page.url,
                    "title": page.title(),
                    "task": prompt,
                    "text": text[:18_000],
                    "links": links,
                },
                indent=2,
            )
        )
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
