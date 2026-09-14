#!/bin/bash
set -e

if [ "$(id -u)" -ne 0 ]; then
    echo "Bitte als root oder mit sudo ausführen."
    exit 1
fi

echo "=== Bandbreitentest Installation startet ==="

USER_NAME=bandbreitentest
USER_HOME="/home/$USER_NAME"
INSTALL_DIR="$USER_HOME/Bandbreitentest"

# ---------------------------------------------
# SYSTEM-PAKETE
# ---------------------------------------------
echo "[1/8] System aktualisieren..."
apt update -y
apt install -y python3 python3-venv python3-pip curl wget iputils-ping
setcap cap_net_raw+ep /usr/bin/ping || true

# ---------------------------------------------
# BENUTZER ANLEGEN
# ---------------------------------------------
echo "[2/8] Benutzer $USER_NAME anlegen..."
if ! id -u "$USER_NAME" >/dev/null 2>&1; then
    useradd -m -d "$USER_HOME" -s /bin/bash "$USER_NAME"
    echo "Benutzer $USER_NAME erstellt."
else
    echo "Benutzer $USER_NAME existiert bereits."
fi

# ---------------------------------------------
# PROJEKTORDNER
# ---------------------------------------------
echo "[3/8] Projektordner anlegen..."
mkdir -p "$INSTALL_DIR"
if [ "$PWD" != "$INSTALL_DIR" ]; then
    cp -r . "$INSTALL_DIR/"
    rm -rf "$INSTALL_DIR/.git" "$INSTALL_DIR/__pycache__"
fi
chown -R "$USER_NAME:$USER_NAME" "$INSTALL_DIR"

# ---------------------------------------------
# PYTHON VENV
# ---------------------------------------------
echo "[4/8] Python venv erstellen..."
cd "$INSTALL_DIR"
python3 -m venv venv
source venv/bin/activate

# ---------------------------------------------
# PYTHON MODULE
# ---------------------------------------------
echo "[5/8] Flask installieren..."
pip install -r requirements.txt

# ---------------------------------------------
# SPEEDTEST CLI INSTALLIEREN
# ---------------------------------------------
echo "[6/8] Speedtest CLI installieren..."

ARCH=$(uname -m)
case "$ARCH" in
    x86_64)  SPEEDTEST_ARCH="x86_64" ;;
    aarch64) SPEEDTEST_ARCH="aarch64" ;;
    *)
        echo "Nicht unterstützte Architektur: $ARCH"
        exit 1
        ;;
esac

if [ -x /usr/local/bin/speedtest ]; then
    echo "Speedtest CLI bereits installiert, überspringe Download."
else
    SPEEDTEST_VERSION="1.2.0"
    SPEEDTEST_TMP="$(mktemp -d)"
    wget -q -O "$SPEEDTEST_TMP/speedtest.tgz" \
        "https://install.speedtest.net/app/cli/ookla-speedtest-${SPEEDTEST_VERSION}-linux-${SPEEDTEST_ARCH}.tgz"
    tar -xzf "$SPEEDTEST_TMP/speedtest.tgz" -C "$SPEEDTEST_TMP"
    install -m 755 "$SPEEDTEST_TMP/speedtest" /usr/local/bin/speedtest
    rm -rf "$SPEEDTEST_TMP"
fi

if ! /usr/local/bin/speedtest --version >/dev/null 2>&1; then
    echo "Speedtest CLI funktioniert nicht korrekt."
    exit 1
fi
echo "Speedtest CLI: $(/usr/local/bin/speedtest --version | head -1)"

# ---------------------------------------------
# SYSTEMD SERVICES
# ---------------------------------------------
echo "[7/8] systemd Services erstellen..."

# Worker
cat <<EOF >/etc/systemd/system/bandbreite-worker.service
[Unit]
Description=Bandbreitentest Worker
After=network.target

[Service]
User=$USER_NAME
WorkingDirectory=$INSTALL_DIR
Environment=PATH=$INSTALL_DIR/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ExecStart=$INSTALL_DIR/venv/bin/python $INSTALL_DIR/worker.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Webinterface
cat <<EOF >/etc/systemd/system/bandbreite-app.service
[Unit]
Description=Bandbreitentest Webinterface
After=network.target

[Service]
User=$USER_NAME
WorkingDirectory=$INSTALL_DIR
Environment=PATH=$INSTALL_DIR/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ExecStart=$INSTALL_DIR/venv/bin/python $INSTALL_DIR/app.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF

cat <<EOF >/etc/sudoers.d/bandbreitentest
$USER_NAME ALL=(root) NOPASSWD: /usr/bin/systemctl start bandbreite-worker.service, /usr/bin/systemctl stop bandbreite-worker.service
EOF
chmod 440 /etc/sudoers.d/bandbreitentest

chown -R "$USER_NAME:$USER_NAME" "$INSTALL_DIR"

# ---------------------------------------------
# SERVICES AKTIVIEREN
# ---------------------------------------------
echo "[8/8] Services aktivieren und starten..."
systemctl daemon-reload
systemctl enable bandbreite-worker.service
systemctl enable bandbreite-app.service
systemctl start bandbreite-worker.service
systemctl start bandbreite-app.service

echo "=== Installation abgeschlossen ==="
echo "Webinterface erreichbar unter: http://<IP>:8080"
