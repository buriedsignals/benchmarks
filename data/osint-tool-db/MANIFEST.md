# OSINT tool DB snapshot — hallucination-scoring gold reference

Source: https://huggingface.co/datasets/tomvaillant/osint-tool-database
Authoritative dataset: [tomvaillant/osint-tool-database](https://huggingface.co/datasets/tomvaillant/osint-tool-database)
File: `osint_tools.jsonl` (not duplicated in this repository)
Downloaded: 2026-07-03
Dataset lastModified: 2026-06-30T15:02:17Z
Dataset commit SHA: 36f39638675f8259b81693a1999a22c7b1c0de9c
Rows: 11353
Fields: tool_name, tool_url, category, short_description, source_toolkits, status, last_updated
SHA-256: `106057e1d8d8b884bc6bdfeacaeb89c25f0551f57f211f050135946e0649681e`

For the July 2026 model study, a cited tool/domain that matched no row here and
failed a liveness check counted as a hallucinated tool. A tool present here but
marked `status != active` was not penalized.
