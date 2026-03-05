from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from flask import Flask, jsonify, render_template, request

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
STATUS_FILE = DATA_DIR / "phones.json"
CONFIG_FILE = BASE_DIR / "config" / "users.json"

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


def load_user_map() -> dict[str, str]:
    if not CONFIG_FILE.exists():
        return {}

    try:
        raw = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}

    users = raw.get("users", {})
    if not isinstance(users, dict):
        return {}

    return {str(mac).upper(): str(name) for mac, name in users.items()}


def normalize_mac(mac: str) -> str:
    return mac.strip().upper()


def get_display_name(mac: str, user_map: dict[str, str]) -> str:
    return user_map.get(mac, mac)


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
    user_map = load_user_map()
    with state_lock:
        statuses = load_statuses()

    phones = []
    for mac in sorted(statuses.keys()):
        phone = statuses[mac]
        phones.append(
            {
                **phone,
                "display_name": get_display_name(mac, user_map),
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
