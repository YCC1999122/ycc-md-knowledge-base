"""Offline REST interface for AI agents (stdlib only, no extra dependency).

Endpoints:
  GET /health                  -> {"ok": true, "library": <name>}
  GET /search?q=<kw>&limit=N   -> hybrid (FTS + semantic) results
  GET /notes/<note_id>         -> note metadata + markdown content
  GET /index.md                -> INDEX.md (agent entrypoint)
  GET /llms.txt                -> llms.txt navigation

Usage:
  python -m app.core.cli serve --port 8000
"""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import db, kb, paths, retriever


def make_handler(lib: Path):
    lib = Path(lib)

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, body: bytes, ctype: str):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code: int, obj) -> None:
            self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                       "application/json; charset=utf-8")

        def do_GET(self):  # noqa: N802 - stdlib naming
            parsed = urlparse(self.path)
            route = parsed.path.rstrip("/") or "/"
            qs = parse_qs(parsed.query)

            if route == "/health":
                conn = db.connect(lib)
                name = kb.library_name(lib)
                conn.close()
                return self._json(200, {"ok": True, "library": name})

            if route == "/search":
                q = (qs.get("q", [""])[0]).strip()
                limit = int(qs.get("limit", ["10"])[0])
                if not q:
                    return self._json(400, {"error": "missing q"})
                conn = db.connect(lib)
                results = retriever.search(conn, q, max(1, min(limit, 50)))
                conn.close()
                return self._json(200, {"query": q, "count": len(results), "results": results})

            if route.startswith("/notes/"):
                note_id = route.split("/notes/", 1)[1].strip("/")
                conn = db.connect(lib)
                row = conn.execute("SELECT * FROM notes WHERE note_id=?", (note_id,)).fetchone()
                conn.close()
                if row is None:
                    return self._json(404, {"error": "note not found", "note_id": note_id})
                note = dict(row)
                note["tags"] = json.loads(note["tags"] or "[]")
                note.pop("level", None)  # 密级体系已取消，不对外暴露
                return self._json(200, note)

            if route in ("/index.md", "/index"):
                f = lib / "INDEX.md"
                if not f.exists():
                    return self._json(404, {"error": "INDEX.md not found"})
                return self._send(200, f.read_bytes(), "text/markdown; charset=utf-8")

            if route == "/llms.txt":
                f = lib / "llms.txt"
                if not f.exists():
                    return self._json(404, {"error": "llms.txt not found"})
                return self._send(200, f.read_bytes(), "text/plain; charset=utf-8")

            return self._json(404, {"error": "unknown route", "routes": [
                "/health", "/search?q=&limit=", "/notes/<note_id>", "/index.md", "/llms.txt"]})

        def log_message(self, fmt, *args):  # quiet access log
            pass

    return Handler


def serve(lib, host: str = "127.0.0.1", port: int = 8000) -> None:
    """Blocking; call in a thread for embedding into other processes."""
    server = ThreadingHTTPServer((host, port), make_handler(lib))
    print(f"知识库检索服务已启动: http://{host}:{port}  (库: {kb.library_name(Path(lib))})")
    print("接口: /health  /search?q=  /notes/<id>  /index.md  /llms.txt")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    serve(paths.LIBRARIES_DIR / paths.DEFAULT_LIBRARY)
