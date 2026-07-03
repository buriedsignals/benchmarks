# Buried Signals Benchmarks

This project measures OSINT-adjacent tools for document parsing, browser automation, and scraping. It produces JSON run artifacts plus a static HTML report in `public/index.html`.

The first implemented category is runnable locally with `pdftotext`; additional local/open-source PDF tools, browser tools, Firecrawl, and Obscura are wired into the runner. Paid API tools skip until their keys are present, and paid/network execution still requires explicit flags.

## Categories

- `pdf_extraction`: LlamaParse, Fireparse/Firecrawl document parse, LangExtract, Surya OCR, Marker, Extend Parse 2.0, Docling, and a Poppler baseline.
- `browser_automation`: browser-use CLI (direct CDP control), dev-browser, a Playwright script, and the Stagehand agent on the same form-driven investigative tasks.
- `scraping`: Firecrawl scrape, Exa contents, Obscura fetch, MarkItDown, Crawl4AI, Scrapling (stealthy fetch), a generic Scrapy spider, Trafilatura, and PixelRAG pixel-native read. Search endpoints are intentionally excluded because they answer a different use case.

## Commands

```bash
python3 -m benchmarkers.cli list
python3 -m benchmarkers.cli doctor
python3 -m benchmarkers.cli run --category pdf_extraction --tool pdftotext_baseline
python3 -m benchmarkers.cli report
open public/index.html
```

If `benchmarks/.env` exists, it is loaded automatically before `doctor` and `run`.
Use `--env-file <path>` only when you want to point at a different dotenv.

Network/API tools are gated:

```bash
python3 -m benchmarkers.cli doctor --allow-network --allow-paid
python3 -m benchmarkers.cli run --category scraping --allow-network --allow-paid
```

Reports can be built from one run, or combined from several runs to avoid re-spending paid credits:

```bash
python3 -m benchmarkers.cli combine \
  results/run-a/results.json \
  results/run-b/results.json \
  --output results/combined-current.json \
  --update-latest
python3 -m benchmarkers.cli report
```

To load keys from a global dotenv instead of the local `.env`:

```bash
python3 -m benchmarkers.cli doctor --allow-network --allow-paid --env-file ~/.claude/.env
python3 -m benchmarkers.cli run --category scraping --allow-network --allow-paid --env-file ~/.claude/.env
```

The runner writes:

- `results/<timestamp>/results.json`
- `results/latest.json`
- `public/index.html`

Copy the static report and JSON into another static directory when needed:

```bash
python3 -m benchmarkers.cli export-site --target site-static/benchmarks
```

## API Keys

Do not commit keys. The runner checks environment variables and otherwise skips tools.

Expected variables:

- `FIRECRAWL_API_KEY`
- `EXA_API_KEY`
- `LLAMA_CLOUD_API_KEY`
- `EXTEND_API_KEY`
- `LANGEXTRACT_MODEL`
- `LANGEXTRACT_PROVIDER` optional; set to `openai` for OpenAI-compatible endpoints
- `LANGEXTRACT_MODEL_URL` optional; set to an Ollama URL such as `http://localhost:11434`
- `LANGEXTRACT_BASE_URL` optional; OpenAI-compatible base URL when `LANGEXTRACT_PROVIDER=openai`
- `LANGEXTRACT_API_KEY` only when the selected LangExtract model backend requires a cloud/API key

Some tools may also use their own CLI auth stores. Firecrawl, for example, can use its configured CLI auth.

`LANGEXTRACT_MODEL` is required to run LangExtract. For local Ollama, use a model such as `gemma2:2b` and optionally `LANGEXTRACT_MODEL_URL=http://localhost:11434`; no LangExtract API key is required. For OpenAI-compatible endpoints, set `LANGEXTRACT_PROVIDER=openai`, `LANGEXTRACT_BASE_URL`, and the provider key in `LANGEXTRACT_API_KEY`. Some CLIs, including Firecrawl, can also use their own auth stores.

## Local Tool Installs

