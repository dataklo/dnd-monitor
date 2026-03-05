#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/dnd-monitor"
VENV_DIR="$APP_DIR/.venv"
SERVICE_FILE="/etc/systemd/system/dnd-monitor.service"

if [[ "$EUID" -ne 0 ]]; then
  echo "Bitte als root ausführen (sudo)."
  exit 1
fi

apt update
apt install -y python3 python3-venv python3-pip nano htop git curl

mkdir -p "$APP_DIR"
rsync -a --delete ./ "$APP_DIR"/

python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install -r "$APP_DIR/requirements.txt"

if [[ ! -f "$APP_DIR/config/users.json" ]]; then
  cp "$APP_DIR/config/users.example.json" "$APP_DIR/config/users.json"
fi

cat > "$SERVICE_FILE" <<EOF
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
EOF

systemctl daemon-reload
systemctl enable --now dnd-monitor.service
systemctl status --no-pager dnd-monitor.service

echo "Fertig. Weboberfläche: http://<CT-IP>:5000"
