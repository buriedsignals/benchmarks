# LOOP PRD v2: A truly solid benchmark — verify browser automation, fix misused tools, close coverage gaps

**STATUS: APPROVED — loop active since 2026-07-03 (Tom launched /loop).**

Self-contained work order for a `/loop` session. Each iteration: read this file top to
bottom, execute the **first unchecked task**, check it off, append a Work Log entry,
commit completed units with `jj`. Stop conditions at the bottom.

Workspace: `/Users/tomvaillant/buried_signals/tools/benchmarks`. Read-only inspection
allowed elsewhere (browser-harness install, docs).

## Mission

Make the benchmark *trustworthy*, not just greener: (1) verify browser_automation was
built correctly and that its two 0% tools are misused rather than weak; (2) modernize
adapters to each tool's documented current usage; (3) close coverage gaps (sparse PDF
matrix, missing category candidates); (4) add structural guards so the June rot problem
(scoring 404 pages for a month) cannot recur.

## Research findings (2026-07-03 — grounds this PRD)

**The 0% tools are not dead — they are almost certainly misused by us:**

- `browser-use`: **102K stars, MIT, pushed yesterday.** Our adapter drives the OLD agentic
  terminal and returns zero evidence. The CLI has been redesigned into deterministic
  direct browser control — Python-on-stdin via `uvx browser-use` (`new_tab()`,
  `page_info()`), local Chrome/Chromium over CDP, cloud optional, NO LLM required for
  scripted flows (docs.browser-use.com/open-source/browser-use-cli). Hypothesis: rebuild
  adapter → real scores.
