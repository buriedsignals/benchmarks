from __future__ import annotations

import json
import mimetypes
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


PARSE_URL = "https://api.extend.ai/parse"
UPLOAD_URL = "https://api.extend.ai/files/upload"
API_VERSION = "2026-02-09"


def auth_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {os.environ['EXTEND_API_KEY']}",
        "x-extend-api-version": API_VERSION,
    }


def upload_file(path: Path) -> str:
    boundary = "----bs-benchmark-extend-boundary"
    mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    head = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
        f"Content-Type: {mime_type}\r\n\r\n"
    ).encode("utf-8")
    tail = f"\r\n--{boundary}--\r\n".encode("utf-8")
    body = head + path.read_bytes() + tail
    headers = auth_headers()
    headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    req = urllib.request.Request(
        UPLOAD_URL,
        data=body,
        method="POST",
        headers=headers,
    )
    with urllib.request.urlopen(req, timeout=300) as res:
        data = json.loads(res.read().decode("utf-8", errors="replace"))
    file_id = data.get("id")
    if not file_id:
        raise RuntimeError(f"Extend upload response missing file id: {data}")
    return file_id


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: extend_parse.py <pdf-path-or-url>", file=sys.stderr)
        return 2
    if not os.environ.get("EXTEND_API_KEY"):
        print("missing EXTEND_API_KEY", file=sys.stderr)
        return 2
    source = sys.argv[1]
    file_payload: dict[str, str]
    if source.startswith(("http://", "https://")):
        file_payload = {
            "url": source,
            "name": source.rsplit("/", 1)[-1] or "document.pdf",
        }
    else:
        try:
            file_payload = {"id": upload_file(Path(source))}
        except (OSError, RuntimeError, urllib.error.HTTPError, urllib.error.URLError) as exc:
            if isinstance(exc, urllib.error.HTTPError):
                print(exc.read().decode("utf-8", errors="replace"), file=sys.stderr)
            else:
                print(str(exc), file=sys.stderr)
            return 1
    payload = json.dumps(
        {
            "file": file_payload,
            "config": {
                "target": "markdown",
                "chunkingStrategy": {"type": "page"},
                "engine": "parse_performance",
                "engineVersion": "2.0.0",
                "blockOptions": {
                    "tables": {"targetFormat": "markdown", "enabled": True},
                    "figures": {"enabled": True},
                },
            },
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        PARSE_URL,
        data=payload,
        method="POST",
        headers={**auth_headers(), "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as res:
            body = res.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        print(exc.read().decode("utf-8", errors="replace"), file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    data = json.loads(body)
    status = data.get("status")
    if status and status != "PROCESSED":
        print(json.dumps(data, indent=2), file=sys.stderr)
        return 1
    chunks = ((data.get("output") or {}).get("chunks") or [])
    for chunk in chunks:
        content = chunk.get("content")
        if content:
            print(content)
            print()
    usage = data.get("usage") or {}
    metrics = data.get("metrics") or {}
    print(
        f"\n[extend metrics] pages={metrics.get('pageCount')} "
        f"processing_ms={metrics.get('processingTimeMs')} credits={usage.get('credits')}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
