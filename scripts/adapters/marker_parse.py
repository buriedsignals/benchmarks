from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 6:
        print(
            "usage: marker_parse.py <pdf_path> <output_dir> <page_range> <timeout_seconds> <case_id>",
            file=sys.stderr,
        )
        return 2
    pdf_path, output_dir, page_range, timeout_seconds, case_id = sys.argv[1:6]
    out_root = Path(output_dir) / f"marker-{case_id}"
    command = [
        "uvx",
        "--from",
        "marker-pdf",
        "marker_single",
        pdf_path,
        "--page_range",
        page_range,
        "--output_dir",
        str(out_root),
    ]
    proc = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=max(60, int(float(timeout_seconds)) - 30),
    )
    if proc.stderr:
        print(proc.stderr[-2000:], file=sys.stderr)
    if proc.returncode != 0:
        print(proc.stdout[-2000:], file=sys.stderr)
        return proc.returncode
    md_files = sorted(out_root.glob("**/*.md"))
    if not md_files:
        print("marker produced no markdown output", file=sys.stderr)
        return 1
    for md in md_files:
        print(md.read_text(encoding="utf-8", errors="replace"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
