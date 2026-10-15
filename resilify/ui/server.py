"""Resilify Developer Workstation HTTP Server.

Lightweight, dependency-free HTTP server powered by Python's built-in
ThreadingHTTPServer. Serves API endpoints and static frontend assets.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import socket
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse, unquote

from resilify.ui import api

STATIC_DIR = Path(__file__).resolve().parent / "static"


class ResilifyUIHandler(BaseHTTPRequestHandler):
    """Request handler for Resilify Developer Workstation UI and API."""

    server_version = "ResilifyServer/0.3.0"

    def do_OPTIONS(self) -> None:
        """Handle CORS preflight requests."""
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def send_json(self, data: any, status: int = 200) -> None:
        """Send a JSON HTTP response with security and CORS headers."""
        payload = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(payload)

    def send_file(self, file_path: Path, content_type: str = "text/html") -> None:
        """Send a static file from disk."""
        if not file_path.exists() or not file_path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, f"File {file_path.name} not found")
            return

        try:
            with open(file_path, "rb") as f:
                content = f.read()

            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, f"Error reading file: {e}")

    def send_download(self, payload: bytes, filename: str, content_type: str) -> None:
        """Send a binary/text file download with robust RFC 6266 and CORS headers."""
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"; filename*=UTF-8\'\'{filename}')
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Expose-Headers", "Content-Disposition, Content-Type, Content-Length")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        """Route GET requests with top-level error handling."""
        try:
            self._handle_get()
        except Exception as e:
            sys.stderr.write(f"[Server Exception in GET {self.path}]: {e}\n")
            self.send_json({"error": str(e)}, status=500)

    def _handle_get(self) -> None:
        """Route GET requests to API handlers or static files."""
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        project = query.get("project", ["linkwatch"])[0]

        # API Endpoints
        if path == "/api/projects":
            self.send_json(api.get_projects())
            return

        if path == "/api/overview":
            self.send_json(api.get_overview(project_id=project))
            return

        if path == "/api/dependencies":
            search = query.get("search", [""])[0]
            risk = query.get("risk", [""])[0]
            manifest = query.get("manifest", [""])[0]
            self.send_json(api.get_dependencies(project_id=project, search=search, risk_filter=risk, manifest_filter=manifest))
            return

        if path.startswith("/api/workbench"):
            pkg = query.get("package", [""])[0]
            if not pkg and "/" in path[len("/api/workbench"):].strip("/"):
                pkg = path[len("/api/workbench"):].strip("/").split("/")[0]
            self.send_json(api.get_workbench(project_id=project, package_name=pkg if pkg else None))
            return

        if path == "/api/runs":
            self.send_json(api.get_runs(project_id=project))
            return

        if path == "/api/capsules":
            self.send_json(api.get_capsules(project_id=project))
            return

        # Direct file download by exact filename in URL path
        if path.startswith("/api/capsules/export/"):
            raw_filename = unquote(path[len("/api/capsules/export/"):].strip("/"))
            fmt = "markdown" if raw_filename.endswith(".md") else "json"
            cid = raw_filename.rsplit(".", 1)[0]

            if raw_filename.startswith("synthetic") or raw_filename.startswith("SYNTHETIC"):
                synth = api.get_synthetic_capsule()
                if not synth:
                    self.send_error(HTTPStatus.NOT_FOUND, "Synthetic capsule fixture not found")
                    return
                if fmt == "markdown":
                    md_content = f"""# Dependency Exit Capsule: {synth.get('target_dependency', {}).get('name')}

> **Notice:** THIS IS A SYNTHETIC TEST FIXTURE FOR SCHEMA VALIDATION ONLY.