Large binaries and model caches are deliberately not committed.

Obscura is installed locally under `bin/obscura/` from the official macOS Apple Silicon release:

```bash
mkdir -p bin/obscura
curl -sSL https://github.com/h4ckf0r0day/obscura/releases/latest/download/obscura-aarch64-macos.tar.gz \
  -o /private/tmp/obscura-aarch64-macos.tar.gz
tar -xzf /private/tmp/obscura-aarch64-macos.tar.gz -C bin/obscura
```

The adapter uses:

```bash
bin/obscura/obscura fetch <url> --dump text --timeout <seconds> --quiet
```

Docling, Surya, and browser-use are run through `uvx` so their large Python environments and model artifacts stay outside git:

- Marker: `uvx --from marker-pdf marker_single` via `scripts/adapters/marker_parse.py` (page-capped like Surya; give it a warm-model timeout — its June 2026 drop was a first-run download timing out, not a tool failure). MinerU was evaluated 2026-07-03 and excluded: its uvx pipeline backend fails on an internal missing dependency.
- Docling: `uvx --from docling-slim docling`
- Surya OCR: `uvx --from surya-ocr surya_ocr`
- Stagehand: `node scripts/adapters/stagehand/run.mjs <url> <instruction>` (tracked npm project; install deps once with `npm install --prefix scripts/adapters/stagehand`; agentic act/execute loop, LLM via OpenRouter `OPENROUTER_API_KEY`, override model with `STAGEHAND_MODEL`, default `openai/gpt-4o-mini`; scored stdout carries only the final page-evidence dump)
- browser-use: `uvx browser-use` driven by `scripts/adapters/browser_use_stdin.py` — the 2026 CLI redesign (Python-on-stdin, direct CDP). The adapter launches Playwright's `chromium_headless_shell` on a private CDP port and points the daemon at it via `BU_CDP_URL`, so no personal Chrome is involved and no LLM is required
- MarkItDown: `uvx markitdown <url>` (plain-HTTP fetch plus HTML-to-Markdown conversion)
- Crawl4AI: `uvx --from crawl4ai crwl <url> -o markdown` (Playwright-rendered; reuses the locally installed Playwright browsers)
- Scrapling: `uvx --from "scrapling[shell]" scrapling extract stealthy-fetch <url> <out.md>` via `scripts/adapters/scrapling_fetch.py`; stealthy-fetch (Camoufox) is the project's headline anti-bot mode and is the benchmarked configuration
- Trafilatura: `uvx trafilatura -u <url>` (main-content extractor baseline; expect low scores on label-preservation probes by design)
- Scrapy: `uvx --from scrapy scrapy runspider scripts/adapters/scrapy_case_spider.py -a url=<url> --nolog` (minimal generic spider: body text + first 80 links, stock settings, no per-site parse rules)
- PixelRAG: `scripts/adapters/pixelrag_read.py` renders the page to screenshot tiles with `uvx --from pixelrag pixelshot`, then a vision model via OpenRouter (`OPENROUTER_API_KEY`, default `google/gemini-2.5-flash`, override with `PIXELRAG_VLM_MODEL`) transcribes the task-relevant content; scored on the model's extraction, not raw page text

## Difficult PDF Fixtures

The PDF set is intentionally small and limited to public source URLs, with local cached copies under `../fine-tuning/source-pdfs` used for repeatable local parsing:

- `shultz-follow-the-money.pdf`: public policy manual with non-linear front matter, budget/oil revenue terminology, and policy-report layout.
- `unesco-story-based-inquiry.pdf`: public UNESCO investigative manual for throughput, chapter extraction, and method terminology.
- `gijn-citizen-investigations.pdf`: public GIJN guide with concrete OSINT tasks, organization/entity probes, and image-heavy pages.

Rank available PDFs by rough extraction difficulty:

```bash
python3 -m benchmarkers.cli pdf-audit
```

## Publishing

The repository includes the latest static report at `public/index.html`. GitHub Pages can publish that directory directly, which makes the report easy to iframe from another site.

