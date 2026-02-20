#!/usr/bin/env python3
"""
Tool Studio server

Runs a static site + lightweight JSON API to execute selected local CLI tools.

Usage:
  python3 tool_studio_server.py
Open:
  https://localhost:8450/tool-studio.html
"""

from __future__ import annotations

import json
import os
import re
import ssl
import subprocess
import sys
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


PORT = 8450
CERT = "cert.pem"
KEY = "key.pem"
BASE_DIR = Path(__file__).resolve().parent
DEV_DIR = BASE_DIR.parent

TOOL_DEFS = {
    "competitive-deep-dive": {
        "repo": DEV_DIR / "competitive-deep-dive",
        "entrypoint": "main.py",
    },
    "protocol-positioning": {
        "repo": DEV_DIR / "protocol-positioning",
        "entrypoint": "main.py",
    },
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def find_python_bin() -> str:
    for candidate in ("python3.12", "python3", sys.executable):
        if not candidate:
            continue
        path = shutil_which(candidate)
        if path:
            return path
    return sys.executable


def shutil_which(binary: str) -> str | None:
    from shutil import which
    return which(binary)


PYTHON_BIN = find_python_bin()
ARTIFACT_RE = re.compile(r"(?:Markdown|Word doc|Research data saved)\s*:\s*(.+)$")


@dataclass
class Job:
    id: str
    tool: str
    status: str = "queued"  # queued | running | succeeded | failed
    created_at: str = field(default_factory=utc_now_iso)
    started_at: str | None = None
    finished_at: str | None = None
    return_code: int | None = None
    error: str | None = None
    logs: list[str] = field(default_factory=list)
    artifacts: list[dict[str, str]] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tool": self.tool,
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "return_code": self.return_code,
            "error": self.error,
            "logs": self.logs[-300:],
            "artifacts": [
                {"id": a["id"], "label": a["label"], "name": a["name"]}
                for a in self.artifacts
            ],
        }


JOBS: dict[str, Job] = {}
JOBS_LOCK = threading.Lock()


def append_log(job: Job, line: str) -> None:
    clean = line.rstrip("\n")
    if not clean:
        return
    job.logs.append(clean)
    if len(job.logs) > 1200:
        del job.logs[:400]


def _safe_artifact_path(tool: str, raw_path: str) -> Path | None:
    tool_repo = TOOL_DEFS[tool]["repo"].resolve()
    p = Path(raw_path.strip())
    if not p.is_absolute():
        p = (tool_repo / p).resolve()
    else:
        p = p.resolve()

    try:
        p.relative_to(tool_repo)
    except ValueError:
        return None
    if not p.exists() or not p.is_file():
        return None
    return p


def maybe_register_artifact(job: Job, line: str) -> None:
    m = ARTIFACT_RE.search(line)
    if not m:
        return
    raw_path = m.group(1).strip()
    path = _safe_artifact_path(job.tool, raw_path)
    if not path:
        return
    for a in job.artifacts:
        if a["path"] == str(path):
            return
    label = "File"
    if "Markdown" in line:
        label = "Markdown"
    elif "Word doc" in line:
        label = "Word"
    elif "Research data saved" in line:
        label = "Research JSON"
    job.artifacts.append(
        {
            "id": uuid.uuid4().hex[:8],
            "label": label,
            "name": path.name,
            "path": str(path),
        }
    )


def build_stdin(tool: str, payload: dict[str, Any]) -> str:
    if tool == "competitive-deep-dive":
        competitor_name = (payload.get("competitor_name") or "").strip()
        if not competitor_name:
            raise ValueError("competitor_name is required")
        lines = [
            "1",  # direct mode
            (payload.get("your_project") or "").strip(),
            competitor_name,
            (payload.get("competitor_website") or "").strip(),
            (payload.get("competitor_context") or "").strip(),
            "",  # end competitors
        ]
        return "\n".join(lines) + "\n"

    if tool == "protocol-positioning":
        your_protocol = (payload.get("your_protocol_name") or "").strip()
        competitor_name = (payload.get("competitor_name") or "").strip()
        if not your_protocol:
            raise ValueError("your_protocol_name is required")
        if not competitor_name:
            raise ValueError("competitor_name is required")
        lines = [
            your_protocol,
            (payload.get("your_protocol_website") or "").strip(),
            (payload.get("your_protocol_context") or "").strip(),
            competitor_name,
            (payload.get("competitor_website") or "").strip(),
            (payload.get("competitor_context") or "").strip(),
            "",  # stop competitors
        ]
        return "\n".join(lines) + "\n"

    raise ValueError("unsupported tool")


