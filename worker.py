import json
import time
import subprocess

import store

DEFAULTS = {"ping_interval": 30, "speedtest_interval": 1800}


# ---------------------------------------------------------
# CONFIG LADEN
# ---------------------------------------------------------

def load_config():
    return store.load_json(store.config_path(), dict(DEFAULTS))


# ---------------------------------------------------------
# PING TEST
# ---------------------------------------------------------

def run_ping():
    try:
        result = subprocess.run(
            ["ping", "-c", "1", "8.8.8.8"],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            return None

        for line in result.stdout.split("\n"):
            if "time=" in line:
                return float(line.split("time=")[1].split(" ")[0])

    except Exception:
        return None

    return None


# ---------------------------------------------------------
# SPEEDTEST (OOKLA CLI)
# ---------------------------------------------------------

def run_speedtest():
    try:
        result = subprocess.run(
            ["/usr/local/bin/speedtest", "--accept-license", "--accept-gdpr", "-f", "json"],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            return None, None

        data = json.loads(result.stdout)

        dl = data["download"]["bandwidth"] * 8 / 1_000_000
        ul = data["upload"]["bandwidth"] * 8 / 1_000_000

        return round(dl, 2), round(ul, 2)

    except Exception:
        return None, None


# ---------------------------------------------------------
# HAUPTSCHLEIFE
# ---------------------------------------------------------

def main():
    print("Worker gestartet...")

    last_ping = 0
    last_speedtest = 0

    while True:
        cfg = load_config()
        ping_interval = cfg.get("ping_interval", DEFAULTS["ping_interval"])
        speedtest_interval = cfg.get("speedtest_interval", DEFAULTS["speedtest_interval"])

        now = time.time()

        ping = None
        dl = None
        ul = None

        # -----------------------------
        # PING AUSFÜHREN
        # -----------------------------
        if now - last_ping >= ping_interval:
            print("Ping wird ausgeführt...")
            ping = run_ping()
            last_ping = now

        # -----------------------------
        # SPEEDTEST AUSFÜHREN
        # -----------------------------
        if now - last_speedtest >= speedtest_interval:
            print("Speedtest wird ausgeführt...")
            dl, ul = run_speedtest()
            last_speedtest = now

        # -----------------------------
        # NUR SPEICHERN, WENN ETWAS GEMESSEN WURDE
        # -----------------------------
        if ping is not None or dl is not None or ul is not None:
            entry = {
                "timestamp": int(time.time()),
                "ping": ping,
                "download": dl,
                "upload": ul
            }

            data = store.load_json(store.data_path(), [])
            data.append(entry)
            store.save_json(store.data_path(), data)

            print(f"Messung gespeichert: Ping={ping}, DL={dl}, UL={ul}")

        time.sleep(1)


if __name__ == "__main__":
    main()