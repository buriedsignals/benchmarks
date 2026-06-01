from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 4:
        print("usage: docling_parse.py <pdf-path> <output-dir> <timeout-seconds>", file=sys.stderr)
        return 2
    pdf_path = Path(sys.argv[1])
    output_dir = Path(sys.argv[2]) / f"{pdf_path.stem}-docling"
    timeout = sys.argv[3]
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        "uvx",
        "--from",
        "docling-slim",
        "docling",
        str(pdf_path),
        "--to",
        "md",
        "--image-export-mode",
        "placeholder",
        "--output",
        str(output_dir),
        "--device",
        "cpu",
        "--document-timeout",
        timeout,
    ]
    proc = subprocess.run(cmd, text=True, capture_output=True, check=False)
    if proc.stderr:
        print(proc.stderr, file=sys.stderr, end="")
    candidates = sorted(output_dir.rglob("*.md")) + sorted(output_dir.rglob("*.txt"))
    for candidate in candidates:
        text = candidate.read_text(encoding="utf-8", errors="replace")
        if text.strip():
            print(text)
    if proc.returncode != 0:
        if proc.stdout:
            print(proc.stdout, end="")
        return proc.returncode
    if not candidates:
        print(proc.stdout, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
