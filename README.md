<div align="center">

# Buried Signals Benchmarks

### Reproducible tests for tools journalists use to read documents, work through websites, find sources, and collect public records.

**A small, inspectable benchmark harness for comparing tools on real public-source tasks. It records the command, output, score, and failure state—rather than asking readers to trust a leaderboard.**

[Quick start](#quick-start) · [Methodology](docs/methodology.md) · [Latest report](https://buriedsignals.github.io/benchmarks/) · [Contributing](#contributing)

[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-0b77b5?style=for-the-badge&logo=opensourceinitiative&logoColor=white)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9%2B-3776ab?style=for-the-badge&logo=python&logoColor=white)](pyproject.toml)
[![Report](https://img.shields.io/badge/report-GitHub%20Pages-222222?style=for-the-badge&logo=githubpages&logoColor=white)](https://buriedsignals.github.io/benchmarks/)

Built and maintained by [**Buried Signals**](https://buriedsignals.com/)

</div>

---

## What this is

This repository benchmarks four kinds of tools against public, journalist-relevant tasks:

- **PDF extraction** — preserve text, structure, and evidence from difficult documents.
- **Browser automation** — complete multi-step public-record workflows rather than merely load a page.
- **Web scraping** — retrieve civic and registry pages while retaining the details a reporter needs.
- **Search** — find useful, source-linked material for a concrete research question.

It also preserves one completed **OSINT model benchmark** as a fixed July 2026 study. It is not a runnable CI job or a rolling leaderboard: the work depended on controlled access to several model providers and a hand-verified ethics test. Read the [final report](https://buriedsignals.github.io/benchmarks/model-benchmark-2026-07-06.html), inspect its versioned [cases](data/model-benchmark-2026-07-06/cases.json), and find the authoritative [OSINT tool database on Hugging Face](https://huggingface.co/datasets/tomvaillant/osint-tool-database).

Each case declares its public URL or fixture, task, and weighted checks. The runner stores the complete command result in JSON, marks unavailable paid or network tools as skipped, and rejects obvious error pages before scoring. A score is a result on these cases—not a general claim that one tool is universally best.

## Quick start

Requires Python 3.9+; no dependencies are needed for the harness itself.

```bash
git clone https://github.com/buriedsignals/benchmarks.git
cd benchmarks
python3 -m benchmarkers.cli list
python3 -m benchmarkers.cli doctor
python3 -m benchmarkers.cli run --category pdf_extraction --tool pdftotext_baseline
python3 -m benchmarkers.cli report
open public/index.html
```

Network and paid tools are always opt-in:

```bash
python3 -m benchmarkers.cli doctor --allow-network --allow-paid
python3 -m benchmarkers.cli run --category scraping --allow-network --allow-paid
```

Copy `.env.example` to `.env` to configure an API-backed tool. Never commit keys. See the [methodology](docs/methodology.md#tool-access-and-cost) for the environment variables and cost rules.

## Use the results carefully

The generated report is published at [buriedsignals.github.io/benchmarks](https://buriedsignals.github.io/benchmarks/). GitHub Actions deploys the already-generated `public/` directory when `main` changes; it does not run tools or spend API credits.

Before comparing scores, check:

- the exact cases and probes in `cases/`;
- the tool command and access requirements in `configs/tools.json`;
- the run artifact in `results/<timestamp>/results.json`; and
- whether a row is a pass, failure, timeout, skipped tool, or invalid source.

For a durable report assembled from more than one run, combine artifacts rather than rerunning paid tools:

```bash
python3 -m benchmarkers.cli combine \
  results/run-a/results.json \
  results/run-b/results.json \
  --output results/combined-current.json \
  --update-latest
python3 -m benchmarkers.cli report
```

## Repository map

```text
benchmarkers/       CLI runner and static-report templates
cases/              Public benchmark cases, grouped by category
configs/tools.json  Tool commands, requirements, and network/cost gates
scripts/adapters/   Thin adapters that normalise each tool's output
tests/              Regression tests for runner safety and result combining
docs/               Methodology and contributor-facing documentation
results/            Local JSON run artifacts (ignored by Git)
public/             Generated static report, published through GitHub Pages
data/               Versioned inputs for completed, non-runnable studies
```

## Adding or updating a benchmark

1. Add a public, stable, task-shaped case in `cases/`.
2. Add a tool entry in `configs/tools.json`; set `network` and `paid` truthfully.
3. Use a small adapter only when a direct command cannot provide comparable text output.
4. Run `doctor`, then a focused run with explicit permission for any network or paid work.
5. Add a regression test when changing runner behaviour, and update the report only from reviewed results.

Do not tune a tool using a case's expected probe values. Do not commit credentials, local binaries, model caches, or paid-run artifacts by default.

## Contributing

Issues and pull requests are welcome, especially for reproducible cases that expose a real reporting task or for corrections to a tool adapter. Please include the source URL, why the task matters, the command used, and any cost or access requirement.

## Acknowledgements

This project depends on public records and open-source infrastructure. Listing does not imply affiliation or endorsement.

| Area | Projects and institutions |
| --- | --- |
| Browser and scraping | [Playwright](https://playwright.dev/), [Crawl4AI](https://github.com/unclecode/crawl4ai), [Scrapy](https://scrapy.org/), [Scrapling](https://github.com/D4Vinci/Scrapling), and [Trafilatura](https://github.com/adbar/trafilatura) |
| Document extraction | [Poppler](https://poppler.freedesktop.org/) (`pdftotext`), [Docling](https://github.com/docling-project/docling), [Marker](https://github.com/VikParuchuri/marker), and [Surya](https://github.com/VikParuchuri/surya) |
| Public-interest source material | The councils, registries, archives, and public institutions whose pages make these tests possible |
| Publication | [GitHub Pages](https://pages.github.com/) for hosting the static report |

If a project or institution should be credited differently, please open an issue or pull request.
