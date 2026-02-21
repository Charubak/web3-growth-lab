#!/usr/bin/env python3
"""
Tool Studio server

Modes:
- demo (default): safe public demo responses + downloadable artifacts
- live: runs local CLI tools from configured repos

Local usage:
  python3 tool_studio_server.py

Fly usage:
  PORT=8080 TOOL_STUDIO_MODE=demo python3 tool_studio_server.py
"""

from __future__ import annotations

import json
import os
import re
import ssl
import subprocess
import sys
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


def _env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    val = os.getenv(name)
    if val is None:
        return default
    try:
        return int(val)
    except ValueError:
        return default


HOST = os.getenv("TOOL_STUDIO_HOST", "0.0.0.0")
PORT = _env_int("PORT", _env_int("TOOL_STUDIO_PORT", 8450))
MODE = os.getenv("TOOL_STUDIO_MODE", "demo").strip().lower()
USE_TLS = _env_bool("TOOL_STUDIO_TLS", default=(PORT == 8450))

CERT = os.getenv("TOOL_STUDIO_CERT", "cert.pem")
KEY = os.getenv("TOOL_STUDIO_KEY", "key.pem")
BASE_DIR = Path(__file__).resolve().parent
DEV_DIR = BASE_DIR.parent
TOOLS_ROOT = Path(os.getenv("TOOLS_ROOT", str(DEV_DIR)))
ARTIFACT_ROOT = Path(
    os.getenv("TOOL_STUDIO_ARTIFACT_ROOT", "/tmp/tool-studio-artifacts")
).resolve()

API_KEY = os.getenv("TOOL_STUDIO_API_KEY", "").strip()
MAX_BODY_BYTES = _env_int("TOOL_STUDIO_MAX_BODY_BYTES", 24_000)
MAX_RUNNING_JOBS = _env_int("TOOL_STUDIO_MAX_RUNNING_JOBS", 2)
JOB_RETENTION_SEC = _env_int("TOOL_STUDIO_JOB_RETENTION_SEC", 3600)
RATE_WINDOW_SEC = _env_int("TOOL_STUDIO_RATE_WINDOW_SEC", 60)
RATE_GET_MAX = _env_int("TOOL_STUDIO_RATE_GET_MAX", 120)
RATE_POST_MAX = _env_int("TOOL_STUDIO_RATE_POST_MAX", 10)

DEFAULT_ALLOWED_ORIGINS = ",".join(
    [
        "https://web3growthlab.com",
        "https://www.web3growthlab.com",
        "https://api.web3growthlab.com",
        "http://localhost:8443",
        "https://localhost:8443",
        "http://localhost:8450",
        "https://localhost:8450",
    ]
)
ALLOWED_ORIGINS = {
    origin.strip()
    for origin in os.getenv("TOOL_STUDIO_ALLOWED_ORIGINS", DEFAULT_ALLOWED_ORIGINS).split(",")
    if origin.strip()
}

