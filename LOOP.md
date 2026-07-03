# LOOP: Verify + extend the scraping benchmark

Self-contained work order for a `/loop` session. Each iteration: read this file top to
bottom, execute the **first unchecked task**, check it off, append one entry to the Work
Log, commit completed units with `jj`. Do not skip ahead. Stop conditions at the bottom.

Workspace: `/Users/tomvaillant/buried_signals/tools/benchmarks` — do not edit outside it.

---

## Mission

1. **Verify** the existing scraping benchmark is correctly built and its published results
   are accurate.
2. **Extend** the scraping category with new open-source tools (list below), re-run, and
   regenerate the report.

## Context map (read before first task)

| File | Role |
|---|---|
| `benchmarkers/cli.py` | Runner: `list`, `doctor`, `run`, `report`, `combine`, `export-site`. Scoring in `score_output()` (~line 183). |
| `configs/tools.json` | Tool registry: command templates, `categories`, `requires_env/executables/files`, `paid`/`network` gates. |
| `cases/scraping.json` | 4 scraping cases (Companies House, Basel, Zurich, Lausanne), scored by weighted probes. |
| `scripts/adapters/*.py` | Adapter pattern: argv in, extracted text on stdout, nonzero exit on failure. Follow `exa_contents.py` as the scraping reference. |
| `results/latest.json`, `results/combined-current.json` | Published numbers behind the report. |
| `public/index.html` | Static report, published via GitHub Pages, iframed from the site. |
| `README.md` | Commands, gating flags, install conventions (`uvx` for Python tools, local binaries under `bin/`). |

Mandatory preflight each session: read `/Users/tomvaillant/buried_signals/kit/coding-rules/SKILL.md`
and follow it (jj VCS, workflow routing, completion standard). The repo has no `.jj` yet;
worktree was clean on 2026-07-03 — run `jj git init --colocate` before the first edit.

## Ground rules

- **Paid-credit budget**: `firecrawl_scrape` and `exa_contents` cost API credits. Do not
  re-run them for debugging. Budget: at most ONE full paid scraping re-run across the whole
  loop (Phase 3). Use `combine` to merge fresh free-tool runs with existing paid results —
  README documents this exact workflow. Iterate/debug adapters against `obscura_browser`
  or the new free tools only.
- **OpenRouter key (Tom-approved for this loop)**: `OPENROUTER_API_KEY` is already in the
  local `.env` (auto-loaded by `doctor`/`run`; also lives in `~/.goose-ops/env` on the Mac
  mini). Use it as the LLM/VLM backend for tools that need one (scraper-factory, PixelRAG).
  Mark such tools `paid: true` + `requires_env: ["OPENROUTER_API_KEY"]` in `tools.json`.
  Keep spend sane: cheap models for debugging, a handful of calls per adapter iteration;
  the full runs are only 4 cases each. Never print or commit the key.
- **No answer leakage**: adapters must never receive probe values, case prompts as
  extraction targets, or anything derived from `cases/*.json` probes. A tool that gets
  "trained" on the expected answer is disqualified from the report. (Acute risk for
  autoscraper, which learns from example wanted-values.)
- **Fair comparison**: one `tools.json` entry per tool, default/headline configuration,
  same 4 cases, same timeout regime as existing scraping tools. If a tool has multiple
  fetch modes (e.g. Scrapling basic/dynamic/stealth), pick the mode the project itself
  headlines for scraping protected pages, and record the choice in README.
- **The benchmarked tools are the deliverable**: running crawl4ai, Scrapling, etc. against
  the 4 case URLs is the benchmark itself — the "always firecrawl for web fetching" house
  rule applies to *your own* research fetches, not to adapters under test.
- New tools install per repo convention: `uvx` for Python packages (keep envs out of git),
  `bin/<tool>/` for binaries. Nothing heavyweight committed.
- Commit one logical unit per task or task-group with `jj` (`jj describe` + `jj new`).
  Do not push or touch GitHub Pages publishing unless Phase 4 says so.

## Candidate tools (from Tom, 2026-07-03)

