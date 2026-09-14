# Fehlerbehebung

Dokumentation der behobenen Fehler (2026-09-13). Änderungen betreffen `app.py`, `worker.py`, `install.sh` und die neue Datei `store.py`.

## Neue Datei: `store.py`

Zentrale, robuste JSON-Aufbewahrung. Alle Lese-/Schreibzugriffe auf `config.json` und `data.json` laufen jetzt darüber.

- Dateipfade werden aus `__file__` abgeleitet → funktionieren unabhängig vom Startverzeichnis (Fix: relative Pfade).
- `save_json` schreibt atomar: erst in eine Temp-Datei, dann `os.replace()`. Dadurch sieht ein gleichzeitiger Leser nie eine halb geschriebene Datei (Fix: paralleles Schreiben von Worker und Web-App).
- `load_json` liefert bei fehlerhafter/korrupter Datei den Default-Wert statt zu crashen (Fix: Worker überlebte kaputte `data.json` nicht).

## `worker.py`

- `load_config`, `load_data`, `save_data` durch `store.*` ersetzt, ungenutzten `os`-Import entfernt.
- Die Hauptschleife stürzt bei einer beschädigten Datei nicht mehr ab.

## `app.py`

- **Authentifizierung (neu):** HTTP Basic Auth. Beim ersten Start wird ein zufälliges Passwort generiert und in `config.json` unter `web_password` gespeichert. Nicht erreichbar ohne Login — auch Worker-Start/Stop, Daten-Löschen und Konfiguration sind geschützt. `/api/config` (GET) liefert das Passwort nicht mit. Das Passwort wird beim Start der App in der Konsole/unter `journalctl -u bandbreite-app.service -e` ausgegeben.
- **Config-Validierung:** `POST /api/config` mit leerem/unvalidem Body liefert 400 statt 500; Intervalle müssen positive Ganzzahlen sein (verhindert dauerhaft laufenden Speedtest bei 0).
- **Chart.js lokal:** statt CDN wird jetzt `static/chart.min.js` mitgeliefert und ausgeliefert (`url_for`). Kein Internetzugriff mehr nötig.
- **Zeitzonen-Fehler:** Datums- und Stundenauswahl im Diagramm gruppieren jetzt nach lokaler Zeit (`localDate()`), konsistent zu den Chart-Labels. Messungen um Mitternacht landen nicht mehr unter falschem Datum.
- **HTML-Fix:** überzähliges `</td>` in der Diagramm-Tabelle entfernt.

## `install.sh`

- `iputils-ping` wird mitinstalliert (vorher: Ping-Test lieferte auf frischen Systemen immer `None`).
- `pip install -r requirements.txt` statt ungepinntem `pip install Flask` — nutzt `Flask==3.0.2` aus `requirements.txt`.
- Speedtest-CLI: Architektur-Erkennung (`x86_64`/`aarch64`), Abbruch bei unbekannter Arch statt stillschweigendem Fehlschlag.
- Beim Kopieren wird `.git` und `__pycache__` entfernt.

## Wie testen

- Syntax: `python3 -m py_compile app.py worker.py store.py`
- Selbsttest der Datei-Ebene: `python3 -c "import store; store.save_json(store.data_path(), [{'a':1}]); assert store.load_json(store.data_path(), []) == [{'a':1}]; store.save_json(store.data_path(), []); assert store.load_json('nice-missing.txt', 'd') == 'd'"` — Fehlerfrei, wenn keine Fehlermeldung kommt.

## Bekannte Einschränkung (nicht behoben)

Das Repository enthält den eigentlichen Projektordner in einem Unterordner (`Bandbreitentest/Bandbreitentest/`). `install.sh` kopiert den kompletten Baum; `app.py`/`worker.py` liegen dadurch korrekt unter dem installierten Verzeichnis. Wer die Struktur flach haben will, verschiebt den Inhalt des Unterordners in die Repo-Wurzel.

# Optimierung für große Datensätze

Vorher lud das Webinterface **alle** Messdaten per `/api/data`, baute die Datums-/Stundenauswahl durch mehrmalige Voll-Scans und rendert jeden Punkt im Chart sowie die komplette Liste im Daten-Tab — bei vielen Tausend Einträgen hängte oder crashte das Interface.

- **Serverseitiges Downsampling:** `/api/data?start=…&end=…` filtert serverseitig auf den Zeitbereich und begrenzt die Antwort auf `MAX_CHART_POINTS` (1000) Punkte, gleichmäßig verteilt. Das Chart rendert nie mehr als 1000 Punkte.
- **Neues `/api/data/summary`:** liefert Gesamtzahl plus Datums- und Stundenlisten **in der Zeitzone des Browsers** (`?tz=` Minuten-Offset). Die Auswahl-Selectoren werden daraus gebaut — kein Voll-Scan mehr im Browser, und Auswahl bleibt über Auto-Refresh erhalten.
- **Daten-Tab gedeckelt:** zeigt nur noch die letzten 100 Messungen samt Gesamtzahl statt der kompletten Datei; der Export läuft weiterhin unbegrenzt über `/api/data/download`.
- Auto-Refresh (120 s) aktualisiert jetzt Summary + aktuellen Zeitbereich statt des gesamten Datensatzes.

Die Messdaten wachsen weiter unbegrenzt; die Oberfläche bleibt durch das Sampling unabhängig von der Dateigröße brauchbar. Wer die Datei automatisch begrenzen will (z. B. letzte 90 Tage), muss das in `worker.py` umsetzen — bewusst nicht verändert, um keine Historie zu löschen.