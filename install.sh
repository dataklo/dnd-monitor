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

echo "[1/6] Pakete installieren ..."
apt update
apt install -y python3 python3-venv python3-pip rsync nano htop git curl

echo "[2/6] Dateien nach $APP_DIR kopieren ..."
mkdir -p "$APP_DIR"
rsync -a --delete ./ "$APP_DIR"/

echo "[3/6] Python-Umgebung einrichten ..."
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install -r "$APP_DIR/requirements.txt"

echo "[4/6] Beispiel-Konfiguration anlegen (falls nötig) ..."
if [[ ! -f "$APP_DIR/config/users.json" ]]; then
  cp "$APP_DIR/config/users.example.json" "$APP_DIR/config/users.json"
fi
if [[ ! -f "$READONLY_AUTH_FILE" ]]; then
  readonly_password="$(python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(18))
PY
)"
  cat > "$READONLY_AUTH_FILE" <<EOF
READONLY_USERNAME=monitor
READONLY_PASSWORD=$readonly_password
EOF
  chmod 600 "$READONLY_AUTH_FILE"
  echo "Read-only Login gespeichert in: $READONLY_AUTH_FILE"
fi

echo "[5/6] systemd-Service erstellen ..."
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

echo "[6/6] Service starten ..."
systemctl daemon-reload
systemctl enable --now dnd-monitor.service

cat <<MSG

Installation abgeschlossen.
Weboberfläche: http://<SERVER-IP>:5000
Nur-Anzeige (mit Login): http://<SERVER-IP>:5001
Login-Datei: $READONLY_AUTH_FILE
Status prüfen: systemctl status dnd-monitor --no-pager

MSG
