# Buried Signals Benchmarks

This project measures OSINT-adjacent tools for document parsing, browser automation, and scraping. It produces JSON run artifacts plus a static HTML report in `public/index.html`.

The first implemented category is runnable locally with `pdftotext`; additional local/open-source PDF tools, browser tools, Firecrawl, and Obscura are wired into the runner. Paid API tools skip until their keys are present, and paid/network execution still requires explicit flags.

## Categories

- `pdf_extraction`: LlamaParse, Fireparse/Firecrawl document parse, LangExtract, Surya OCR, Extend Parse 2.0, Docling, and a Poppler baseline.
- `browser_automation`: browser-use terminal, browser-harness, dev-browser, and a Playwright script on the same form-driven investigative tasks.
- `scraping`: Firecrawl scrape, Exa contents, Obscura fetch, MarkItDown, Crawl4AI, and Scrapling (stealthy fetch). Search endpoints are intentionally excluded because they answer a different use case.

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

- Docling: `uvx --from docling-slim docling`
- Surya OCR: `uvx --from surya-ocr surya_ocr`
- browser-use: `uvx --from browser-use browser-use`
- MarkItDown: `uvx markitdown <url>` (plain-HTTP fetch plus HTML-to-Markdown conversion)
- Crawl4AI: `uvx --from crawl4ai crwl <url> -o markdown` (Playwright-rendered; reuses the locally installed Playwright browsers)
- Scrapling: `uvx --from "scrapling[shell]" scrapling extract stealthy-fetch <url> <out.md>` via `scripts/adapters/scrapling_fetch.py`; stealthy-fetch (Camoufox) is the project's headline anti-bot mode and is the benchmarked configuration

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

- `pdftotext_baseline` is fast and strong on the current public born-digital PDF set.
- Browser automation is now scored on four investigative form workflows, not snapshots: Companies House filing history, OpenSanctions entity screening, Wikidata entity identity, and OpenStreetMap place lookup.
- `dev-browser` and the `Playwright script` completed all four browser workflows and returned the target evidence.
- `browser-harness` currently fails the browser tasks with a CDP keepalive timeout.
- `browser-use` terminal executed but returned no target evidence with the current adapter, so it is shown as missed rather than successful.
- Scraping now uses harder registry/civic-monitoring sources from the Scoutpost benchmark family: Companies House, Basel-Stadt protocols, Zurich Gemeinderat protocols, and Lausanne Conseil communal PVs.
- `Firecrawl scrape`, `Exa contents API`, and `Obscura headless browser` are compared as scraping/content retrieval tools; Firecrawl and Exa search endpoints are excluded.
- `Exa contents API` returned explicit retrieval errors on two civic pages in the latest scraping run; those are scored as failures, not accidental URL/probe matches.