- `browser-harness` (Tom's own tool): all 4 cases fail with "CDP keepalive ping timeout" —
  smells like a missing running Chrome / wrong environment, i.e. harness misuse. NOTE: the
  SKILL.md path in global CLAUDE.md (`tools/browser-harness/SKILL.md`) does not exist;
  first resolve the real install (`which browser-harness`, read its actual docs). Also do
  not confuse it with browser-use's product of the same name.

**Category-candidate survey (stars/license/activity checked 2026-07-03 via GitHub API):**

| Candidate | Category | Stats | Verdict for this loop |
|---|---|---|---|
| Stagehand (browserbase) | browser_automation | 23K, MIT, active | **Include** — the leading "AI browser SDK" (act/extract/observe on Playwright); LLM via OpenRouter, cheap model |
| playwright-mcp (Microsoft) | browser_automation | 35K, Apache-2.0 | Investigate — a11y-tree driven, huge adoption; awkward to drive headlessly (MCP protocol), include only if a clean non-interactive path exists |
| lightpanda | browser_automation | 31K, AGPL | Investigate — purpose-built headless browser for AI, CDP-compatible, very fast; known web-compat gaps make it an honest hard-mode candidate |
| zendriver (nodriver successor) | browser_automation | 1.3K (nodriver 4.4K), AGPL | Investigate — undetected-CDP niche; include only if trivially scriptable for our form flows |
| Skyvern | browser_automation | 22K, AGPL | **Skip** — vision-agent niche, Docker-heavy, duplicates agentic coverage Stagehand provides at far lower setup cost |
| trafilatura | scraping | 6.2K, Apache-2.0 | **Include** — the academic-standard web text extractor; the missing baseline for civic monitoring pipelines |
| marker | pdf_extraction | 37K, GPL-3.0 | Investigate — an old results file (`combined-local-…-marker-surya.json`) shows it was benchmarked once and silently dropped; find out why, re-add if it runs locally |
| MinerU | pdf_extraction | 73K, active | Investigate — top PDF→markdown tool; heavy model downloads, time-box the install, uvx/venv only |
| olmOCR (AllenAI) | pdf_extraction | 18.6K, Apache-2.0 | **Skip** — needs GPU serving; not runnable in this local harness |

## Ground rules

- **ANTI-GAMING (prime rule)**: "improve" = fix harness bugs, rotted cases/selectors,
  outdated adapters, and adopt tools' *documented* recommended invocations. NEVER tune
  any adapter, prompt, case, or probe because of what probes check. Case/probe changes
  require live validation (live page scores high, error page scores ~0) with evidence
  logged. Honest weakness stays in the report.
- **Paid budget**: LlamaParse ≤2 parses (the missing matrix cells), Extend 0, Fireparse ≤3,
  LangExtract ≤4 calls, ONE firecrawl+exa scraping re-run only if scraping cases change
  (not expected). OpenRouter approved for Stagehand/PixelRAG/Scraper Factory/LangExtract —
  cheap models, usage logged. New-tool installs time-boxed: 20 min each, one retry, then
  `[BLOCKED]` and move on. Debug against free tools only.
- **Live services**: browser cases drive real registries (Companies House, OpenSanctions,
  Wikidata, OSM). Max one full browser-case sweep per iteration; no selector-debug loops
  against live sites — use stored artifacts and screenshots first. Back off on rate
  limits/CAPTCHAs; never retry-hammer.
- **Repo discipline**: jj commit per task-unit, no push. After every partial `run`, restore
  `latest.json` (`cp results/combined-current.json results/latest.json`); rebuild via
  `combine --update-latest` only in Phase 5. Check `jj status` for the model-benchmark
  session's foreign WIP (LOOP_MODELS.md, scripts/score_*, m_* runs) before describing —
  never fold it into loop commits.

## Tasks

### Phase 0 — Setup
- [x] 0.1 Preflight: coding-rules, `jj status` (log foreign WIP), `cli list`, `doctor
      --allow-network --allow-paid`, `which browser-harness` + locate its real docs.

### Phase 1 — Verify browser_automation as built
- [x] 1.1 **Case/probe audit.** Read `cases/browser_automation.json`; check probes for the
      known false-positive patterns (URL echo, nav chrome, short tokens). Inspect stored
      dev-browser/Playwright 1.0 artifacts: is the "target evidence" genuine result content
      (filing rows, sanction hits, Wikidata identity, OSM place) or chrome? Verdict per case.
- [x] 1.2 **Live selector check.** One Playwright sweep of the 4 cases; for any regression
      vs stored 1.0, classify selector rot / redesign / transient with screenshot evidence
      before touching case files.
- [x] 1.3 **browser-harness diagnosis.** Resolve the real install; reproduce ONE case via
      its stdin protocol manually; read its actual helper docs. Classify the keepalive
      failure: (a) harness misuse (e.g. requires a running/visible Chrome the benchmark
      never started — if so, fix the benchmark invocation to the tool's documented
      requirements), (b) adapter bug (fix here), (c) genuine defect (leave score honest,
      Work-Log note for a separate session in the tool's own repo).
- [x] 1.4 **Rebuild browser-use for the new CLI.** Deterministic Python-on-stdin adapter
      (mirror the browser_harness stdin_template pattern) driving the same generic
      form-workflow variables. Resolve the browser question reproducibly: prefer
      `BU_CDP_URL` pointed at a benchmark-launched headless Chromium so no personal Chrome
      is touched; document setup in README. Verify with `--doctor`, 1 case, then all 4.
- [x] 1.5 **Checkpoint**: full browser sweep (existing 4 tools), compare vs stored, commit.

### Phase 2 — Browser category candidates (research-grounded)
- [x] 2.1 **Stagehand**: wire via a small Node adapter (its native runtime), OpenRouter
      cheap model, same form-workflow variables; smoke 1 case then all 4; README note;
      commit. Time-box applies.
- [x] 2.2 **playwright-mcp / lightpanda / zendriver**: [ALL SKIPPED] one investigation task — for each,
      answer "clean non-interactive path for our form flows? install cost sane?" Include
      at most the ONE that passes cleanly (avoid category bloat); document the other
      verdicts in README findings. Skip-with-reasons is a fine outcome.

### Phase 3 — PDF: complete + extend the matrix
- [x] 3.1 Fill missing pairs: LlamaParse `unesco`+`gijn` (≤2 paid), Surya `follow`+`unesco`
      (free, slow, background), LangExtract `unesco`+`gijn`. No tool×case cell may be
      empty without a logged reason — sparse matrices fake the category average (the
      98% lesson).
- [x] 3.2 Rule the 0.83s (LangExtract, Surya): honest weakness vs unfair probe, with
      fixture-validated probe fixes only.
- [ ] 3.3 **marker**: find why it was dropped (old combined file proves it once ran);
      re-add via uvx if it runs locally within the time-box. **MinerU**: attempt within
      time-box; include or document exclusion. Commit.

### Phase 4 — Scraping: baseline + invocation hardening
- [ ] 4.1 **trafilatura**: wire (`uvx trafilatura -u {url}` or thin adapter), run all 8
      cases, commit. This is the missing standard baseline.
- [ ] 4.2 **Obscura**: adopt documented wait/render flags if they exist; else accept 25%.
- [ ] 4.3 **Scraper Factory**: decide on the SHIPPED `example_configs/school_board_meetings.json`
      (vendor's own schema for civic meetings — documented usage, not probe-tuning);
      document reasoning either way; regenerate + re-run if switched (OpenRouter).
- [ ] 4.4 **PixelRAG**: adopt documented full-page/multi-tile capture if available
      (MAX_TILES=8, truncation logged); re-run (cents). **Exa**: verify livecrawl forcing;
      adopt documented full-text params if unused; else accept. Commit.

### Phase 5 — Structural solidity (the "never again" layer)
- [ ] 5.1 **Liveness guard**: pre-score check in the runner — detect 404/error/redirect-loop
      pages (status where available; error-page heuristics otherwise) and mark the row
      `invalid_source` instead of scoring it. Test-first; this is the guard that would
      have caught June's 404 scoring within a day.
- [ ] 5.2 **Discrimination audit**: flag cases where every tool scores 1.0 (zero signal);
      propose (do not silently add) 1–2 harder cases in the Work Log for Tom.
- [ ] 5.3 **Fairness note in report**: annotate extraction-style tools (PixelRAG, Scraper
      Factory) in the report/README so preservation probes aren't read as quality verdicts.
      (Full second metric family = out of scope; note as future work.)
- [ ] 5.4 Full rebuild: `combine` all fresh runs (dedup keeps newest) `--update-latest`,
      `report`, verify category numbers and every matrix cell; README findings updated
      honestly (including what did NOT improve and why).
- [ ] 5.5 Completion standard: diff re-read, tests pass, verified-vs-not statement, final
      Work Log summary, commit. No push.

## Stop conditions

- All boxes checked → final summary, stop.
- Task blocked >2 attempts → `[BLOCKED: reason]`, move on; ≥3 blocked → stop + summarize.
- Any paid cap reached → skip, log, continue free.
- Live-service throttling → back off, task moves to next iteration.

## Work Log

(append-only; newest first; `- 2026-07-03 — task N.N — done/found/committed`)

- 2026-07-03 — tasks 3.1–3.2 — PDF matrix filled. ROOT CAUSE of sparseness found: surya's command requires {page_range} but only gijn defined it — the runner silently skipped the other cases ('case missing template fields'). Mirrored gijn's page_range '0-5' onto follow+unesco (uniform case policy, not probe-informed). Results: llamaparse gijn 1.0; langextract unesco 0.8, gijn 0.83 (retry at 600s, 3rd of ≤4 cap); surya follow 0.83, unesco 0.8. BLOCKED-ON-BUDGET: llamaparse unesco timed out at the default 120s (my invocation error) and the ≤2-parse cap is spent — needs Tom's one-parse approval to fill the last cell. (3.2) Verdict on ALL sub-1.0 PDF scores: every one is a min_chars miss with all content probes hitting — page-capped OCR (case design) and extraction-style output (langextract) legitimately trade bulk preservation; probes stay as-is, fairness annotation lands in 5.3.

- 2026-07-03 — task 2.2 — Candidate triage: ALL THREE SKIPPED with reasons. playwright-mcp: a protocol wrapper around Playwright (already benchmarked directly); its a11y-tree value only manifests under an LLM driver, which Stagehand now represents — no new signal for harness cost. zendriver: anti-detection niche is irrelevant on cooperative registries (none block our stock Playwright) — belongs in a future scraping-stealth comparison if ever. lightpanda 0.3.4: hands-on FAILURE — binary installs and serves CDP fine, but Playwright-over-CDP navigation to Wikidata Special:Search times out at 30s under both 'load' and 'domcontentloaded'; engine compat not ready for these civic/registry workflows. Binary removed. Browser category stays at 4 tools (3 scripted @1.0 + Stagehand @0.92).

- 2026-07-03 — task 2.1 — Stagehand 3.6.0 wired: npm project in gitignored bin/stagehand, adapter run.mjs (env LOCAL, headless; v3 API uses stagehand.context.pages()[0], not .page; agent().execute with maxSteps 12; OpenRouter via model {modelName, apiKey, baseURL} — 'openai/gpt-4o-mini' routes correctly). Scores: CH 1.0, OpenSanctions 1.0, Wikidata 1.0, OSM 0.67 (agent reaches Zug but final page state lacks the exact Nominatim label string) → avg 0.92, the first non-1.0 browser signal — agentic exploration vs scripted selectors is now measurable. Instruction + agent chatter to stderr only. Spend: ~cents (gpt-4o-mini).

- 2026-07-03 — tasks 1.4–1.5 — browser-use rebuilt for the redesigned CLI: scripts/adapters/browser_use_stdin.py launches Playwright's chromium_headless_shell on private CDP port 9243, sets BU_CDP_URL, drives the form workflow as stepwise synchronous js() calls (single-call async version died with 'Execution context was destroyed' across click navigations — restructured with wait_for_load between steps). No personal Chrome, no LLM, no prompt echo. Old agentic adapter deleted; tool relabeled 'browser-use CLI' (id kept so dedup replaces June's 0.0 rows). Checkpoint sweep: 12/12 rows at 1.0 across dev-browser/Playwright/browser-use — browser_automation is now 3 healthy tools at 100%, echo-free. PRD hypothesis confirmed: browser-use was misused, not weak.

- 2026-07-03 — tasks 0.1–1.3 — Preflight: all 20 tools doctor-ready; foreign WIP logged (LOOP_MODELS.md, llm_openrouter.py, score_refusal.py, egg-info, small tools.json m_* hunk) — kept out of loop commits via jj split. (1.1) CRITICAL: dev-browser and Playwright adapters echoed the case prompt into scored stdout, and prompts contain probe values verbatim — Companies House echo alone was worth 0.75. Stored artifacts show the 1.0s were nonetheless genuine ("View PDF"/"Confirmation statement" present — not in prompt). FIXED: task now goes to stderr in both (playwright adapter + dev_browser script_template). browser-use old adapter did not echo (its 0.0 was honest). (1.2) Live Playwright sweep post-fix: 4/4 still 1.0, echo-free, selectors healthy — no rot in browser cases. (1.3) browser-harness is a GHOST: uv editable install points at deleted source dir (~/buried_signals/tools/browser-harness gone, no moved copy found); executable dies on import ("No module named run"). June's CDP timeout and today's state are both environmental. REMOVED from tools.json — a 0% row for an uninstalled tool misleads. NOTE FOR TOM: ~/.claude/CLAUDE.md still references the dead SKILL.md path (outside workspace, not touched).