Current notable findings in the report:

- `pdftotext_baseline` is fast and strong on the current public born-digital PDF set. The PDF matrix is complete as of 2026-07-03 (every tool ran every case, except one LlamaParse parse pending budget approval); the earlier 98% category average was a sparse-matrix artifact — the honest full matrix reads 93%.
- The runner now carries a source-liveness guard: output that looks like a 404/error page is marked `invalid_source` and excluded from scoring instead of being probe-scored, so the June rot failure mode cannot silently recur.
- Browser automation is now scored on four investigative form workflows, not snapshots: Companies House filing history, OpenSanctions entity screening, Wikidata entity identity, and OpenStreetMap place lookup.
- Browser candidates evaluated 2026-07-03: `Stagehand` (agentic, included at 92%), `playwright-mcp` (skipped: wraps Playwright, which is benchmarked directly), `zendriver` (skipped: anti-detection is moot on cooperative registries), `lightpanda` 0.3.4 (skipped: cannot complete navigation to Wikidata over CDP — engine compatibility not ready), `Skyvern` (skipped: Docker-heavy, duplicates Stagehand's niche).
- `dev-browser`, the `Playwright script`, and the rebuilt `browser-use CLI` all complete the four browser workflows with full target evidence (verified 2026-07-03, after removing a prompt-echo contamination that had leaked probe terms into scored output — the 1.0s are genuine either way).
- `browser-harness` was removed from the benchmark on 2026-07-03: its editable install points at a deleted source directory and the executable cannot start, so its historical 0% was environmental, not a tool result.
- `browser-use` scored 0% in June only because the old adapter drove the deprecated agentic terminal; the redesigned CLI adapter scores 100% on all four workflows.
- Scraping uses harder registry/civic-monitoring sources from the Scoutpost benchmark family: Companies House, Basel-Stadt protocols, Zurich Gemeinderat sessions, and Lausanne Conseil communal séances. Firecrawl and Exa search endpoints remain excluded.
- 2026-07-03 verification: the Zurich and Lausanne case URLs had rotted to 404 pages — and were already dead during the 2026-06-01 run, so the earlier published scores for those two cases were partly earned on 404 chrome via loose substring probes. Both cases now point at the live replacement pages with page-specific probes, and every scraping tool was re-run.
- The scraping set is 8 cases: the 4 original registry/civic sources plus 4 adopted from the Scoutpost civic suite (Bern Stadtrat, Bozeman City Commission, Madison Common Council, Zermatt Gemeinde) in `cases/scraping-scoutpost.json`. Three of Scoutpost's own scenario URLs were rotten (Zurich, Lausanne, Bern) and were replaced with the live pages here.
- Over all 8 cases, `Scrapling stealthy fetch` and `Crawl4AI` score 100%; `Scrapy` and `MarkItDown` 88% (both zero only on Bozeman's bot-protected CivicPlus CMS — plain HTTP is refused); `Firecrawl scrape` 79%, including a total miss on the Zermatt homepage where `--only-main-content` strips the whole page to image markdown.
- `Exa contents API` scores 79% on the live pages — its June "failures" were the dead URLs, not a retrieval defect. `Obscura headless browser` scores 50%: the Basel and Zurich cookie walls reduce it to banner-only or empty output.
- `PixelRAG pixel-native read` (83%) renders pages to screenshot tiles and has a vision model extract the task-relevant content (OpenRouter backend). It reads through cookie banners that blind Obscura, but is scored on the model's extraction rather than raw page text and deliberately trades bulk preservation (min-chars probes) for precision.
- `Tow Center Scraper Factory` (29%) LLM-generates a Playwright scraper per source and emits structured title/date/url records; content-preservation probes score that low even though its Zurich session extraction is the strongest structured monitoring output in the set. Its Basel generation fails inside the factory's page-analysis step.
- `autoscraper` was evaluated and excluded: it must be trained on example wanted-values that for these cases are the probe targets themselves, which would leak answers into the tool under test.