TOOL_DEFS = {
    "competitive-deep-dive": {
        "repo": TOOLS_ROOT / "competitive-deep-dive",
        "entrypoint": "main.py",
    },
    "protocol-positioning": {
        "repo": TOOLS_ROOT / "protocol-positioning",
        "entrypoint": "main.py",
    },
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def find_python_bin() -> str:
    from shutil import which

    for candidate in ("python3.12", "python3", sys.executable):
        if not candidate:
            continue
        path = which(candidate)
        if path:
            return path
    return sys.executable


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
RATE_BUCKETS: dict[str, deque[float]] = {}
RATE_LOCK = threading.Lock()


def cleanup_jobs() -> None:
    cutoff = time.time() - JOB_RETENTION_SEC
    stale_ids: list[str] = []
    with JOBS_LOCK:
        for job_id, job in JOBS.items():
            if not job.finished_at:
                continue
            try:
                finished = datetime.fromisoformat(job.finished_at).timestamp()
            except ValueError:
                stale_ids.append(job_id)
                continue
            if finished < cutoff:
                stale_ids.append(job_id)
        for job_id in stale_ids:
            JOBS.pop(job_id, None)


def append_log(job: Job, line: str) -> None:
    clean = line.rstrip("\n")
    if not clean:
        return
    job.logs.append(clean)
    if len(job.logs) > 1200:
        del job.logs[:400]


def register_artifact(job: Job, label: str, file_path: Path) -> None:
    p = file_path.resolve()
    for existing in job.artifacts:
        if existing["path"] == str(p):
            return
    job.artifacts.append(
        {
            "id": uuid.uuid4().hex[:8],
            "label": label,
            "name": p.name,
            "path": str(p),
        }
    )


def _safe_artifact_path(tool: str, raw_path: str) -> Path | None:
    tool_repo = TOOL_DEFS[tool]["repo"].resolve()
    p = Path(raw_path.strip())
    p = (tool_repo / p).resolve() if not p.is_absolute() else p.resolve()
    try:
        p.relative_to(tool_repo)
    except ValueError:
        return None
    if not p.exists() or not p.is_file():
        return None
    return p


def is_path_safe_for_job(job: Job, p: Path) -> bool:
    p = p.resolve()
    roots = [ARTIFACT_ROOT / job.id]
    tool_repo = TOOL_DEFS.get(job.tool, {}).get("repo")
    if isinstance(tool_repo, Path):
        roots.append(tool_repo.resolve())
    for root in roots:
        try:
            p.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def maybe_register_artifact_from_line(job: Job, line: str) -> None:
    m = ARTIFACT_RE.search(line)
    if not m:
        return
    raw_path = m.group(1).strip()
    path = _safe_artifact_path(job.tool, raw_path)
    if not path:
        return
    label = "File"
    if "Markdown" in line:
        label = "Markdown"
    elif "Word doc" in line:
        label = "Word"
    elif "Research data saved" in line:
        label = "Research JSON"
    register_artifact(job, label, path)


def build_stdin(tool: str, payload: dict[str, Any]) -> str:
    if tool == "competitive-deep-dive":
        competitor_name = (payload.get("competitor_name") or "").strip()
        if not competitor_name:
            raise ValueError("competitor_name is required")
        lines = [
            "1",
            (payload.get("your_project") or "").strip(),
            competitor_name,
            (payload.get("competitor_website") or "").strip(),
            (payload.get("competitor_context") or "").strip(),
            "",
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
            "",
        ]
        return "\n".join(lines) + "\n"

    raise ValueError("unsupported tool")


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "project"


def run_demo_job(job: Job, payload: dict[str, Any]) -> None:
    with JOBS_LOCK:
        job.status = "running"
        job.started_at = utc_now_iso()

    target = (
        payload.get("competitor_name")
        or payload.get("your_protocol_name")
        or payload.get("your_project")
        or "project"
    )
    target_slug = _slug(str(target))

    out_dir = (ARTIFACT_ROOT / job.id).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    append_log(job, f"[demo] Starting {job.tool} for {target}...")
    time.sleep(0.8)
    append_log(job, "[demo] Pulling market and narrative signals...")
    time.sleep(0.7)
    append_log(job, "[demo] Synthesizing executive recommendations...")
    time.sleep(0.6)

    if job.tool == "competitive-deep-dive":
        md_path = out_dir / f"demo_deepdive_{target_slug}.md"
        json_path = out_dir / f"demo_deepdive_{target_slug}.json"
        md_path.write_text(
            "\n".join(
                [
                    f"# Demo Competitive Deep-Dive: {target}",
                    "",
                    "## Executive Snapshot",
                    "- Market momentum: Positive",
                    "- Narrative threat: Medium",
                    "- Recommended move: Clarify differentiated positioning in 2-week sprint",
                    "",
                    "## Suggested Campaign Angle",
                    "\"Own the execution narrative with proof-backed data stories.\"",
                ]
            ),
            encoding="utf-8",
        )
        json_path.write_text(
            json.dumps(
                {
                    "mode": "demo",
                    "tool": job.tool,
                    "target": target,
                    "summary": {
                        "threat_level": "medium",
                        "priority_move": "Double down on data-backed messaging",
                    },
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        register_artifact(job, "Markdown", md_path)
        register_artifact(job, "Research JSON", json_path)
    else:
        md_path = out_dir / f"demo_positioning_{target_slug}.md"
        csv_path = out_dir / f"demo_positioning_{target_slug}.csv"
        md_path.write_text(
            "\n".join(
                [
                    f"# Demo Protocol Positioning: {target}",
                    "",
                    "## Positioning Matrix Summary",
                    "- Strength: Narrative clarity",
                    "- Weakness: Distribution dependence",
                    "- Opportunity: Partnership-led onboarding funnels",
                    "- Threat: Faster-moving exchange narratives",
                ]
            ),
            encoding="utf-8",
        )
        csv_path.write_text(
            "\n".join(
                [
                    "factor,your_protocol,competitor,advantage",
                    "narrative_clarity,8,7,your_protocol",
                    "growth_velocity,7,8,competitor",
                    "community_quality,8,7,your_protocol",
                ]
            ),
            encoding="utf-8",
        )
        register_artifact(job, "Markdown", md_path)
        register_artifact(job, "Matrix CSV", csv_path)

    append_log(job, "[demo] Completed successfully.")
    with JOBS_LOCK:
        job.return_code = 0
        job.finished_at = utc_now_iso()
        job.status = "succeeded"


def run_live_job(job: Job, payload: dict[str, Any]) -> None:
    tool_cfg = TOOL_DEFS[job.tool]
    repo = tool_cfg["repo"]
    entrypoint = tool_cfg["entrypoint"]

    with JOBS_LOCK:
        job.status = "running"
        job.started_at = utc_now_iso()

    if not repo.exists():
        with JOBS_LOCK:
            job.return_code = -1
            job.finished_at = utc_now_iso()
            job.status = "failed"
            job.error = f"tool repo not found: {repo}"
        append_log(job, f"[error] tool repo not found: {repo}")
        return

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
            maybe_register_artifact_from_line(job, line)

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


def run_job(job: Job, payload: dict[str, Any]) -> None:
    if MODE == "live":
        run_live_job(job, payload)
        return
    run_demo_job(job, payload)


def current_running_jobs() -> int:
    with JOBS_LOCK:
        return sum(1 for j in JOBS.values() if j.status in {"queued", "running"})


def take_rate_slot(ip: str, method: str) -> bool:
    key = f"{ip}:{method}"
    now = time.time()
    max_hits = RATE_POST_MAX if method == "POST" else RATE_GET_MAX
    with RATE_LOCK:
        q = RATE_BUCKETS.setdefault(key, deque())
        cutoff = now - RATE_WINDOW_SEC
        while q and q[0] < cutoff:
            q.popleft()
        if len(q) >= max_hits:
            return False
        q.append(now)
        return True


class StudioHandler(SimpleHTTPRequestHandler):
    server_version = "ToolStudio/0.2"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(BASE_DIR), **kwargs)

    def log_message(self, format: str, *args) -> None:
        super().log_message(format, *args)

    def _origin(self) -> str:
        return (self.headers.get("Origin") or "").strip()

    def _origin_allowed(self) -> bool:
        origin = self._origin()
        if not origin:
            return True
        return origin in ALLOWED_ORIGINS

    def _client_ip(self) -> str:
        forwarded = (self.headers.get("X-Forwarded-For") or "").strip()
        if forwarded:
            return forwarded.split(",")[0].strip()
        return self.client_address[0]

    def _authorized(self) -> bool:
        if MODE != "live":
            return True
        if not API_KEY:
            return False
        return (self.headers.get("X-Tool-Studio-Key") or "").strip() == API_KEY

    def end_headers(self) -> None:
        origin = self._origin()
        if origin and origin in ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Tool-Studio-Key")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        super().end_headers()

    def _json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length > MAX_BODY_BYTES:
            raise ValueError("payload too large")
        raw = self.rfile.read(length) if length > 0 else b"{}"
        return json.loads(raw.decode("utf-8"))

    def _not_found(self) -> None:
        self._json({"error": "not found"}, status=404)

    def _forbidden(self, message: str = "forbidden") -> None:
        self._json({"error": message}, status=403)

    def _too_many(self) -> None:
        self._json({"error": "rate limit exceeded"}, status=429)

    def _require_origin(self) -> bool:
        if self._origin_allowed():
            return True
        self._forbidden("origin not allowed")
        return False

    def do_OPTIONS(self) -> None:
        if not self._require_origin():
            return
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()

    def do_POST(self) -> None:
        cleanup_jobs()
        if not self._require_origin():
            return
        if not take_rate_slot(self._client_ip(), "POST"):
            self._too_many()
            return
        if MODE == "live" and not self._authorized():
            self._forbidden("missing or invalid api key")
            return

        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/run/"):
            if current_running_jobs() >= MAX_RUNNING_JOBS:
                self._json(
                    {"error": "too many jobs running, please retry shortly"},
                    status=429,
                )
                return

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
            self._json({"job_id": job.id, "status": job.status, "mode": MODE}, status=202)
            return

        self._not_found()

    def do_GET(self) -> None:
        cleanup_jobs()
        if not self._require_origin():
            return
        if not take_rate_slot(self._client_ip(), "GET"):
            self._too_many()
            return

        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/health":
            self._json({"ok": True, "time": utc_now_iso(), "mode": MODE})
            return

        if path.startswith("/api/") and MODE == "live" and not self._authorized():
            self._forbidden("missing or invalid api key")
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
            file_path = Path(artifact["path"]).resolve()
            if not file_path.exists() or not file_path.is_file():
                self._not_found()
                return
            if not is_path_safe_for_job(job, file_path):
                self._forbidden("artifact path denied")
                return

            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header(
                "Content-Disposition",
                f'attachment; filename="{file_path.name}"',
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
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-keyout",
            KEY,
            "-out",
            CERT,
            "-days",
            "365",
            "-nodes",
            "-subj",
            "/CN=localhost",
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
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)

    httpd = HTTPServer((HOST, PORT), StudioHandler)
    scheme = "http"

    if USE_TLS:
        ensure_certs()
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(str(BASE_DIR / CERT), str(BASE_DIR / KEY))
        httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
        scheme = "https"

    print(
        f"Tool Studio [{MODE}] running at {scheme}://{HOST}:{PORT}/tool-studio.html",
        flush=True,
    )
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[studio] stopped", flush=True)


if __name__ == "__main__":
    main()
