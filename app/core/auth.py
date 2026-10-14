"""Global user accounts (offline, stored in config/users.json).

First run seeds the initial account admin / admin. Passwords are salted
SHA-256 hashes; no network, no external deps.
"""
from __future__ import annotations

import hashlib
import json
import secrets

from . import paths

USERS_FILE = paths.CONFIG_DIR / "users.json"


def _hash(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()


def _load() -> dict:
    if USERS_FILE.exists():
        return json.loads(USERS_FILE.read_text(encoding="utf-8"))
    return {}


def _save(users: dict) -> None:
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    USERS_FILE.write_text(json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8")


def ensure_default_users() -> None:
    users = _load()
    if "admin" not in users:
        salt = secrets.token_hex(8)
        users["admin"] = {"salt": salt, "hash": _hash("admin", salt), "role": "管理员"}
        _save(users)


def verify(username: str, password: str) -> bool:
    u = _load().get(username.strip())
    return bool(u) and u["hash"] == _hash(password, u["salt"])


def role(username: str) -> str:
    u = _load().get(username.strip())
    return u.get("role", "编辑") if u else "编辑"