| Repo | What it is | Status |
|---|---|---|
| `unclecode/crawl4ai` | LLM-friendly crawler/scraper (Python, `crwl` CLI, needs `crawl4ai-setup` for Playwright browsers) | Include |
| `microsoft/markitdown` | File/URL → Markdown converter; fetches http(s) URLs directly | Include |
| `D4Vinci/Scrapling` | Adaptive scraping framework with stealth fetchers; has CLI (`scrapling install` for browser deps) | Include |
| `alirezamika/autoscraper` | Learns extraction rules from example wanted-values | Investigate — see leakage rule; if no fair generic URL→text adapter exists, exclude and document why |
| `StarTrail-org/PixelRAG` | "Pixel-native search" RAG (pixelrag.ai) — renders pages as pixels instead of parsing | Include — Tom explicitly wants this tested. Make a real attempt: find its URL→text/answer path, use the OpenRouter key for any LLM/VLM backend it needs. Exclude only after a documented failed attempt, not a doc skim. |
| `TowCenter/scraper-factory` | Tow Center "generalized Scraper Factory" (19 stars) — likely LLM-generates per-site scrapers | Investigate — determine if it can scrape an arbitrary URL non-interactively; point its LLM backend at OpenRouter and mark `paid: true` |
| `scrapy/scrapy` | The canonical Python scraping framework (Tom confirmed: scrcpy was a paste error for Scrapy) | Include — framework, not a URL→text CLI, so it needs a minimal generic spider adapter: fetch the case URL, emit page text/links to stdout. No per-site parse rules (fair-comparison rule). |

---

## Tasks

### Phase 0 — Session setup
- [x] 0.1 Read coding-rules skill + this file fully; `jj git init --colocate`; run
      `python3 -m benchmarkers.cli list` and `doctor` (no network flags) and record output
      in the Work Log.

### Phase 1 — Verify the current scraping benchmark
- [x] 1.1 **Audit scoring logic.** Read `score_output()`, `run_one()`, `text_metrics()`,
      `cmd_combine()` in `benchmarkers/cli.py`. Verify: probe kinds behave as documented;
      `contains` is case-insensitive substring — check each scraping probe for
      false-positive risk (short tokens like `"PV"`, `"PDF"` matching unrelated text, e.g.
      inside URLs or unrelated words); how errors/timeouts score (None vs 0) and whether
      the report ranks None fairly; whether `combine` can silently keep stale results for
      a tool that also appears in a newer run. Fix real bugs (test-first per coding-rules);
      log false-positive risks in Work Log even if not fixed.
- [x] 1.2 **Verify cases against live pages.** For each of the 4 scraping cases, fetch the
      URL once with `firecrawl scrape` (research fetch, cheap) and confirm every probe value
      still exists on the live page (Companies House address/incorporation strings are the
      likely rot). Fix any rotted probe values; note fixes.
- [x] 1.3 **Reproduce free-tool results.** Run `obscura_browser` on all 4 scraping cases
      (`run --category scraping --tool obscura_browser --allow-network`). Compare scores
      to `results/latest.json` / `combined-current.json`. Investigate any regression
      (page drift vs harness bug) before touching anything else.
- [x] 1.4 **Audit published paid results (no re-run).** Read the stored raw outputs for
      `firecrawl_scrape` and `exa_contents` in the results dirs; spot-check that recorded
      probe hits actually appear in the stored stdout, that Exa's two recorded failures are
      genuine errors (README claims they are), and that the report (`public/index.html` +
      `latest.json`) matches the underlying run files. Log verdict: ACCURATE or list of
      discrepancies (fix report-generation bugs; do not massage data).
- [x] 1.5 **Checkpoint.** Regenerate report (`report`), confirm no diff beyond expected
      fixes, `jj` commit "verify scraping benchmark" with a summary of findings in the
      description.

### Phase 2 — Wire in new tools (one task per tool; each ends with: entry in
`configs/tools.json`, adapter if needed, all 4 cases passing a smoke run with
`--allow-network`, README install note, `jj` commit)
- [x] 2.1 **markitdown** (easiest, do first): try plain command template
      `uvx markitdown {url}`; adapter only if URL handling needs headers/UA.
- [x] 2.2 **crawl4ai**: `uvx` + `crwl {url} -o markdown` (or thin adapter). Handle its
      one-time `crawl4ai-setup`/Playwright-browser install; document in README like the
      obscura/docling notes.
- [x] 2.3 **Scrapling**: pick headline fetch mode (see Fair comparison rule), wire CLI or
      thin adapter, handle `scrapling install`.
- [x] 2.4 **autoscraper** [EXCLUDED]: investigate first (leakage rule). Decide include/exclude; if
      excluded, add a short "evaluated, excluded because…" note to README findings instead.
