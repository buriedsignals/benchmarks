# Buried Signals benchmarks

This repository measures document parsing, browser automation, and scraping
tools. The CLI in `benchmarkers/` produces JSON run artifacts under
`results/` and the static report under `public/index.html`.

## Working rules

- Start with `python3 -m benchmarkers.cli doctor`; use `--allow-network` and
  `--allow-paid` explicitly because some tools spend money or make external
  requests.
- Never commit API keys, `.env` files, model caches, or large local binaries.
- Prefer combining existing result JSON files over re-running paid tools.
- Run focused tests with `python3 -m pytest` after changing adapters or the
  runner, and regenerate the report with `python3 -m benchmarkers.cli report`.

See `README.md` and `LOOP.md` for the current benchmark matrix and methodology.
