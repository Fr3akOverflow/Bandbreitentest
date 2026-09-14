# Bandbreitentest

Eine leichte Python-Webanwendung zur Messung und Visualisierung von Netzwerkbandbreite. Das Projekt bietet ein Browser-Interface zur Steuerung des Hintergrund-Workers, Konfiguration von Intervallen und Darstellung von Ping-, Download- und Upload-Werten.

## Funktionen

- Weboberfläche mit Status, Konfiguration, Diagramm und Datenansicht
- Periodischer Ping-Test
- Periodischer Ookla Speedtest via CLI
- Speicherung der Messdaten in `data.json`
- Download- und Löschfunktion für Messdaten
- Systemd-Services für Worker und Webinterface

## Technik

- Python 3
- Flask Webserver
- Chart.js für Diagramme im Browser
- JSON-basierte Konfiguration
- Systemd-Integration für automatische Ausführung

## Installation

1. `install.sh` mit Root-Rechten oder via sudo ausführen:

```bash
sudo bash install.sh
```

Der Installer legt den Systembenutzer `bandbreitentest` an, installiert das Projekt nach `/home/bandbreitentest/Bandbreitentest`, richtet ein Python-Virtualenv ein, installiert Flask, lädt die Ookla Speedtest-CLI, erstellt `config.json` und legt zwei systemd-Services an.

Die Deinstallation erfolgt mit Root-Rechten über `uninstall.sh` und entfernt Benutzer, Projektdaten und Service-Dateien vollständig.

## Nutzung

- Webinterface: http://<IP>:8080
- Login: `admin` / `admin` (Passwort direkt nach dem ersten Login im Tab "Passwort" ändern!)
- Start/Stop `bandbreite-worker.service` und `bandbreite-app.service` via `systemctl`
- Einstellungen in der Weboberfläche anpassen
- Messdaten anzeigen, herunterladen oder löschen

## Konfiguration

Die Datei `config.json` enthält:

- `ping_interval`: Intervall für Ping-Tests in Sekunden
- `speedtest_interval`: Intervall für Speedtests in Sekunden

## Projektdateien

- `app.py`: Flask-basierte Webanwendung und API
- `worker.py`: Hintergrundprozess für Ping- und Speedtest-Messungen
- `config.json`: Konfiguration
- `data.json`: Messdaten
- `install.sh`: Installationsskript
- `uninstall.sh`: Deinstallationsskript

## Hinweise

- Alle benötigten Komponenten (Python, Flask, Ookla Speedtest-CLI, Ping-Support) werden vom Installationsskript automatisch installiert und konfiguriert.
- Die Dienste laufen als Systembenutzer `bandbreitentest`, die Installation muss aber mit Root-Rechten ausgeführt werden.
