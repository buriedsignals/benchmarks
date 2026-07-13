# Methodology

Buried Signals Benchmarks compares tools on bounded, reproducible tasks that resemble reporting work: extracting evidence from a document, reaching a public record through a website, retrieving a civic page, or finding useful source material.

## The July 2026 OSINT model study

The [July 2026 OSINT model benchmark](../public/model-benchmark-2026-07-06.html) is a completed, fixed study—not a benchmark that the normal CLI should rerun. It compares 20 models on 15 closed-book investigative questions, including matched abliterated-base versus journalist-tune pairs.

Its outputs are published in the static [final report](../public/model-benchmark-2026-07-06.html). The exact inputs retained in this repository are:

- `data/model-benchmark-2026-07-06/cases.json` — the 15 prompts and weighted probes;
- the 11,353-row [OSINT tool database](https://huggingface.co/datasets/tomvaillant/osint-tool-database) snapshot used for hallucination scoring; and
- `data/osint-tool-db/MANIFEST.md` — the Hugging Face dataset revision (`36f39638675f8259b81693a1999a22c7b1c0de9c`), download date, schema, and scoring rule.

The study used provider and local GGUF runs that cannot be reconstructed automatically from a public GitHub workflow. Do not treat the static results as a live leaderboard or invoke the ordinary tool runner to reproduce them. A follow-up study should preserve a new dated input directory and report rather than overwrite this one.

## What a benchmark case contains

Every JSON file in `cases/` declares one category and its cases. A case includes:

- a stable identifier and human-readable title;
- a public URL or local fixture;
- a plain-language task and prompt passed to the tool where needed; and
- weighted probes that check for target evidence, usable output length, or a timing limit.

The cases are deliberately task-specific. A tool that wins a civic-page extraction case has not automatically won at every form of scraping.

## How tools run

`configs/tools.json` is the tool registry. It declares the command, required executables and environment variables, and whether a tool uses the network or a paid API. `scripts/adapters/` holds thin wrappers where a tool needs output normalised before it can be scored.

The CLI does not silently run external or paid work:

```bash
python3 -m benchmarkers.cli doctor
python3 -m benchmarkers.cli doctor --allow-network --allow-paid
python3 -m benchmarkers.cli run --category scraping --allow-network
```

If a required dependency or key is unavailable, the tool is recorded as skipped rather than treated as a poor-performing result.

## Scoring and source validity

Most checks are weighted text probes. A case can also require minimum output length, an output artifact, or a maximum runtime. The score is the matched weight divided by the available weight.

The runner performs a conservative error-page check before scoring. Small outputs that clearly resemble a 404 or equivalent error page are marked `invalid_source` and excluded from averages. This protects against a common false result: matching a probe in a page's navigation or error chrome rather than retrieving the requested source.

Scores are diagnostic, not a universal ranking. Read the case, probes, raw output, tool version, access conditions, and status alongside any chart.

## Reproducibility and report publication

Each run produces `results/<timestamp>/results.json`. Combine independent runs when a complete matrix needs more than one session:

```bash
python3 -m benchmarkers.cli combine results/run-a/results.json results/run-b/results.json \
  --output results/combined-current.json --update-latest
python3 -m benchmarkers.cli report
```

`report` renders the latest reviewed artifact to `public/index.html`. The GitHub Pages workflow only publishes that directory on pushes to `main`; it does not perform benchmark runs, make network requests, or use API keys.

## Tool access and cost

API-backed tools are configured locally through `.env`; see `.env.example` for current names. Common examples include `FIRECRAWL_API_KEY`, `EXA_API_KEY`, `LLAMA_CLOUD_API_KEY`, and `EXTEND_API_KEY`.

Before running a tool that could charge money, inspect it with `doctor --allow-network --allow-paid`, run the smallest relevant category or tool selection, and preserve the resulting JSON. Do not rerun paid tools simply to regenerate a report.

## Maintaining cases

Public pages rot. When a source moves, update the case to a live equivalent and revise the probes so they test page evidence rather than URL fragments or generic site chrome. Add a regression test whenever the runner's safety or result-combination behaviour changes.

Do not add a case when its expected answer cannot be inspected. Do not train or prompt a tool with its own probe values. Keep credentials, downloaded binaries, cached models, and ordinary run artifacts out of Git.
