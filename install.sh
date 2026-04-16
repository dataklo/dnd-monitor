#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/dnd-monitor"
VENV_DIR="$APP_DIR/.venv"
SERVICE_FILE="/etc/systemd/system/dnd-monitor.service"
READONLY_AUTH_FILE="$APP_DIR/config/readonly-auth.env"

if [[ "$EUID" -ne 0 ]]; then
  echo "Bitte als root ausführen (sudo)."
  exit 1
fi

ask_yes_no() {
  local prompt="$1"
  local default="${2:-Y}"
  local answer=""

  while true; do
    if [[ "$default" == "Y" ]]; then
      read -r -p "$prompt [Y/n]: " answer
      answer="${answer:-Y}"
    else
      read -r -p "$prompt [y/N]: " answer
      answer="${answer:-N}"
    fi

    case "${answer,,}" in
      y|yes) return 0 ;;
      n|no) return 1 ;;
      *) echo "Bitte y oder n eingeben." ;;
    esac
  done
}

echo "========================================"
echo " DND Monitor - interaktive Installation"
echo "========================================"
echo

echo "Zielverzeichnis: $APP_DIR"
echo "Systemd-Service: dnd-monitor.service"
echo

if ! ask_yes_no "Installation jetzt starten?" "Y"; then
  echo "Abgebrochen."
  exit 0
fi

echo
echo "[1/7] Pakete aktualisieren und installieren ..."
apt update
apt install -y python3 python3-venv python3-pip rsync nano htop git curl

echo
echo "[2/7] Dateien nach $APP_DIR kopieren ..."
mkdir -p "$APP_DIR"
rsync -a --delete ./ "$APP_DIR"/

echo
echo "[3/7] Python-Umgebung einrichten ..."
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install -r "$APP_DIR/requirements.txt"

echo
echo "[4/7] Konfiguration prüfen ..."
if [[ ! -f "$APP_DIR/config/users.json" ]]; then
  cp "$APP_DIR/config/users.example.json" "$APP_DIR/config/users.json"
  echo "- users.json wurde aus users.example.json erstellt."
else
  echo "- users.json existiert bereits (bleibt unverändert)."
fi

if [[ ! -f "$READONLY_AUTH_FILE" ]]; then
  readonly_password="$(python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(18))
PY
)"
  cat > "$READONLY_AUTH_FILE" <<ENV
READONLY_USERNAME=monitor
READONLY_PASSWORD=$readonly_password
ENV
  chmod 600 "$READONLY_AUTH_FILE"
  echo "- Read-only Login wurde neu erstellt: $READONLY_AUTH_FILE"
else
  echo "- Read-only Login existiert bereits: $READONLY_AUTH_FILE"
fi

echo
echo "[5/7] systemd-Service schreiben ..."
cat > "$SERVICE_FILE" <<EOS
[Unit]
Description=DND Monitor Webservice
After=network.target

[Service]
Type=simple
WorkingDirectory=$APP_DIR
EnvironmentFile=-$READONLY_AUTH_FILE
ExecStart=$VENV_DIR/bin/python $APP_DIR/app.py
Restart=always
RestartSec=3
User=root
Group=root

[Install]
WantedBy=multi-user.target
EOS

echo
echo "[6/7] Service laden und aktivieren ..."
systemctl daemon-reload
systemctl enable --now dnd-monitor.service

echo
echo "[7/7] Abschluss"
if ask_yes_no "Soll der aktuelle Service-Status jetzt angezeigt werden?" "Y"; then
  systemctl status dnd-monitor --no-pager || true
fi

cat <<MSG

Installation abgeschlossen.
Weboberfläche: http://<SERVER-IP>:5000
Nur-Anzeige (mit Login): http://<SERVER-IP>:5001
Login-Datei: $READONLY_AUTH_FILE

Hilfreiche Tools wurden installiert:
- nano (Editor)
- htop (Prozess-Monitor)

Nächste Schritte:
1) users.json bearbeiten: nano $APP_DIR/config/users.json
2) Zugangsdaten prüfen: cat $READONLY_AUTH_FILE
3) Logs live ansehen: journalctl -u dnd-monitor -f

MSG
