#!/usr/bin/env python3
"""Minimal Streamable HTTP MCP server for K-352 Tailscale comparison.

Modes:
  readonly : Only exposes ping and read_fixture (zero secrets, no side effects).
  runner   : Adds delegate_codex_fixture and get_job_status targeting ONLY the
             secret-free fixture repo with idempotent task_id and sandboxed Codex.
"""
import argparse
import hashlib
import json
import os
import pathlib
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PROTOCOL_VERSION = "2025-03-26"

JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()
FIXTURE_DIR: pathlib.Path = pathlib.Path(".")
MODE = "readonly"


def safe_read_fixture(rel_path: str) -> str:
    target = (FIXTURE_DIR / rel_path).resolve()
    root = FIXTURE_DIR.resolve()
    if not str(target).startswith(str(root) + os.sep) and target != root:
        raise ValueError("Path outside fixture repo is forbidden")
    if not target.is_file():
        raise FileNotFoundError(f"Not a file: {rel_path}")
    return target.read_text(encoding="utf-8", errors="replace")[:8192]


def run_codex_job(task_id: str, instruction: str) -> None:
    t0 = time.time()
    cmd = [
        "codex",
        "exec",
        "-s",
        "workspace-write",
        "--ephemeral",
        "-C",
        str(FIXTURE_DIR),
        instruction,
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=180,
            env={
                "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                "HOME": os.environ.get("HOME", ""),
                "USER": os.environ.get("USER", ""),
                "TERM": "dumb",
            },
        )
        diff_proc = subprocess.run(
            ["git", "-C", str(FIXTURE_DIR), "diff", "--", "."],
            capture_output=True,
            text=True,
            timeout=15,
        )
        test_proc = subprocess.run(
            ["python3", "-m", "unittest", "-v"],
            cwd=str(FIXTURE_DIR),
            capture_output=True,
            text=True,
            timeout=30,
        )
        with JOBS_LOCK:
            JOBS[task_id].update(
                {
                    "status": "completed" if proc.returncode == 0 else "failed",
                    "returncode": proc.returncode,
                    "elapsed_sec": round(time.time() - t0, 2),
                    "agent_stdout_tail": proc.stdout[-2000:],
                    "agent_stderr_tail": proc.stderr[-1000:],
                    "git_diff": diff_proc.stdout[:4000],
                    "test_returncode": test_proc.returncode,
                    "test_output": (test_proc.stdout + test_proc.stderr)[-2000:],
                    "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }
            )
    except Exception as e:
        with JOBS_LOCK:
            JOBS[task_id].update(
                {
                    "status": "error",
                    "error": str(e),
                    "elapsed_sec": round(time.time() - t0, 2),
                    "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }
            )


def get_tools() -> list[dict]:
    tools = [
        {
            "name": "k352_ping",
            "description": "Read-only connectivity check over Tailscale. Echoes nonce and server metadata.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "nonce": {"type": "string", "description": "Caller-supplied nonce string"}
                },
                "required": ["nonce"],
            },
        },
        {
            "name": "k352_read_fixture",
            "description": "Read a file inside the secret-free K-352 fixture repository (read-only).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative file path in fixture repo (e.g. README.md, calc.py, test_calc.py)",
                    }
                },
                "required": ["path"],
            },
        },
    ]
    if MODE == "runner":
        tools.extend(
            [
                {
                    "name": "k352_delegate_codex",
                    "description": (
                        "Run a sandboxed Codex task inside the secret-free K-352 fixture repo. "
                        "Idempotent by task_id: re-sending an existing task_id returns the cached job without re-running."
                    ),
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "task_id": {
                                "type": "string",
                                "description": "Idempotency key for this task",
                            },
                            "instruction": {
                                "type": "string",
                                "description": "Task instruction for Codex inside the fixture repo",
                            },
                            "wait_seconds": {
                                "type": "integer",
                                "description": "Optional sync wait time (0-90s). Default 60.",
                            },
                        },
                        "required": ["task_id", "instruction"],
                    },
                },
                {
                    "name": "k352_job_status",
                    "description": "Retrieve status, git diff, and unittest result for a previously submitted task_id.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "task_id": {"type": "string", "description": "Task id to query"}
                        },
                        "required": ["task_id"],
                    },
                },
            ]
        )
    return tools


