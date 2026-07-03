from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 4:
        print("usage: scrapling_fetch.py <url> <output_dir> <timeout_seconds>", file=sys.stderr)
        return 2
    url, output_dir, timeout_seconds = sys.argv[1], sys.argv[2], sys.argv[3]
    out_path = Path(output_dir) / "scrapling-stealthy.md"
    timeout_ms = str(int(float(timeout_seconds)) * 1000)
    command = [
        "uvx",
        "--from",
        "scrapling[shell]",
        "scrapling",
        "extract",
        "stealthy-fetch",
        url,
        str(out_path),
        "--timeout",
        timeout_ms,
    ]
    proc = subprocess.run(command, capture_output=True, text=True)
    if proc.stderr:
        print(proc.stderr, file=sys.stderr)
    if proc.stdout:
        print(proc.stdout, file=sys.stderr)
    if proc.returncode != 0:
        return proc.returncode
    if not out_path.exists() or out_path.stat().st_size == 0:
        print("scrapling produced no output file", file=sys.stderr)
        return 1
    print(out_path.read_text(encoding="utf-8", errors="replace"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
