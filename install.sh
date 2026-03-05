#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/dnd-monitor"
VENV_DIR="$APP_DIR/.venv"
SERVICE_FILE="/etc/systemd/system/dnd-monitor.service"

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

echo "[5/6] systemd-Service erstellen ..."
cat > "$SERVICE_FILE" <<EOS
[Unit]
Description=DND Monitor Webservice
After=network.target

[Service]
Type=simple
WorkingDirectory=$APP_DIR
ExecStart=$VENV_DIR/bin/gunicorn -w 2 -b 0.0.0.0:5000 app:app
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
Status prüfen: systemctl status dnd-monitor --no-pager

MSG