- [x] 2.5 **Scrapy**: minimal generic spider adapter (fetch case URL, output body
      text + first ~80 links to stdout), run via `uvx --from scrapy`. No per-site
      selectors or parse rules — the point is measuring Scrapy's default fetch layer
      against the same civic/registry pages.
- [x] 2.6 **PixelRAG** (Tom wants this tested — invest real effort): clone/install, read
      its docs/examples, find the ingestion path for a live URL and a query path that
      returns text. Wire OpenRouter as its model backend if it needs one (`paid: true`,
      `requires_env: ["OPENROUTER_API_KEY"]`). If its output is answers-to-queries rather
      than page text, score it by querying with the case `prompt` (NOT the probe values —
      leakage rule) and letting the probes run over the answer; note this scoring caveat
      in README. Exclude only after a documented hands-on failure.
- [x] 2.7 **scraper-factory**: investigate; include if it can scrape arbitrary URLs
      non-interactively with OpenRouter as the LLM backend (`paid: true`,
      `requires_env: ["OPENROUTER_API_KEY"]`); else document exclusion.

### Phase 3 — Full run + report
- [x] 3.1 Full scraping run of obscura + every new tool (including the OpenRouter-backed
      ones — that spend is approved) on all 4 cases in one timestamped run
      (`--allow-network --allow-paid`). The Phase-3 paid budget rule below only restricts
      `firecrawl_scrape`/`exa_contents`.
- [x] 3.2 The single budgeted PAID re-run (`firecrawl_scrape`, `exa_contents`,
      `--allow-network --allow-paid`) — only if Phase 1 changed probes/scoring (stale paid
      results would be incomparable); otherwise `combine` the fresh free run with the
      existing paid results per README.
- [x] 3.3 `combine --update-latest`, `report`, eyeball `public/index.html` (open it):
      every included tool has a row, scores plausible, no None-ranking artifacts.
- [x] 3.4 Update README: Categories line, install notes, "notable findings" bullets
      (including any exclusions and the PixelRAG scoring caveat if applicable). `jj` commit.

### Phase 4 — Wrap up
- [ ] 4.1 Completion standard from coding-rules: re-read full diff, state what was verified
      vs not. Write a final summary at the top of the Work Log: verification verdict for
      the old benchmark, which tools were added/excluded and why, score table for the new
      tools, open risks. Do NOT push; leave commits local for Tom's review.

---

## Stop conditions

- All boxes checked → write final summary, stop.
- Blocked >2 attempts on one task (install failure, tool fundamentally incompatible,
  missing key) → mark the task `[BLOCKED: reason]` in place, log it, move to the next
  task. If ≥3 tasks are blocked, stop and summarize.
- Any action that would spend paid credits beyond the Phase 3 budget → do not spend; log
  and continue with free tools.

## Work Log

(append-only; newest entry first; format: `- 2026-07-03 HH:MM — task N.N — what was done / found / committed`)

- 2026-07-03 — tasks 3.1–3.4 — Full 9-tool scraping run (36 rows, one timestamped run incl. the budgeted firecrawl+exa re-run — required because 1.2 changed probes). Final leaderboard on refreshed cases: Scrapy 1.00 (fastest), Scrapling 1.00, Crawl4AI 1.00, MarkItDown 1.00, Firecrawl 0.88, PixelRAG 0.83, Exa 0.79, Obscura 0.50, Scraper Factory 0.29. VERIFICATION PAYOFF: Exa 0.38→0.79 (its June failures were the dead URLs) and Firecrawl 0.75→0.88 — the June gaps were substantially rot artifacts. combine ran with the new dedup: dropped exactly the 12 stale scraping rows, kept 15 pdf + 16 browser rows; latest.json now 67 rows; report regenerated and eyeballed (ranking sane; cosmetic wart: scraper-factory note column shows a raw log line for its Basel failure — failure_note picks the last stderr line; left as-is). README findings rewritten: rot disclosure, new-tool results, PixelRAG + Scraper Factory scoring caveats, autoscraper exclusion. OpenRouter spend this loop: well under $1 (gpt-4o-mini generations + gemini-flash tile reads).

