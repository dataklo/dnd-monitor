# DND Monitor für Snom D385

Dieses Projekt stellt einen kleinen Webserver bereit, der die Action-URLs von Snom-Telefonen verarbeitet und auf einer Dashboard-Seite als Kacheln visualisiert.

## Funktionen

- Endpunkte für Snom-Actions:
  - `/status/dnd-on?mac=<MAC>`
  - `/status/dnd-off?mac=<MAC>`
  - `/status/connected?mac=<MAC>`
  - `/status/disconnected?mac=<MAC>`
- Neue MAC-Adressen werden automatisch als neues Telefon angelegt.
- Anzeige-Logik:
  - **Grün**: nicht DND und nicht im Gespräch
  - **Gelb**: im Gespräch (hat Vorrang, auch wenn DND aktiv ist)
  - **Rot**: DND aktiv und nicht im Gespräch
- Schwarzer Seitenhintergrund.
- 4 Kacheln pro Reihe (responsive bei kleinen Displays).
- Namensauflösung über Konfigurationsdatei (`config/users.json`), sonst Anzeige der MAC.

## Komplett-Installation auf Ubuntu 25.04 minimal (Proxmox CT)

> Als root oder mit `sudo -i` ausführen.

```bash
apt update
apt install -y git
cd /opt
git clone <DEIN-REPO-URL> dnd-monitor
cd dnd-monitor
./install.sh
```

### Enthaltene Pakete durch Install-Skript

- `python3`
- `python3-venv`
- `python3-pip`
- `nano`
- `htop`
- `git`
- `curl`

## Konfiguration Namen

Datei anpassen:

```bash
nano /opt/dnd-monitor/config/users.json
```

Format:

```json
{
  "users": {
    "00041393C660": "Empfang",
    "00041393C661": "Büro 1"
  }
}
```

## Snom Action URLs

Im Snom-Provisioning (oder pro Telefon) setzen:

```xml
<action_dnd_on_url perm="R">http://<SERVER-IP>:5000/status/dnd-on?mac=$mac</action_dnd_on_url>
<action_dnd_off_url perm="R">http://<SERVER-IP>:5000/status/dnd-off?mac=$mac</action_dnd_off_url>
<action_connected_url perm="R">http://<SERVER-IP>:5000/status/connected?mac=$mac</action_connected_url>
<action_disconnected_url perm="R">http://<SERVER-IP>:5000/status/disconnected?mac=$mac</action_disconnected_url>
```

## Service-Verwaltung

```bash
systemctl status dnd-monitor
systemctl restart dnd-monitor
journalctl -u dnd-monitor -f
```

## Tablet-Ansicht

Einfach `http://<SERVER-IP>:5000` im Browser öffnen und ggf. als Vollbild/PWA-Kioskmodus verwenden.