def run_job(job: Job, payload: dict[str, Any]) -> None:
    tool_cfg = TOOL_DEFS[job.tool]
    repo = tool_cfg["repo"]
    entrypoint = tool_cfg["entrypoint"]

    with JOBS_LOCK:
        job.status = "running"
        job.started_at = utc_now_iso()

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    stdin_blob = build_stdin(job.tool, payload)
    cmd = [PYTHON_BIN, entrypoint]

    append_log(job, f"$ {' '.join(cmd)}  (cwd={repo})")
    proc = None
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(repo),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env,
        )
        assert proc.stdin is not None
        assert proc.stdout is not None
        proc.stdin.write(stdin_blob)
        proc.stdin.close()

        for line in proc.stdout:
            append_log(job, line)
            maybe_register_artifact(job, line)

        rc = proc.wait(timeout=7200)
        with JOBS_LOCK:
            job.return_code = rc
            job.finished_at = utc_now_iso()
            job.status = "succeeded" if rc == 0 else "failed"
            if rc != 0:
                job.error = f"tool exited with code {rc}"
    except Exception as ex:
        if proc and proc.poll() is None:
            proc.kill()
        with JOBS_LOCK:
            job.return_code = -1
            job.finished_at = utc_now_iso()
            job.status = "failed"
            job.error = str(ex)
        append_log(job, f"[error] {ex}")


class StudioHandler(SimpleHTTPRequestHandler):
    server_version = "ToolStudio/0.1"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(BASE_DIR), **kwargs)

    def _json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        super().end_headers()

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length > 0 else b"{}"
        return json.loads(raw.decode("utf-8"))

    def _not_found(self) -> None:
        self._json({"error": "not found"}, status=404)

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/run/"):
            tool = parsed.path.split("/")[-1]
            if tool not in TOOL_DEFS:
                self._json({"error": "unsupported tool"}, status=400)
                return
            try:
                payload = self._read_json()
                _ = build_stdin(tool, payload)
            except Exception as ex:
                self._json({"error": str(ex)}, status=400)
                return

            job = Job(id=uuid.uuid4().hex, tool=tool)
            with JOBS_LOCK:
                JOBS[job.id] = job
            worker = threading.Thread(target=run_job, args=(job, payload), daemon=True)
            worker.start()
            self._json({"job_id": job.id, "status": job.status}, status=202)
            return

        self._not_found()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/health":
            self._json({"ok": True, "time": utc_now_iso()})
            return

        if path.startswith("/api/jobs/") and "/artifacts/" not in path:
            job_id = path.split("/")[-1]
            with JOBS_LOCK:
                job = JOBS.get(job_id)
            if not job:
                self._not_found()
                return
            self._json(job.to_json())
            return

        if path.startswith("/api/jobs/") and "/artifacts/" in path:
            parts = path.strip("/").split("/")
            # api/jobs/<job_id>/artifacts/<artifact_id>
            if len(parts) != 5:
                self._not_found()
                return
            _, _, job_id, _, artifact_id = parts
            with JOBS_LOCK:
                job = JOBS.get(job_id)
            if not job:
                self._not_found()
                return
            artifact = next((a for a in job.artifacts if a["id"] == artifact_id), None)
            if not artifact:
                self._not_found()
                return
            file_path = Path(artifact["path"])
            if not file_path.exists():
                self._not_found()
                return

            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header(
                "Content-Disposition",
                f'attachment; filename="{file_path.name}"'
            )
            fs = file_path.stat()
            self.send_header("Content-Length", str(fs.st_size))
            self.end_headers()
            with open(file_path, "rb") as f:
                self.copyfile(f, self.wfile)
            return

        if path == "/tool-studio":
            self.path = "/tool-studio.html"

        super().do_GET()


def check_mkcert() -> bool:
    try:
        subprocess.run(["mkcert", "--version"], capture_output=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def generate_certs_mkcert() -> None:
    subprocess.run(["mkcert", "-install"], check=True, capture_output=True)
    subprocess.run(
        ["mkcert", "-key-file", KEY, "-cert-file", CERT, "localhost", "127.0.0.1"],
        check=True,
    )


def generate_certs_openssl() -> None:
    subprocess.run(
        [
            "openssl", "req", "-x509", "-newkey", "rsa:2048",
            "-keyout", KEY, "-out", CERT,
            "-days", "365", "-nodes",
            "-subj", "/CN=localhost",
        ],
        check=True,
        capture_output=True,
    )


def ensure_certs() -> None:
    os.chdir(BASE_DIR)
    cert_path = BASE_DIR / CERT
    key_path = BASE_DIR / KEY
    if cert_path.exists() and key_path.exists():
        return
    if check_mkcert():
        generate_certs_mkcert()
        return
    generate_certs_openssl()


def main() -> None:
    ensure_certs()

    httpd = HTTPServer(("0.0.0.0", PORT), StudioHandler)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(str(BASE_DIR / CERT), str(BASE_DIR / KEY))
    httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)

    print(f"Tool Studio running at https://localhost:{PORT}/tool-studio.html")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[studio] stopped")


if __name__ == "__main__":
    main()
