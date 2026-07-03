"""Minimal generic Scrapy spider for the scraping benchmark.

Fetches one URL with Scrapy's default fetch layer and emits body text plus
the first 80 links to stdout. No per-site selectors or parse rules, so the
benchmark measures Scrapy's stock retrieval, not hand-written extraction.
Run: scrapy runspider scrapy_case_spider.py -a url=<url> --nolog
"""
from __future__ import annotations

import scrapy


class CaseFetchSpider(scrapy.Spider):
    name = "case_fetch"

    def __init__(self, url: str | None = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not url:
            raise ValueError("pass the target with -a url=<url>")
        self.start_urls = [url]

    def parse(self, response):
        texts = [t.strip() for t in response.xpath("//body//text()").getall()]
        print("\n".join(t for t in texts if t))
        print("links:")
        for anchor in response.css("a")[:80]:
            label = " ".join(anchor.css("::text").getall()).strip()
            href = anchor.attrib.get("href", "")
            print(f"- {label} {href}".strip())
