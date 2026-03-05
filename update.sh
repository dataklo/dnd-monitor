#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/dnd-monitor"

if [[ "$EUID" -ne 0 ]]; then
  echo "Bitte als root ausführen (sudo)."
  exit 1
fi

if [[ ! -d "$APP_DIR/.git" ]]; then
  echo "Fehler: $APP_DIR ist kein Git-Checkout."
  echo "Bitte Repository zuerst korrekt nach /opt/dnd-monitor klonen."
  exit 1
fi

echo "Update startet ..."
cd "$APP_DIR"
git pull --ff-only
./install.sh

echo "Update abgeschlossen."
