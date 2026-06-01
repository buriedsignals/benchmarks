from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path


SCRIPT = r"""
from pathlib import Path
import sys
from llama_cloud import LlamaCloud

path = Path(sys.argv[1])
client = LlamaCloud()
file = client.files.create(file=str(path), purpose="parse")
result = client.parsing.parse(
    file_id=file.id,
    tier="agentic",
    version="latest",
    expand=["markdown"],
)
for page in result.markdown.pages:
    print(page.markdown)
"""


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: llamaparse.py <pdf-path>", file=sys.stderr)
        return 2
    if not os.environ.get("LLAMA_CLOUD_API_KEY"):
        print("missing LLAMA_CLOUD_API_KEY", file=sys.stderr)
        return 2
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(SCRIPT)
        script_path = f.name
    try:
        proc = subprocess.run(
            ["uvx", "--from", "llama-cloud", "python", script_path, sys.argv[1]],
            text=True,
            capture_output=True,
            check=False,
        )
    finally:
        Path(script_path).unlink(missing_ok=True)
    if proc.stderr:
        print(proc.stderr, file=sys.stderr, end="")
    print(proc.stdout, end="")
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