- **Capsule ID:** `{synth.get('capsule_id')}`
- **Repository:** `{synth.get('repository', {}).get('url')}` (`{str(synth.get('repository', {}).get('commit_sha'))[:8]}`)
- **Target Dependency:** `{synth.get('target_dependency', {}).get('name')}` (`{synth.get('target_dependency', {}).get('installed_version')}`)
- **Proposed Action:** `{synth.get('migration_proposal', {}).get('proposed_action')}` $\\rightarrow$ `{synth.get('migration_proposal', {}).get('replacement_package')}`
- **Verification Verdict:** **{synth.get('verification', {}).get('verdict')}**

## 1. Observed Evidence
{chr(10).join('- ' + r.get('evidence', '') for r in synth.get('risk_evidence', []))}

## 2. Usage Locations
{chr(10).join('- `' + u.get('file_path', '') + ':' + str(u.get('line_numbers', [])) + '` — symbol: `' + u.get('ast_symbol', '') + '`' for u in synth.get('usage_locations', []))}

## 3. Gemma Recommendation
{synth.get('migration_proposal', {}).get('rationale')}

## 4. Verification Verdict Scope
{synth.get('verification', {}).get('verdict_scope_explanation')}
"""
                    self.send_download(md_content.encode("utf-8"), raw_filename, "text/markdown; charset=utf-8")
                    return
                else:
                    payload = json.dumps(synth, indent=2).encode("utf-8")
                    self.send_download(payload, raw_filename, "application/json; charset=utf-8")
                    return

            # Production capsule requested by filename
            capsules_info = api.get_capsules(project_id=project)
            prod_list = capsules_info.get("production_capsules", [])
            selected = None
            if cid:
                for c in prod_list:
                    if c.get("capsule_id") == cid:
                        selected = c
                        break
            if not selected and cid:
                for other_pid in ["swasthyavaani", "linkwatch"]:
                    if other_pid != project:
                        other_info = api.get_capsules(project_id=other_pid)
                        for c in other_info.get("production_capsules", []):
                            if c.get("capsule_id") == cid:
                                selected = c
                                project = other_pid
                                break
                    if selected:
                        break
            if not selected and prod_list:
                selected = prod_list[0]
            if not selected:
                self.send_error(HTTPStatus.NOT_FOUND, "No production exit capsule found")
                return

            prod_cap = selected.get("full_json", {})
            actual_cid = selected.get("capsule_id", cid)
            filename = f"{actual_cid}.md" if fmt == "markdown" else f"{actual_cid}.json"

            if fmt == "markdown":
                repo_dict = prod_cap.get("repository", {})
                repo_url = repo_dict.get("url", "https://github.com/rishrek/LinkWatch" if project == "linkwatch" else "https://github.com/SwasthyaVaani/backend")
                commit_sha = str(repo_dict.get("commit_sha", "HEAD"))[:8]
                target_dep = selected.get("target_dependency", "Dependencies")
                proposed_act = selected.get("proposed_action", "UPGRADE")
                replacement = selected.get("replacement_package", "Target")
                status = selected.get("status", "VERIFIED_SUCCESS")
                generated_at = selected.get("generated_at", "")
                verdict_scope = selected.get("verdict_scope", "")
                telemetry = json.dumps(prod_cap.get("verification", {}), indent=2)

                md_content = f"""# Production Dependency Exit Capsule: {target_dep}

> **Certified Production Capsule** | Schema: `exitguard.capsule_schema.DependencyExitCapsule` (v1.0.0)

- **Capsule ID:** `{actual_cid}`
- **Repository:** `{repo_url}` (`{commit_sha}`)
- **Target Dependency:** `{target_dep}`
- **Proposed Action:** `{proposed_act}` $\\rightarrow$ `{replacement}`
- **Verification Verdict:** **{status}**
- **Generated At:** `{generated_at}`

## 1. Verification Scope & Certification
{verdict_scope}

