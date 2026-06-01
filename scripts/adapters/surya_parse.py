from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(strings(item))
        return out
    if isinstance(value, dict):
        out = []
        for item in value.values():
            out.extend(strings(item))
        return out
    return []


def main() -> int:
    if len(sys.argv) != 4:
        print("usage: surya_parse.py <pdf-path> <output-dir> <page-range>", file=sys.stderr)
        return 2
    pdf_path = Path(sys.argv[1])
    output_dir = Path(sys.argv[2]) / f"{pdf_path.stem}-surya"
    page_range = sys.argv[3]
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        "uvx",
        "--from",
        "surya-ocr",
        "surya_ocr",
        str(pdf_path),
        "--output_dir",
        str(output_dir),
        "--page_range",
        page_range,
    ]
    proc = subprocess.run(cmd, text=True, capture_output=True, check=False)
    if proc.stderr:
        print(proc.stderr, file=sys.stderr, end="")
    emitted = False
    for candidate in sorted(output_dir.rglob("*")):
        if candidate.suffix.lower() in {".txt", ".md"}:
            text = candidate.read_text(encoding="utf-8", errors="replace")
            if text.strip():
                print(text)
                emitted = True
        elif candidate.suffix.lower() == ".json":
            data = json.loads(candidate.read_text(encoding="utf-8", errors="replace"))
            text = "\n".join(s for s in strings(data) if s.strip())
            if text.strip():
                print(text)
                emitted = True
    if proc.returncode != 0:
        if proc.stdout:
            print(proc.stdout, end="")
        return proc.returncode
    if not emitted:
        print(proc.stdout, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
