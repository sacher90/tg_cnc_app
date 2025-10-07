"""Administration helpers for managing authorised Telegram users."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List

USERS_PATH = Path("db/users.json")
HISTORY_PATH = Path("db/history.json")


def _load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError:
        return default
    return data


def _save_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def verify_admin_password(password: str) -> bool:
    """Check password against environment variable with default fallback."""
    expected = os.environ.get("ADMIN_PASSWORD", "admin123")
    return password == expected


def get_users() -> List[Dict[str, str]]:
    data = _load_json(USERS_PATH, [])
    return data if isinstance(data, list) else []


def save_users(users: List[Dict[str, str]]) -> None:
    _save_json(USERS_PATH, users)


def add_user(user_id: int, full_name: str) -> Dict[str, str]:
    users = get_users()
    if any(str(u.get("id")) == str(user_id) for u in users):
        raise ValueError("Пользователь уже существует")
    entry = {"id": str(user_id), "name": full_name or "Без имени"}
    users.append(entry)
    save_users(users)
    return entry


def delete_user(user_id: int) -> None:
    users = get_users()
    filtered = [u for u in users if str(u.get("id")) != str(user_id)]
    save_users(filtered)


def is_user_authorised(user_id: int) -> bool:
    users = get_users()
    return any(str(u.get("id")) == str(user_id) for u in users)


def append_history(entry: Dict[str, str]) -> None:
    history = _load_json(HISTORY_PATH, [])
    if not isinstance(history, list):
        history = []
    history.append(entry)
    _save_json(HISTORY_PATH, history)


def get_history() -> List[Dict[str, str]]:
    history = _load_json(HISTORY_PATH, [])
    return history if isinstance(history, list) else []
