#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/dnd-monitor"
SERVICE_FILE="/etc/systemd/system/dnd-monitor.service"

if [[ "$EUID" -ne 0 ]]; then
  echo "Bitte als root ausführen (sudo)."
  exit 1
fi

echo "Stoppe und entferne systemd-Service ..."
if systemctl list-unit-files | grep -q '^dnd-monitor.service'; then
  systemctl disable --now dnd-monitor.service || true
fi

rm -f "$SERVICE_FILE"
systemctl daemon-reload

if [[ -d "$APP_DIR" ]]; then
  echo "Entferne $APP_DIR ..."
  rm -rf "$APP_DIR"
fi

echo "DND Monitor wurde deinstalliert."
