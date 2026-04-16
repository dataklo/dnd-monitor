# DND Monitor für Snom D385

Ein einfaches Dashboard, das den Telefonstatus deiner Snom-Telefone als große Kacheln im Browser anzeigt.
Perfekt für Empfang, Backoffice oder ein Wand-Tablet.

- 🟩 **Grün** = frei
- 🟨 **Gelb** = im Gespräch
- 🟥 **Rot** = DND aktiv

![Beispielansicht DND Monitor](docs/dashboard-example.svg)

---

## Inhalt

1. [Was macht das Projekt?](#was-macht-das-projekt)
2. [Voraussetzungen](#voraussetzungen)
3. [Schnellstart (interaktiv)](#schnellstart-interaktiv)
4. [Was installiert das Skript genau?](#was-installiert-das-skript-genau)
5. [Weboberflächen und Login](#weboberflächen-und-login)
6. [Telefone benennen und sortieren](#telefone-benennen-und-sortieren)
7. [Snom Action-URLs](#snom-action-urls)
8. [DND per Klick auf Kachel](#dnd-per-klick-auf-kachel)
9. [Betrieb im Alltag](#betrieb-im-alltag)
10. [Update](#update)
11. [Deinstallation](#deinstallation)
12. [Tipps für Dauerbetrieb (Tablet/Monitor)](#tipps-für-dauerbetrieb-tabletmonitor)
13. [Fehlerbehebung](#fehlerbehebung)

---

## Was macht das Projekt?

Der DND Monitor nimmt Statusmeldungen von Snom-Telefonen entgegen und zeigt sie live als Dashboard an.

Zusätzlich gibt es eine zweite, schreibgeschützte Ansicht für Kollegen (mit Login), die nur den Status sehen sollen.

---

## Voraussetzungen

- Ubuntu / Debian (auch als Proxmox-Container möglich)
- Internetzugang auf dem Server
- Root-Zugriff oder Benutzer mit `sudo`
- Snom-Telefone, die Action-URLs senden dürfen

---

## Schnellstart (interaktiv)

> Die Installation ist jetzt interaktiv und fragt dich Schritt für Schritt.

### 1) Als root anmelden

```bash
sudo -i
```

### 2) Git installieren (falls noch nicht vorhanden)

```bash
apt update
apt install -y git
```

### 3) Repository klonen

```bash
cd /opt
git clone https://github.com/dataklo/dnd-monitor.git dnd-monitor
cd dnd-monitor
```

### 4) Interaktive Installation starten

```bash
./install.sh
```

Während der Installation fragt das Skript z. B.:

- ob die Installation gestartet werden soll
- ob am Ende direkt der Service-Status angezeigt werden soll

Am Ende bekommst du eine kompakte Zusammenfassung mit URLs und den nächsten Befehlen.

---

## Was installiert das Skript genau?

Das Installationsskript führt folgende Aufgaben aus:

1. installiert Systempakete
2. kopiert das Projekt nach `/opt/dnd-monitor`
3. baut eine Python-Virtualenv
4. installiert Python-Abhängigkeiten
5. erstellt Standard-Konfigurationen (falls nicht vorhanden)
6. schreibt den systemd-Service
7. aktiviert und startet den Service

Installierte Pakete:

- `python3`
- `python3-venv`
- `python3-pip`
- `rsync`
- `git`
- `curl`
- `nano` ✅
- `htop` ✅

Damit sind **nano** (Editor) und **htop** (Systemmonitor) direkt mit dabei.

---

## Weboberflächen und Login

Nach erfolgreicher Installation:

- Hauptoberfläche: `http://<SERVER-IP>:5000`
- Nur-Anzeige (mit Login): `http://<SERVER-IP>:5001`

Beispiel:

```text
http://192.168.1.20:5000
```

Die Read-Only-Zugangsdaten werden in dieser Datei abgelegt:

```text
/opt/dnd-monitor/config/readonly-auth.env
```

Anzeigen mit:

```bash
cat /opt/dnd-monitor/config/readonly-auth.env
```

Hinweis:
Die Event/API-Endpunkte (`/status/...` und `/api/...`) bleiben erreichbar,
damit Telefone weiterhin Status senden können.

---

## Telefone benennen und sortieren

Konfigurationsdatei öffnen:

```bash
nano /opt/dnd-monitor/config/users.json
```

Beispiel:

```json
{
  "users": {
    "00041393C660": {
      "name": "Empfang",
      "id": 1
    },
    "00041393C661": {
      "name": "Büro 1",
      "id": 2
    }
  }
}
```

### Bedeutung der `id`

- `1` = links oben
- danach fortlaufend in Leserichtung
- fehlende IDs werden einfach übersprungen

Unbekannte MAC-Adressen werden automatisch in `users.json` angelegt
und bekommen die nächste freie ID (ab `101`).

Danach neu starten:

```bash
systemctl restart dnd-monitor
```

---

## Snom Action-URLs

Diese URLs in der Snom-Konfiguration hinterlegen:

```xml
<action_dnd_on_url perm="R">http://<SERVER-IP>:5000/status/dnd-on?mac=$mac</action_dnd_on_url>
<action_dnd_off_url perm="R">http://<SERVER-IP>:5000/status/dnd-off?mac=$mac</action_dnd_off_url>
<action_connected_url perm="R">http://<SERVER-IP>:5000/status/connected?mac=$mac</action_connected_url>
<action_disconnected_url perm="R">http://<SERVER-IP>:5000/status/disconnected?mac=$mac</action_disconnected_url>
```

Bei jedem Event wird die Quell-IP geprüft und nur bei Änderung gespeichert.

---

## DND per Klick auf Kachel

Ein Klick auf den **Namen** einer Kachel kann DND direkt am Telefon schalten.

Server-seitig wird dafür ein Request in dieser Form ausgelöst:

```bash
curl --digest -u root:PASSWORT "http://<telefon-ip>/command.htm?key=DND"
```

Schutzmechanismen:

- Sicherheitsabfrage vor dem Auslösen
- Cooldown (5 Sekunden) pro Telefon gegen Doppelklicks

---

## Betrieb im Alltag

Service-Status:

```bash
systemctl status dnd-monitor --no-pager
```

Neustarten:

```bash
systemctl restart dnd-monitor
```

Logs live:

```bash
journalctl -u dnd-monitor -f
```

Hilfreiche Admin-Tools:

```bash
nano /opt/dnd-monitor/config/users.json
htop
```

---

## Update

```bash
cd /opt/dnd-monitor
./update.sh
```

Ablauf:

- `git pull`
- `install.sh` erneut ausführen
- Service mit neuer Version starten

---

## Deinstallation

```bash
cd /opt/dnd-monitor
./uninstall.sh
```

Dabei werden Service und Projektverzeichnis entfernt.

---

## Tipps für Dauerbetrieb (Tablet/Monitor)

- Browser im Vollbild
- Bildschirm-Sperre deaktivieren
- Dashboard als Startseite setzen
- Optional: Kiosk-Modus verwenden

---

## Fehlerbehebung

### Service startet nicht

```bash
journalctl -u dnd-monitor -n 200 --no-pager
```

### Port 5000/5001 nicht erreichbar

- Firewall prüfen
- Container/VM-Netzwerk prüfen
- Mit `ss -tulpen | grep 500` kontrollieren, ob Prozesse lauschen

### Login für Port 5001 vergessen

```bash
cat /opt/dnd-monitor/config/readonly-auth.env
```

---

Viel Erfolg beim Einrichten 👋