## 2. Test Execution Telemetry
```json
{telemetry}
```
"""
                self.send_download(md_content.encode("utf-8"), filename, "text/markdown; charset=utf-8")
                return
            else:
                payload = json.dumps(prod_cap, indent=2).encode("utf-8")
                self.send_download(payload, filename, "application/json; charset=utf-8")
                return

        if path == "/api/capsules/production/export":
            fmt = query.get("format", ["json"])[0]
            capsule_id_param = query.get("capsule_id", [None])[0]
            capsules_info = api.get_capsules(project_id=project)
            prod_list = capsules_info.get("production_capsules", [])
            if not prod_list:
                self.send_error(HTTPStatus.NOT_FOUND, "No production exit capsule certified for this project")
                return

            selected = None
            if capsule_id_param:
                for c in prod_list:
                    if c.get("capsule_id") == capsule_id_param:
                        selected = c
                        break
            if not selected:
                selected = prod_list[0]

            prod_cap = selected.get("full_json", {})
            cid = selected.get("capsule_id", "PRODUCTION_CAPSULE")
            filename = f"{cid}.md" if fmt == "markdown" else f"{cid}.json"

            if fmt == "markdown":
                repo_dict = prod_cap.get("repository", {})
                repo_url = repo_dict.get("url", "https://github.com/rishrek/LinkWatch" if project == "linkwatch" else "https://github.com/SwasthyaVaani/backend")
                commit_sha = str(repo_dict.get("commit_sha", "HEAD"))[:8]
                target_dep = selected.get("target_dependency", "Dependencies")
                proposed_act = selected.get("proposed_action", "UPGRADE")
                replacement = selected.get("replacement_package", "Target")
                status = selected.get("status", "VERIFIED_SUCCESS")
                generated_at = selected.get("generated_at", "")
                verdict_scope = selected.get("verdict_scope", "")
                telemetry = json.dumps(prod_cap.get("verification", {}), indent=2)

                md_content = f"""# Production Dependency Exit Capsule: {target_dep}

> **Certified Production Capsule** | Schema: `exitguard.capsule_schema.DependencyExitCapsule` (v1.0.0)

- **Capsule ID:** `{cid}`
- **Repository:** `{repo_url}` (`{commit_sha}`)
- **Target Dependency:** `{target_dep}`
- **Proposed Action:** `{proposed_act}` $\\rightarrow$ `{replacement}`
- **Verification Verdict:** **{status}**
- **Generated At:** `{generated_at}`

## 1. Verification Scope & Certification
{verdict_scope}

## 2. Test Execution Telemetry
```json
{telemetry}
```
"""
                self.send_download(md_content.encode("utf-8"), filename, "text/markdown; charset=utf-8")
                return
            else:
                payload = json.dumps(prod_cap, indent=2).encode("utf-8")
                self.send_download(payload, filename, "application/json; charset=utf-8")
                return

        if path == "/api/capsules/synthetic/export":
            fmt = query.get("format", ["json"])[0]
            synth = api.get_synthetic_capsule()
            if not synth:
                self.send_error(HTTPStatus.NOT_FOUND, "Synthetic capsule fixture not found")
                return

            if fmt == "markdown":
                md_content = f"""# Dependency Exit Capsule: {synth.get('target_dependency', {}).get('name')}

> **Notice:** THIS IS A SYNTHETIC TEST FIXTURE FOR SCHEMA VALIDATION ONLY.

- **Capsule ID:** `{synth.get('capsule_id')}`
- **Repository:** `{synth.get('repository', {}).get('url')}` (`{str(synth.get('repository', {}).get('commit_sha'))[:8]}`)
- **Target Dependency:** `{synth.get('target_dependency', {}).get('name')}` (`{synth.get('target_dependency', {}).get('installed_version')}`)
- **Proposed Action:** `{synth.get('migration_proposal', {}).get('proposed_action')}` $\\rightarrow$ `{synth.get('migration_proposal', {}).get('replacement_package')}`
- **Verification Verdict:** **{synth.get('verification', {}).get('verdict')}**

## 1. Observed Evidence
{chr(10).join('- ' + r.get('evidence', '') for r in synth.get('risk_evidence', []))}

