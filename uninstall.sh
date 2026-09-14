#!/bin/bash
set -e

if [ "$(id -u)" -ne 0 ]; then
    echo "Bitte als root oder mit sudo ausführen."
    exit 1
fi

echo "=== Bandbreitentest Uninstall startet ==="

USER_NAME=bandbreitentest
INSTALL_DIR="/home/$USER_NAME/Bandbreitentest"

# ---------------------------------------------
# SERVICES STOPPEN
# ---------------------------------------------
echo "[1/7] Stoppe systemd Services..."
systemctl stop bandbreite-worker.service 2>/dev/null || true
systemctl stop bandbreite-app.service 2>/dev/null || true

# ---------------------------------------------
# SERVICES DEAKTIVIEREN
# ---------------------------------------------
echo "[2/7] Deaktiviere Services..."
systemctl disable bandbreite-worker.service 2>/dev/null || true
systemctl disable bandbreite-app.service 2>/dev/null || true

# ---------------------------------------------
# SERVICE-DATEIEN ENTFERNEN
# ---------------------------------------------
echo "[3/7] Entferne Service-Dateien..."
rm -f /etc/systemd/system/bandbreite-worker.service
rm -f /etc/systemd/system/bandbreite-app.service

systemctl daemon-reload

# ---------------------------------------------
# PROJEKTORDNER LÖSCHEN
# ---------------------------------------------
echo "[4/7] Entferne Projektordner..."
rm -rf "$INSTALL_DIR"

# ---------------------------------------------
# BENUTZER ENTFERNEN
# ---------------------------------------------
echo "[5/7] Entferne Benutzer $USER_NAME..."
if id -u "$USER_NAME" >/dev/null 2>&1; then
    userdel -r "$USER_NAME" || true
fi

# ---------------------------------------------
# SPEEDTEST CLI ENTFERNEN
# ---------------------------------------------
echo "[6/7] Entferne Speedtest CLI..."
rm -f /usr/local/bin/speedtest

# ---------------------------------------------
# SUDOERS AUFRÄUMEN
# ---------------------------------------------
echo "[7/7] Entferne sudoers-Regel..."
rm -f /etc/sudoers.d/bandbreitentest

# ---------------------------------------------
# SUDOERS AUFRÄUMEN
# ---------------------------------------------
rm -f /etc/sudoers.d/bandbreitentest

echo "Deinstallation abgeschlossen."
echo "Alle Komponenten wurden entfernt."
