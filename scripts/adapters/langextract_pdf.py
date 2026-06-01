from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path


SCRIPT = r"""
from pathlib import Path
import os
import sys
import langextract as lx

text = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")
prompt = sys.argv[2]
model_id = sys.argv[3]
provider = sys.argv[4]
model_url = sys.argv[5]
base_url = sys.argv[6]
api_key = sys.argv[7]

examples = [
    lx.data.ExampleData(
        text="Bellingcat investigated Syria using open-source evidence and satellite imagery.",
        extractions=[
            lx.data.Extraction(
                extraction_class="organization",
                extraction_text="Bellingcat",
            ),
            lx.data.Extraction(
                extraction_class="method",
                extraction_text="open-source evidence",
            ),
            lx.data.Extraction(
                extraction_class="method",
                extraction_text="satellite imagery",
            ),
        ],
    )
]

kwargs = {
    "text_or_documents": text[:60000],
    "prompt_description": prompt,
    "examples": examples,
}
if provider == "openai":
    from langextract.factory import ModelConfig
    provider_kwargs = {}
    if api_key:
        provider_kwargs["api_key"] = api_key
    if base_url:
        provider_kwargs["base_url"] = base_url
    kwargs["config"] = ModelConfig(
        model_id=model_id,
        provider="openai",
        provider_kwargs=provider_kwargs,
    )
else:
    kwargs["model_id"] = model_id
    if model_url:
        kwargs["model_url"] = model_url

result = lx.extract(**kwargs)
for extraction in result.extractions:
    print(extraction.extraction_text)
    if extraction.attributes:
        print(extraction.attributes)
"""


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: langextract_pdf.py <pdf-path> <prompt>", file=sys.stderr)
        return 2
    model_id = os.environ.get("LANGEXTRACT_MODEL")
    if not model_id:
        print(
            "missing LANGEXTRACT_MODEL; set a local or cloud model identifier "
            "and provide the provider API key only if that backend requires one",
            file=sys.stderr,
        )
        return 2
    provider = os.environ.get("LANGEXTRACT_PROVIDER", "").strip().lower()
    model_url = os.environ.get("LANGEXTRACT_MODEL_URL", "").strip()
    base_url = os.environ.get("LANGEXTRACT_BASE_URL", "").strip()
    api_key = os.environ.get("LANGEXTRACT_API_KEY", "").strip()
    package = "langextract[openai]" if provider == "openai" else "langextract"
    text_proc = subprocess.run(
        ["pdftotext", "-enc", "UTF-8", sys.argv[1], "-"],
        text=True,
        capture_output=True,
        check=False,
    )
    if text_proc.returncode != 0:
        print(text_proc.stderr, file=sys.stderr, end="")
        return text_proc.returncode
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as text_file:
        text_file.write(text_proc.stdout)
        text_path = text_file.name
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as script_file:
        script_file.write(SCRIPT)
        script_path = script_file.name
    try:
        proc = subprocess.run(
            [
                "uvx",
                "--from",
                package,
                "python",
                script_path,
                text_path,
                sys.argv[2],
                model_id,
                provider,
                model_url,
                base_url,
                api_key,
            ],
            text=True,
            capture_output=True,
            check=False,
        )
    finally:
        Path(text_path).unlink(missing_ok=True)
        Path(script_path).unlink(missing_ok=True)
    if proc.stderr:
        print(proc.stderr, file=sys.stderr, end="")
    print(proc.stdout, end="")
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