- 2026-07-03 — task 2.7 — scraper-factory INCLUDED: installed under gitignored bin/scraper-factory (uv venv + requirements + playwright chromium); OpenRouter via OPENAI_BASE_URL + LLM_MODEL=openai/gpt-4o-mini (stock openai client honors both); `generate` is DB-free (Mongo only needed for `register`, unused). Adapter scripts/adapters/scraper_factory_scrape.py: generates once per case (persisted in bin/), re-executes via `cli.py test` on later runs, prints result.json records. Smoke: CH 0.67, Basel FAIL (factory-internal "'NoneType' object is not subscriptable" during page analysis — reproduced manually, genuine tool limitation on that source), Zurich 0.17, Lausanne 0.33. Low scores are design-honest: it emits structured title/date/url records per stock config.json, not page content — its Zurich extraction (session list with dates + detail URLs from the JS-rendered table) is excellent AS MONITORING OUTPUT; the probes measure content preservation. Key findings bullet for 3.4. PHASE 2 COMPLETE: 7 candidates -> 6 included (markitdown, crawl4ai, scrapling, scrapy, pixelrag, scraper-factory), autoscraper excluded (leakage), scrcpy replaced by scrapy per Tom.

- 2026-07-03 — task 2.6 — PixelRAG wired as a pixel-native scraping pipeline: `pixelshot {url}` renders screenshot tiles, then a VLM (OpenRouter, default google/gemini-2.5-flash, override via PIXELRAG_VLM_MODEL) reads the tiles guided by the case prompt (never probe values) and emits extracted text. Adapter scripts/adapters/pixelrag_read.py, max 8 tiles (truncation logged), token usage logged to stderr (~3K tokens/case — cents). Scores: CH 1.0, Basel 0.67, Zurich 0.83, Lausanne 0.83 — FIRST tool with a differentiated profile. Notable: reads through cookie banners (Basel: real June-2026 protocol listings incl. Wortprotokoll links where obscura sees only the banner); min_chars misses are honest — precise extraction vs bulk preservation tradeoff, worth a findings bullet. Scoring caveat (VLM answer, not page text) to document in README at 3.4.

- 2026-07-03 — task 2.5 — Scrapy wired: minimal generic spider (scripts/adapters/scrapy_case_spider.py — body text + first 80 links, stock library settings, no per-site rules) via `uvx --from scrapy scrapy runspider ... --nolog`. 4x pass, all 1.0, fastest tool so far (0.6-1.5s). Plain HTTP suffices on all 4 refreshed cases; the JS-only content is not required by current probes.

- 2026-07-03 — task 2.4 — autoscraper EXCLUDED, structural: its only mode is build(url, wanted_list) — supervised extraction-rule learning from example values known to be on the page. For our cases the natural wanted-values ARE the probe targets (company names, protocol labels) = answer leakage; a neutral wanted_list from another page doesn't transfer. It is a per-site rule learner, not a generic URL-to-text scraper; no fair adapter exists. README findings note added in 3.4.

