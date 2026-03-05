from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from flask import Flask, jsonify, render_template, request

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
STATUS_FILE = DATA_DIR / "phones.json"
DEFAULT_CONFIG_FILE = Path("/opt/dnd-monitor/config/users.json")
CONFIG_FILE = (
    DEFAULT_CONFIG_FILE
    if DEFAULT_CONFIG_FILE.exists() or DEFAULT_CONFIG_FILE.parent.exists()
    else BASE_DIR / "config" / "users.json"
)

app = Flask(__name__)
state_lock = Lock()


EVENT_MAP = {
    "dnd-on": {"dnd": True},
    "dnd-off": {"dnd": False},
    "connected": {"connected": True},
    "disconnected": {"connected": False},
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STATUS_FILE.touch(exist_ok=True)
    if STATUS_FILE.stat().st_size == 0:
        STATUS_FILE.write_text("{}", encoding="utf-8")


ensure_dirs()


def load_statuses() -> dict[str, dict]:
    try:
        return json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, FileNotFoundError):
        return {}


def save_statuses(statuses: dict[str, dict]) -> None:
    STATUS_FILE.write_text(
        json.dumps(statuses, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )


def load_user_config() -> dict[str, dict]:
    if not CONFIG_FILE.exists():
        return {}

    try:
        raw = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}

    users = raw.get("users", {})
    if not isinstance(users, dict):
        return {}

    parsed_users: dict[str, dict] = {}
    for mac_raw, value in users.items():
        mac = str(mac_raw).upper()

        if isinstance(value, dict):
            name = str(value.get("name") or mac)
            order = value.get("id")
        else:
            name = str(value)
            order = None

        parsed_users[mac] = {
            "name": name,
            "id": order if isinstance(order, int) else None,
        }

    return parsed_users


def save_user_config(users: dict[str, dict]) -> None:
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "users": {
            mac: {"name": entry.get("name", mac), "id": entry.get("id")}
            for mac, entry in sorted(users.items())
        }
    }
    CONFIG_FILE.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )


def next_free_user_id(users: dict[str, dict], start: int = 101) -> int:
    used_ids = {
        entry.get("id")
        for entry in users.values()
        if isinstance(entry.get("id"), int)
    }
    next_id = start
    while next_id in used_ids:
        next_id += 1
    return next_id


def ensure_user(mac: str, users: dict[str, dict]) -> dict:
    if mac not in users:
        users[mac] = {
            "name": mac,
            "id": next_free_user_id(users),
        }
        save_user_config(users)

    return users[mac]


def normalize_mac(mac: str) -> str:
    return mac.strip().upper()


def get_display_name(mac: str, user_config: dict[str, dict]) -> str:
    return user_config.get(mac, {}).get("name", mac)


def upsert_phone(statuses: dict[str, dict], mac: str) -> dict:
    if mac not in statuses:
        statuses[mac] = {
            "mac": mac,
            "dnd": False,
            "connected": False,
            "last_event": "created",
            "updated_at": utc_now_iso(),
        }

    return statuses[mac]


def tile_status(phone: dict) -> str:
    if phone.get("connected"):
        return "busy"
    if phone.get("dnd"):
        return "dnd"
    return "free"


@app.get("/")
def dashboard():
    return render_template("index.html")


@app.get("/api/phones")
def phones_api():
    user_config = load_user_config()
    with state_lock:
        statuses = load_statuses()

    sorted_macs = sorted(
        statuses.keys(),
        key=lambda mac: (
            user_config.get(mac, {}).get("id")
            if isinstance(user_config.get(mac, {}).get("id"), int)
            else 1_000_000,
            get_display_name(mac, user_config).lower(),
            mac,
        ),
    )

    phones = []
    for mac in sorted_macs:
        phone = statuses[mac]
        phones.append(
            {
                **phone,
                "display_name": get_display_name(mac, user_config),
                "status": tile_status(phone),
            }
        )

    return jsonify({"phones": phones, "updated_at": utc_now_iso()})


@app.get("/status/<event>")
def update_status(event: str):
    change = EVENT_MAP.get(event)
    if change is None:
        return jsonify({"ok": False, "error": "unknown event"}), 404

    mac_raw = request.args.get("mac", "")
    if not mac_raw:
        return jsonify({"ok": False, "error": "missing mac"}), 400

    mac = normalize_mac(mac_raw)

    with state_lock:
        user_config = load_user_config()
        ensure_user(mac, user_config)
        statuses = load_statuses()
        phone = upsert_phone(statuses, mac)
        phone.update(change)
        phone["last_event"] = event
        phone["updated_at"] = utc_now_iso()
        save_statuses(statuses)

    return jsonify({"ok": True, "mac": mac, "event": event, "state": phone})


if __name__ == "__main__":
    ensure_dirs()
    app.run(host="0.0.0.0", port=5000)
