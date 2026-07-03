# OSINT tool DB snapshot — hallucination-scoring gold reference

Source: https://huggingface.co/datasets/tomvaillant/osint-tool-database
File: osint_tools.jsonl (gitignored — pull with the curl in README/Work Log)
Downloaded: 2026-07-03
Dataset lastModified: 2026-06-30T15:02:17Z
Dataset commit SHA: 36f39638675f8259b81693a1999a22c7b1c0de9c
Rows: 11353
Fields: tool_name, tool_url, category, short_description, source_toolkits, status, last_updated

Used by scripts/score_hallucination.py: a cited (tool_name|domain) that matches no row
here AND fails a liveness ping is counted as a hallucinated tool. A tool present here but
marked status!=active is NOT penalized (tool rot rule).