- 2026-07-03 — task 2.3 — Scrapling wired via headline mode `stealthy-fetch` (StealthyFetcher/Camoufox — the project's flagship anti-bot fetcher, per fair-comparison rule). CLI writes to a file, so thin adapter scripts/adapters/scrapling_fetch.py relays the saved markdown to stdout and pushes all CLI logs to stderr. 4x pass, all 1.0, 1.4-3.2s. Handled the Zurich cookie-check redirect chain cleanly. Note: all 3 new tools so far score 1.0 — the refreshed cases don't discriminate among modern fetchers; old tools' gaps (obscura cookie-wall, exa index misses) provide the spread. Worth a bullet in 3.4 findings.

- 2026-07-03 — task 2.2 — crawl4ai wired: `uvx --from crawl4ai crwl {url} -o markdown`, clean markdown on stdout, no adapter, no separate crawl4ai-setup needed (Playwright browsers already present from the browser_automation adapters). 4x pass, all 1.0, 2.7-5.1s. Standout: renders the JS seance listing on Lausanne (118KB output vs firecrawl's 9KB static shell).

- 2026-07-03 — task 2.1 — markitdown wired: plain `uvx markitdown {url}` command template, no adapter needed. Smoke run on all 4 cases: 4x pass, score 1.0 on every case, 0.6-1.7s per case. Notable: full Basel content (604KB) over plain HTTP — the cookie-wall only trips headless browsers; Companies House does not block the default requests UA. README updated (category line + uvx install note). latest.json re-restored from combined-current after the run (cmd_run clobber footgun from 1.3).

- 2026-07-03 — tasks 1.3–1.5 — VERIFICATION VERDICT: harness correct, published scraping data partly inaccurate due to source rot. (1.3) obscura re-run: Companies House 1.0 reproduces exactly; Basel 0.0 reproduces (obscura returns only the cookie banner, 147B — genuine tool limitation); refreshed cases re-baseline: Zurich 0.0 (obscura emits a single newline on the new termine page), Lausanne 1.0. Also found: `cmd_run` unconditionally overwrites results/latest.json even on partial runs — it clobbered the combined latest; restored from combined-current.json. FOOTGUN: never run partial `run` without re-running `combine --update-latest` after. (1.4) Stored paid outputs audited: every recorded probe verdict consistent with stored stdout; Exa's 2 failures genuine (exit 1, cost=0, empty stdout). SMOKING GUN: stored firecrawl stdout for Zurich ("Dokument nicht auffindbar (Error 404)") and Lausanne ("Erreur 404") proves both URLs were ALREADY DEAD on 2026-06-01 — the published firecrawl 75% and obscura 46% scraping coverage include scores earned on 404 chrome (fc 0.83 + 0.5, obscura 0.67 + 0.17). Report rendering itself is faithful; the data for those 2 cases is not. Remedy: refreshed cases (1.2) + full paid re-run (3.2). (1.5) Report regenerated: diff confined to task-brief case metadata, all score tables identical → renderer verified. 5/5 tests pass. Committed.

- 2026-07-03 — task 1.2 — MAJOR ROT FOUND AND FIXED. Companies House + Basel cases fully intact (all probes hit live). But BOTH the Zurich and Lausanne case URLs now 404: gemeinderat-zuerich.ch/protokolle and lausanne.ch/.../seances-et-pv.html are dead. Worse, the 404 pages still scored 5/6 (Zurich: "Gemeinderat"/"Protokoll" match nav links + URL echo) and 3/6 (Lausanne: weight-2 "PV" matches the URL slug "seances-et-pv" printed on the 404 page) — live confirmation of the 1.1 probe-robustness risk. Fixed: Zurich → gemeinderat-zuerich.ch/sitzungen/termine/ with probes Sitzungskalender(2)/Traktanden(2)/Protokoll(1)/min_chars(1); Lausanne → lausanne.ch/officiel/conseil-communal/seances/seances-et-ordres-du-jour.html with probes "Séances et ordres du jour"(2)/"Conseil communal"(2)/"calendrier des séances"(1)/min_chars(1). Validated: new probes 6/6 on live pages, 2/6 and 1/6 on the old 404s. Both new pages have JS-rendered listings (difficulty preserved). CONSEQUENCE: stored paid results for these 2 cases are incomparable under new probes → Phase 3.2 budgeted paid re-run IS required.
- 2026-07-03 — task 1.1 — Scoring audit done. Confirmed: probes score FULL stdout (not preview), `contains` is case-insensitive substring. FIXED (test-first, 5 tests in tests/test_combine.py): `cmd_combine` had no dedup — duplicate (case,tool) rows across combined inputs would be silently averaged, and fresh gated-run `skip` rows would sit beside old paid `pass` rows; new `dedupe_results()`: later inputs win, skip never shadows an executed row. Current combined-current.json verified clean (0 dupes, 43 rows pass through unchanged; latest.json identical). LOGGED RISKS (not fixed here): (1) weight-2 `"PV"` probe matches "pv" anywhere incl. the case URL slug `seances-et-pv.html` if a tool echoes the URL; `"PDF"` matches ".pdf" hrefs — revisit probe values in 1.2; (2) fail/timeout rows still get probe-scored and enter averages — currently benign (Exa's 2 fails scored 0.0, no accidental matches), spot-check stored stdout in 1.4; (3) in single-run reports, `skip` rows inflate a tool's `runs` count/pass-rate denominator — cosmetic, report shows "N skip" note.
- 2026-07-03 — task 0.1 — coding-rules read; `jj git init --colocate` done, `main` bookmark tracked. `cli list`: 3 categories, 11 cases, 14 tools registered. `doctor` (no flags): 3 ready (pdftotext, surya, docling), 11 skip on network gate — correct gating. `doctor --allow-network --allow-paid`: all 14 ready (all keys/executables present, incl. firecrawl, exa, obscura binary).