## 2. Usage Locations
{chr(10).join('- `' + u.get('file_path', '') + ':' + str(u.get('line_numbers', [])) + '` — symbol: `' + u.get('ast_symbol', '') + '`' for u in synth.get('usage_locations', []))}

## 3. Gemma Recommendation
{synth.get('migration_proposal', {}).get('rationale')}

## 4. Verification Verdict Scope
{synth.get('verification', {}).get('verdict_scope_explanation')}
"""
                self.send_download(md_content.encode("utf-8"), "SYNTHETIC_EXIT_CAPSULE.md", "text/markdown; charset=utf-8")
                return
            else:
                payload = json.dumps(synth, indent=2).encode("utf-8")
                self.send_download(payload, "synthetic_exit_capsule.json", "application/json; charset=utf-8")
                return

        if path == "/api/settings":
            self.send_json(api.get_settings(project_id=project))
            return

        # Static Assets
        if path in ("/", "/index.html"):
            self.send_file(STATIC_DIR / "index.html", "text/html; charset=utf-8")
            return

        if path == "/styles.css":
            self.send_file(STATIC_DIR / "styles.css", "text/css; charset=utf-8")
            return

        if path == "/app.js":
            self.send_file(STATIC_DIR / "app.js", "application/javascript; charset=utf-8")
            return

        # Check if asset exists in static directory
        relative_path = path.lstrip("/")
        potential_file = STATIC_DIR / relative_path
        if potential_file.exists() and potential_file.is_file():
            mime_type, _ = mimetypes.guess_type(str(potential_file))
            self.send_file(potential_file, mime_type or "application/octet-stream")
            return

        self.send_error(HTTPStatus.NOT_FOUND, f"Resource {path} not found")

    def do_POST(self) -> None:
        """Route POST requests (e.g. triggering repository analysis or test execution)."""
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)

        # Parse optional JSON body
        content_len = int(self.headers.get("Content-Length", 0))
        body = {}
        if content_len > 0:
            try:
                raw_body = self.rfile.read(content_len).decode("utf-8")
                body = json.loads(raw_body)
            except Exception:
                body = {}

        project = body.get("project") or query.get("project", ["linkwatch"])[0]

        if parsed.path == "/api/run-tests":
            res = api.run_project_tests(project_id=project)
            self.send_json(res)
            return

        if parsed.path == "/api/analyze":
            res = api.run_project_analysis(project_id=project)
            self.send_json(res)
            return

        self.send_error(HTTPStatus.NOT_FOUND, f"Endpoint {parsed.path} not found")

    def log_message(self, format: str, *args) -> None:
        """Suppress noisy request logging unless error."""
        if args and str(args[1]) in ("404", "500"):
            sys.stderr.write(f"[ResilifyUI Error] {args[0]} -> {args[1]}\n")


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """Check if a network port is already in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((host, port)) == 0


def find_available_port(start_port: int = 8000, max_attempts: int = 20) -> int:
    """Find the first available port starting from start_port."""
    for port in range(start_port, start_port + max_attempts):
        if not is_port_in_use(port):
            return port
    return start_port


def start_server(host: str = "127.0.0.1", port: int = 8000) -> ThreadingHTTPServer:
    """Start and run the Resilify Developer Workstation HTTP server."""
    chosen_port = find_available_port(port)
    server = ThreadingHTTPServer((host, chosen_port), ResilifyUIHandler)
    url = f"http://{host}:{chosen_port}"
    print(f"Resilify Developer Workstation running at: {url}")
    print("Press Ctrl+C to stop.")
    return server


def main() -> None:
    """CLI entrypoint for running the Resilify UI."""
    parser = argparse.ArgumentParser(description="Start the Resilify UI Workstation Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default: 8000)")
    args = parser.parse_args()

    server = start_server(host=args.host, port=args.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down Resilify UI server.")
        server.server_close()


if __name__ == "__main__":
    main()
