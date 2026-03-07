from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPDigestAuthHandler, HTTPPasswordMgrWithDefaultRealm, build_opener

from flask import Flask, jsonify, render_template, request
from werkzeug.middleware.proxy_fix import ProxyFix

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
STATUS_FILE = DATA_DIR / "phones.json"
DEFAULT_CONFIG_FILE = Path("/opt/dnd-monitor/config/users.json")
LOCAL_CONFIG_FILE = BASE_DIR / "config" / "users.json"


def resolve_config_file() -> Path:
    if DEFAULT_CONFIG_FILE.exists():
        return DEFAULT_CONFIG_FILE
    if LOCAL_CONFIG_FILE.exists():
        return LOCAL_CONFIG_FILE
    if DEFAULT_CONFIG_FILE.parent.exists():
        return DEFAULT_CONFIG_FILE
    return LOCAL_CONFIG_FILE


CONFIG_FILE = resolve_config_file()

app = Flask(__name__)
TRUSTED_PROXY_HOPS = int(os.getenv("TRUSTED_PROXY_HOPS", "0"))
if TRUSTED_PROXY_HOPS > 0:
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=TRUSTED_PROXY_HOPS, x_host=0, x_proto=0, x_port=0, x_prefix=0)
state_lock = Lock()


EVENT_MAP = {
    "dnd-on": {"dnd": True},
    "dnd-off": {"dnd": False},
    "connected": {"connected": True},
    "disconnected": {"connected": False},
}

WEBHOOK_USER = "root"
WEBHOOK_PASSWORD = "lbs2021"
WEBHOOK_KEY = "DND"
DND_COOLDOWN_SECONDS = 5


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
    config_candidates = [CONFIG_FILE]
    fallback = LOCAL_CONFIG_FILE if CONFIG_FILE == DEFAULT_CONFIG_FILE else DEFAULT_CONFIG_FILE
    config_candidates.append(fallback)

    raw = None
    for config_file in config_candidates:
        if not config_file.exists():
            continue
        try:
            raw = json.loads(config_file.read_text(encoding="utf-8"))
            break
        except json.JSONDecodeError:
            continue

    if raw is None:
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


def request_ip() -> str | None:
    return request.remote_addr


def trigger_dnd_webhook(ip: str) -> tuple[bool, str, int | None]:
    url = f"http://{ip}/command.htm?{urlencode({'key': WEBHOOK_KEY})}"

    password_mgr = HTTPPasswordMgrWithDefaultRealm()
    password_mgr.add_password(None, url, WEBHOOK_USER, WEBHOOK_PASSWORD)
    auth_handler = HTTPDigestAuthHandler(password_mgr)
    opener = build_opener(auth_handler)

    try:
        with opener.open(url, timeout=5) as response:
            return True, "ok", getattr(response, "status", 200)
    except HTTPError as exc:
        return False, f"http_error:{exc.code}", exc.code
    except URLError as exc:
        return False, f"url_error:{exc.reason}", None


def parse_iso_datetime(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def is_in_cooldown(phone: dict, now: datetime) -> tuple[bool, int]:
    last_triggered = str(phone.get("last_dnd_trigger_at") or "").strip()
    if not last_triggered:
        return False, 0

    last_dt = parse_iso_datetime(last_triggered)
    if last_dt is None:
        return False, 0

    delta_seconds = (now - last_dt).total_seconds()
    if delta_seconds >= DND_COOLDOWN_SECONDS:
        return False, 0

    remaining = int(DND_COOLDOWN_SECONDS - delta_seconds)
    if (DND_COOLDOWN_SECONDS - delta_seconds) > remaining:
        remaining += 1

    return True, max(remaining, 1)


def tile_status(phone: dict) -> str:
    if not phone or not phone.get("updated_at"):
        return "unknown"
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

    known_macs = set(user_config.keys()) | set(statuses.keys())

    sorted_macs = sorted(
        known_macs,
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
        phone = statuses.get(mac, {})
        phones.append(
            {
                "mac": mac,
                "dnd": bool(phone.get("dnd", False)),
                "connected": bool(phone.get("connected", False)),
                "last_event": phone.get("last_event", "config-only"),
                "updated_at": phone.get("updated_at"),
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

        incoming_ip = request_ip()
        if incoming_ip and incoming_ip != str(phone.get("ip") or ""):
            phone["ip"] = incoming_ip

        phone["updated_at"] = utc_now_iso()
        save_statuses(statuses)

    return jsonify({"ok": True, "mac": mac, "event": event, "state": phone})


@app.post("/api/phones/<mac>/dnd")
def trigger_phone_dnd(mac: str):
    normalized_mac = normalize_mac(mac)
    now = datetime.now(timezone.utc)

    with state_lock:
        statuses = load_statuses()
        phone = statuses.get(normalized_mac)
        if not phone:
            return jsonify({"ok": False, "error": "unknown mac"}), 404

        ip = str(phone.get("ip") or "").strip()
        if not ip:
            return jsonify({"ok": False, "error": "missing ip for mac"}), 400

        in_cooldown, remaining_seconds = is_in_cooldown(phone, now)
        if in_cooldown:
            return (
                jsonify(
                    {
                        "ok": False,
                        "error": "cooldown active",
                        "mac": normalized_mac,
                        "ip": ip,
                        "retry_after": remaining_seconds,
                    }
                ),
                429,
            )

        phone["last_dnd_trigger_at"] = now.isoformat()
        save_statuses(statuses)

    ok, detail, status_code = trigger_dnd_webhook(ip)
    if not ok:
        return (
            jsonify({
                "ok": False,
                "error": "webhook failed",
                "detail": detail,
                "mac": normalized_mac,
                "ip": ip,
            }),
            502,
        )

    return jsonify(
        {
            "ok": True,
            "mac": normalized_mac,
            "ip": ip,
            "webhook_status": status_code,
            "cooldown_seconds": DND_COOLDOWN_SECONDS,
        }
    )


if __name__ == "__main__":
    ensure_dirs()
    app.run(host="0.0.0.0", port=5000)