def handle_tool_call(name: str, args: dict) -> dict:
    if name == "k352_ping":
        nonce = str(args.get("nonce", ""))
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "ack": f"K352-TS-ACK {nonce}",
                            "mode": MODE,
                            "server": "k352-tailscale-mcp",
                            "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        },
                        ensure_ascii=False,
                    ),
                }
            ]
        }

    if name == "k352_read_fixture":
        rel = str(args.get("path", "README.md"))
        content = safe_read_fixture(rel)
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "path": rel,
                            "sha256": hashlib.sha256(content.encode()).hexdigest()[:16],
                            "content": content,
                        },
                        ensure_ascii=False,
                    ),
                }
            ]
        }

    if MODE == "runner" and name == "k352_delegate_codex":
        task_id = str(args.get("task_id", "")).strip()
        instruction = str(args.get("instruction", "")).strip()
        wait_seconds = max(0, min(90, int(args.get("wait_seconds", 60))))
        if not task_id or not instruction:
            raise ValueError("task_id and instruction are required")

        deduplicated = False
        with JOBS_LOCK:
            if task_id in JOBS:
                deduplicated = True
                JOBS[task_id]["duplicate_hits"] = JOBS[task_id].get("duplicate_hits", 0) + 1
            else:
                JOBS[task_id] = {
                    "task_id": task_id,
                    "status": "running",
                    "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "duplicate_hits": 0,
                }
                t = threading.Thread(target=run_codex_job, args=(task_id, instruction), daemon=True)
                t.start()

        deadline = time.time() + wait_seconds
        while time.time() < deadline:
            with JOBS_LOCK:
                st = JOBS[task_id]["status"]
                if st != "running":
                    break
            time.sleep(0.5)

        with JOBS_LOCK:
            snapshot = dict(JOBS[task_id])
        snapshot["deduplicated"] = deduplicated
        return {"content": [{"type": "text", "text": json.dumps(snapshot, ensure_ascii=False)}]}

    if MODE == "runner" and name == "k352_job_status":
        task_id = str(args.get("task_id", "")).strip()
        with JOBS_LOCK:
            job = JOBS.get(task_id)
        if not job:
            return {
                "isError": True,
                "content": [{"type": "text", "text": f"Unknown task_id: {task_id}"}],
            }
        return {"content": [{"type": "text", "text": json.dumps(job, ensure_ascii=False)}]}

    return {"isError": True, "content": [{"type": "text", "text": f"Unknown tool: {name}"}]}


class MCPHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        ts = time.strftime("%H:%M:%S", time.gmtime())
        print(f"[{ts}] {self.address_string()} {fmt % args}", flush=True)

    def _send_json(self, code: int, payload: dict | None):
        if payload is None:
            self.send_response(code)
            self.end_headers()
            return
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self._send_json(200, {"ok": True, "mode": MODE, "jobs": len(JOBS)})
            return
        self._send_json(405, {"error": "Use POST for MCP Streamable HTTP"})

    def do_POST(self):
        if self.path not in ("/mcp", "/"):
            self._send_json(404, {"error": "Not found"})
            return
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        try:
            msg = json.loads(raw.decode("utf-8"))
        except Exception as e:
            self._send_json(
                400,
                {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": str(e)}},
            )
            return

        req_id = msg.get("id")
        method = msg.get("method", "")
        params = msg.get("params") or {}

        if method == "notifications/initialized":
            self._send_json(202, None)
            return

        if method == "initialize":
            self._send_json(
                200,
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "protocolVersion": PROTOCOL_VERSION,
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "k352-tailscale-mcp", "version": "0.1.0"},
                    },
                },
            )
            return

        if method == "ping":
            self._send_json(200, {"jsonrpc": "2.0", "id": req_id, "result": {}})
            return

        if method == "tools/list":
            self._send_json(200, {"jsonrpc": "2.0", "id": req_id, "result": {"tools": get_tools()}})
            return

        if method == "tools/call":
            try:
                res = handle_tool_call(params.get("name", ""), params.get("arguments") or {})
                self._send_json(200, {"jsonrpc": "2.0", "id": req_id, "result": res})
            except Exception as e:
                self._send_json(
                    200,
                    {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {"isError": True, "content": [{"type": "text", "text": str(e)}]},
                    },
                )
            return

        self._send_json(
            200,
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            },
        )


def main():
    global FIXTURE_DIR, MODE
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=18352)
    ap.add_argument("--mode", choices=["readonly", "runner"], default="readonly")
    ap.add_argument("--fixture", required=True)
    args = ap.parse_args()
    FIXTURE_DIR = pathlib.Path(args.fixture).resolve()
    MODE = args.mode
    srv = ThreadingHTTPServer((args.host, args.port), MCPHandler)
    print(f"k352-tailscale-mcp listening on http://{args.host}:{args.port}/mcp mode={MODE} fixture={FIXTURE_DIR}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
