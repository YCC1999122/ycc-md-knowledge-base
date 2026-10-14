"""REST interface test: start server in thread, hit every endpoint."""
import json
import sys
import threading
import time
import urllib.request

sys.path.insert(0, ".")
import os
os.environ.setdefault("HF_HUB_OFFLINE", "1")

from app.core import db, paths, server  # noqa: E402

lib = paths.LIBRARIES_DIR / paths.DEFAULT_LIBRARY
PORT = 8765

t = threading.Thread(
    target=server.serve, args=(lib,), kwargs={"host": "127.0.0.1", "port": PORT}, daemon=True)
t.start()
time.sleep(1.0)

BASE = f"http://127.0.0.1:{PORT}"


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=30) as r:
        return r.status, r.headers.get("Content-Type", ""), r.read()


# 1. health
code, ct, body = get("/health")
print("1) /health:", code, json.loads(body))

# 2. search (hybrid)
code, _, body = get("/search?q=" + urllib.request.quote("门禁") + "&limit=3")
data = json.loads(body)
print("2) /search 门禁:", code, "count=", data["count"],
      "->", [r["title"] for r in data["results"]])

# 3. note detail (use first search hit)
nid = data["results"][0]["note_id"]
code, _, body = get("/notes/" + nid)
note = json.loads(body)
print("3) /notes/<id>:", code, note["title"], "| tags:", note["tags"], "| len(content):", len(note["content"]))

# 4. index.md
code, ct, body = get("/index.md")
print("4) /index.md:", code, ct, len(body), "bytes")

# 5. llms.txt
code, ct, body = get("/llms.txt")
print("5) /llms.txt:", code, ct, len(body), "bytes")

# 6. 404s
try:
    get("/notes/not-exist")
    print("6) FAIL: expected 404")
except urllib.error.HTTPError as e:
    print("6) /notes/not-exist ->", e.code)
try:
    get("/whatever")
    print("7) FAIL: expected 404")
except urllib.error.HTTPError as e:
    print("7) /whatever ->", e.code)

print("REST TEST OK")
