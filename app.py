from flask import Flask, jsonify, request, render_template_string, send_file, url_for
import subprocess
from datetime import datetime, timedelta, timezone
import store

app = Flask(__name__)

CONFIG_FILE = store.config_path()
DATA_FILE = store.data_path()


# ---------------------------------------------------------
# CONFIG LADEN / SPEICHERN
# ---------------------------------------------------------

def load_config():
    cfg = store.load_json(CONFIG_FILE, {
        "ping_interval": 30,
        "speedtest_interval": 1800
    })
    defaults = {"web_username": "admin", "web_password": "admin"}
    changed = False
    for key, value in defaults.items():
        if key not in cfg:
            cfg[key] = value
            changed = True
    if changed:
        store.save_json(CONFIG_FILE, cfg)
    return cfg


def save_config(cfg):
    store.save_json(CONFIG_FILE, cfg)


# ---------------------------------------------------------
# DATA LADEN / SPEICHERN / LÖSCHEN
# ---------------------------------------------------------

def load_data():
    return store.load_json(DATA_FILE, [])


def clear_data():
    store.save_json(DATA_FILE, [])


# ---------------------------------------------------------
# BASIC AUTH SCHUTZ
# ---------------------------------------------------------

@app.before_request
def require_auth():
    cfg = load_config()
    username = cfg.get("web_username", "admin")
    password = cfg.get("web_password", "admin")
    auth = request.authorization
    if not auth or auth.username != username or auth.password != password:
        return jsonify({"error": "authorization required"}), 401, {
            "WWW-Authenticate": 'Basic realm="Bandbreitentest"'
        }


# ---------------------------------------------------------
# SYSTEMD STEUERUNG
# ---------------------------------------------------------

def worker_status():
    result = subprocess.run(
        ["systemctl", "is-active", "bandbreite-worker.service"],
        capture_output=True,
        text=True
    )
    return result.stdout.strip()


def worker_start():
    subprocess.run(["sudo", "systemctl", "start", "bandbreite-worker.service"])


def worker_stop():
    subprocess.run(["sudo", "systemctl", "stop", "bandbreite-worker.service"])


# ---------------------------------------------------------
# API ROUTEN
# ---------------------------------------------------------

@app.route("/api/worker/status")
def api_worker_status():
    return jsonify({"status": worker_status()})


@app.route("/api/worker/start", methods=["POST"])
def api_worker_start():
    worker_start()
    return jsonify({"status": "started"})


@app.route("/api/worker/stop", methods=["POST"])
def api_worker_stop():
    worker_stop()
    return jsonify({"status": "stopped"})


@app.route("/api/config", methods=["GET", "POST"])
def api_config():
    if request.method == "GET":
        cfg = load_config()
    public = {k: v for k, v in cfg.items() if k not in ("web_username", "web_password")}
    return jsonify(public)

    data = request.get_json(silent=True) or {}
    cfg = load_config()

    try:
        if "ping_interval" in data:
            value = int(data["ping_interval"])
            if value < 1:
                raise ValueError
            cfg["ping_interval"] = value

        if "speedtest_interval" in data:
            value = int(data["speedtest_interval"])
            if value < 1:
                raise ValueError
            cfg["speedtest_interval"] = value
    except (TypeError, ValueError):
        return jsonify({"status": "error", "error": "Intervall muss eine positive Zahl sein"}), 400

    save_config(cfg)
    return jsonify({"status": "saved", "config": cfg})


@app.route("/api/config/password", methods=["POST"])
def api_change_password():
    data = request.get_json(silent=True) or {}
    old_password = data.get("old_password", "")
    new_password = data.get("new_password", "")

    cfg = load_config()
    if old_password != cfg.get("web_password"):
        return jsonify({"status": "error", "error": "Altes Passwort falsch"}), 403
    if len(new_password) < 6:
        return jsonify({"status": "error", "error": "Neues Passwort muss mindestens 6 Zeichen lang sein"}), 400

    cfg["web_password"] = new_password
    save_config(cfg)
    return jsonify({"status": "changed"})


MAX_CHART_POINTS = 1000


def downsample(points, limit):
    n = len(points)
    if n <= limit:
        return points
    step = n / limit
    return [points[int(i * step)] for i in range(limit)]


@app.route("/api/data")
def api_data():
    data = load_data()

    if "start" not in request.args and "end" not in request.args:
        if "limit" in request.args:
            try:
                return jsonify(data[-int(request.args["limit"]):])
            except ValueError:
                return jsonify({"error": "ungültiges limit"}), 400
        return jsonify(data)

    try:
        start = int(request.args["start"]) if request.args.get("start") else None
        end = int(request.args["end"]) if request.args.get("end") else None
    except ValueError:
        return jsonify({"error": "ungültiger Zeitbereich"}), 400

    data = [d for d in data
            if (start is None or d["timestamp"] >= start)
            and (end is None or d["timestamp"] <= end)]
    return jsonify(downsample(data, MAX_CHART_POINTS))


@app.route("/api/data/summary")
def api_data_summary():
    data = load_data()
    try:
        tz_minutes = int(request.args.get("tz", "0"))
    except ValueError:
        tz_minutes = 0
    tz = timezone(timedelta(minutes=tz_minutes))

    dates = {}
    for d in data:
        dt = datetime.fromtimestamp(d["timestamp"], tz)
        dates.setdefault(dt.strftime("%Y-%m-%d"), set()).add(dt.hour)

    return jsonify({
        "count": len(data),
        "dates": [{"date": date, "hours": sorted(hours)} for date, hours in dates.items()]
    })


@app.route("/api/data/clear", methods=["POST"])
def api_data_clear():
    clear_data()
    return jsonify({"status": "cleared"})


@app.route("/api/data/download")
def api_data_download():
    return send_file(DATA_FILE, as_attachment=True)


# ---------------------------------------------------------
# WEBINTERFACE MIT TABS + DARK MODE + CHECKBOXEN + START/ENDE DATUM/STUNDE
# ---------------------------------------------------------

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Bandbreitentest</title>

    <style>
        body {
            font-family: Arial;
            margin: 20px;
            background: white;
            color: black;
        }

        .tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
        }

        .tab {
            padding: 10px 15px;
            background: #ddd;
            cursor: pointer;
            border-radius: 5px;
        }

        .tab.active {
            background: #007bff;
            color: white;
        }

        .content {
            display: none;
        }

        .content.active {
            display: block;
        }

        .box {
            border: 1px solid #ccc;
            padding: 15px;
            background: #f7f7f7;
        }

        button {
            padding: 10px;
            margin: 5px;
            background: #007bff;
            color: white;
            border: none;
            cursor: pointer;
        }

        footer {
            margin-top: 30px;
            padding: 15px 0;
            font-size: 13px;
            color: #888;
            text-align: center;
            border-top: 1px solid #ddd;
        }

        input, select {
            padding: 5px;
            width: 150px;
        }

        /* DARK MODE */
        @media (prefers-color-scheme: dark) {
            body {
                background: #121212;
                color: #e0e0e0;
            }

            .box {
                background: #1e1e1e;
                border-color: #333;
            }

            .tab {
                background: #333;
                color: #ccc;
            }

            .tab.active {
                background: #2196f3;
                color: white;
            }

            input, select {
                background: #2a2a2a;
                color: white;
                border: 1px solid #444;
            }
        }
    </style>

    <script src="{{ url_for('static', filename='chart.min.js') }}"></script>
</head>
<body>

<h1>Bandbreitentest</h1>

    <div class="tabs">
        <div class="tab" onclick="showTab('status')">Status</div>
        <div class="tab" onclick="showTab('config')">Konfiguration</div>
        <div class="tab" onclick="showTab('password')">Passwort</div>
        <div class="tab active" onclick="showTab('chart')">Diagramm</div>
        <div class="tab" onclick="showTab('data')">Daten</div>
    </div>

<!-- STATUS -->
<div id="status" class="content box">
    <h2>Worker Status</h2>
    <p>Status: <span id="workerStatus">Lade...</span></p>
    <button onclick="startWorker()">Starten</button>
    <button onclick="stopWorker()">Stoppen</button>
</div>

<!-- KONFIG -->
<div id="config" class="content box">
    <h2>Konfiguration</h2>

    <label>Ping Intervall (Sekunden):</label>
    <input id="pingInput" type="number"><br><br>

    <label>Speedtest Intervall (Sekunden):</label>
    <input id="speedtestInput" type="number"><br><br>

    <button onclick="saveConfig()">Speichern</button>
</div>

<!-- PASSWORT -->
<div id="password" class="content box">
    <h2>Passwort ändern</h2>

    <label>Aktuelles Passwort:</label>
    <input id="oldPasswordInput" type="password"><br><br>

    <label>Neues Passwort (min. 6 Zeichen):</label>
    <input id="newPasswordInput" type="password"><br><br>

    <button onclick="changePassword()">Passwort ändern</button>
</div>

<!-- DIAGRAMM -->
<div id="chart" class="content active box">
<table>
    <tr>
        <td>
            <h2>Diagramm</h2>
        </td>
        <td width="150"></td>
        <td>
        </td>
    </tr>
    <tr>
        <td>
            <label><input type="checkbox" id="cbPing" checked onchange="updateChartVisibility()"> Ping</label> <br>
            <label><input type="checkbox" id="cbDownload" checked onchange="updateChartVisibility()"> Download</label> <br>
            <label><input type="checkbox" id="cbUpload" checked onchange="updateChartVisibility()"> Upload</label> <br>

        </td>
        <td>
        </td>
        <td>
            <h3>Zeitbereich</h3>

            <div>
                <strong>Start:</strong>
                <label>Datum:</label>
                <select id="startDateSelect" onchange="updateStartHourSelector(); applyDateHourRangeFilter();"></select>

                <label>Stunde:</label>
                <select id="startHourSelect" onchange="applyDateHourRangeFilter();"></select>
            </div>

            <div style="margin-top:10px;">
                <strong>Ende:</strong>
                <label>Datum:</label>
                <select id="endDateSelect" onchange="updateEndHourSelector(); applyDateHourRangeFilter();"></select>

                <label>Stunde:</label>
                <select id="endHourSelect" onchange="applyDateHourRangeFilter();"></select>
            </div>
        </td>
    </tr>
</table>

    <br><br>

    <canvas id="chartCanvas" height="80"></canvas>

</div>

<!-- DATEN -->
<div id="data" class="content box">
    <h2>Daten</h2>
    <button onclick="downloadData()">Download</button>
    <button onclick="clearData()">Löschen</button>
    <pre id="dataBox">Lade...</pre>
</div>

<script>
let chart = null;
let lastChartData = null;
let rangeInfo = [];
let lastSummary = null;

function pad2(n) {
    return (n < 10 ? "0" + n : "" + n);
}

function showTab(name) {
    document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
    document.querySelectorAll(".content").forEach(c => c.classList.remove("active"));

    document.querySelector(`.tab[onclick="showTab('${name}')"]`).classList.add("active");
    document.getElementById(name).classList.add("active");
}

function isDarkMode() {
    return window.matchMedia &&
           window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function updateStatus() {
    fetch("/api/worker/status")
        .then(r => r.json())
        .then(d => document.getElementById("workerStatus").innerText = d.status);
}

function startWorker() {
    fetch("/api/worker/start", {method: "POST"})
        .then(() => updateStatus());
}

function stopWorker() {
    fetch("/api/worker/stop", {method: "POST"})
        .then(() => updateStatus());
}

function loadConfig() {
    fetch("/api/config")
        .then(r => r.json())
        .then(cfg => {
            document.getElementById("pingInput").value = cfg.ping_interval;
            document.getElementById("speedtestInput").value = cfg.speedtest_interval;
        });
}

function saveConfig() {
    const ping = document.getElementById("pingInput").value;
    const speed = document.getElementById("speedtestInput").value;

    fetch("/api/config", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
            ping_interval: ping,
            speedtest_interval: speed
        })
    }).then(() => alert("Gespeichert"));
}

function changePassword() {
    const oldp = document.getElementById("oldPasswordInput").value;
    const newp = document.getElementById("newPasswordInput").value;
    fetch("/api/config/password", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({old_password: oldp, new_password: newp})
    }).then(r => r.json().then(d => ({ok: r.ok, d})))
      .then(({ok, d}) => {
          if (ok && d.status === "changed") {
              alert("Passwort geändert. Bitte mit neuem Passwort neu anmelden.");
              document.getElementById("oldPasswordInput").value = "";
              document.getElementById("newPasswordInput").value = "";
          } else {
              alert("Fehler: " + (d.error || "Unbekannt"));
          }
      });
}

function buildDateSelectors() {
    const startDateSel = document.getElementById("startDateSelect");
    const endDateSel = document.getElementById("endDateSelect");
    const prevStart = startDateSel.value;
    const prevEnd = endDateSel.value;

    startDateSel.innerHTML = "";
    endDateSel.innerHTML = "";

    rangeInfo.forEach(e => {
        const opt1 = document.createElement("option");
        opt1.value = e.date;
        opt1.textContent = e.date;
        startDateSel.appendChild(opt1);

        const opt2 = document.createElement("option");
        opt2.value = e.date;
        opt2.textContent = e.date;
        endDateSel.appendChild(opt2);
    });

    const select = (sel, prev, preferLast) => {
        if (prev && [...sel.options].some(o => o.value === prev)) {
            sel.value = prev;
        } else if (sel.options.length > 0) {
            sel.selectedIndex = preferLast ? sel.options.length - 1 : 0;
        }
    };
    select(startDateSel, prevStart, false);
    select(endDateSel, prevEnd, true);
}

function updateStartHourSelector() {
    const hourSel = document.getElementById("startHourSelect");
    const prevHour = hourSel.value;
    hourSel.innerHTML = "";

    const date = document.getElementById("startDateSelect").value;
    const info = rangeInfo.find(e => e.date === date);
    const hours = info ? info.hours : [];

    hours.forEach(h => {
        const opt = document.createElement("option");
        opt.value = h;
        opt.textContent = pad2(h) + ":00";
        hourSel.appendChild(opt);
    });

    if (prevHour !== "" && hours.includes(parseInt(prevHour))) {
        hourSel.value = prevHour;
    } else if (hourSel.options.length > 0) {
        hourSel.selectedIndex = 0;
    }
}

function updateEndHourSelector() {
    const hourSel = document.getElementById("endHourSelect");
    const prevHour = hourSel.value;
    hourSel.innerHTML = "";

    const date = document.getElementById("endDateSelect").value;
    const info = rangeInfo.find(e => e.date === date);
    const hours = info ? info.hours : [];

    hours.forEach(h => {
        const opt = document.createElement("option");
        opt.value = h;
        opt.textContent = pad2(h) + ":00";
        hourSel.appendChild(opt);
    });

    if (prevHour !== "" && hours.includes(parseInt(prevHour))) {
        hourSel.value = prevHour;
    } else if (hourSel.options.length > 0) {
        hourSel.selectedIndex = hourSel.options.length - 1;
    }
}

function applyDateHourRangeFilter() {
    const startDate = document.getElementById("startDateSelect").value;
    const endDate = document.getElementById("endDateSelect").value;
    const startHour = document.getElementById("startHourSelect").value;
    const endHour = document.getElementById("endHourSelect").value;

    if (!startDate || !endDate || startHour === "" || endHour === "") {
        updateChart([]);
        return;
    }

    const toTs = (date, hour, sec) => new Date(date + "T" + pad2(hour) + ":" + sec).getTime() / 1000;
    const startTs = Math.floor(toTs(startDate, startHour, "00"));
    const endTs = Math.floor(toTs(endDate, endHour, "59:59"));

    fetch("/api/data?start=" + startTs + "&end=" + endTs)
        .then(r => r.json())
        .then(d => {
            lastChartData = d;
            updateChart(d);
        });
}

function updateChart(data) {
    if (!data || data.length === 0) {
        if (chart !== null) {
            chart.destroy();
            chart = null;
        }
        return;
    }

    const labels = data.map(d => new Date(d.timestamp * 1000).toLocaleTimeString());

    const ping = data.map(d => d.ping ?? null);
    const download = data.map(d => d.download ?? null);
    const upload = data.map(d => d.upload ?? null);

    if (chart !== null) chart.destroy();

    const ctx = document.getElementById("chartCanvas").getContext("2d");

    chart = new Chart(ctx, {
        type: "line",
        data: {
            labels: labels,
            datasets: [
                {
                    label: "Ping (ms)",
                    data: ping,
                    borderColor: "orange",
                    fill: false,
                    hidden: !document.getElementById("cbPing").checked,
                    spanGaps: true
                },
                {
                    label: "Download (Mbit/s)",
                    data: download,
                    borderColor: "green",
                    fill: false,
                    hidden: !document.getElementById("cbDownload").checked,
                    spanGaps: true
                },
                {
                    label: "Upload (Mbit/s)",
                    data: upload,
                    borderColor: "blue",
                    fill: false,
                    hidden: !document.getElementById("cbUpload").checked,
                    spanGaps: true
                }
            ]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    labels: { color: isDarkMode() ? "#e0e0e0" : "#000000" }
                }
            },
            scales: {
                x: { ticks: { color: isDarkMode() ? "#e0e0e0" : "#000000" }},
                y: { beginAtZero: true, ticks: { color: isDarkMode() ? "#e0e0e0" : "#000000" }}
            }
        }
    });
}

function updateChartVisibility() {
    if (!chart) return;

    chart.data.datasets[0].hidden = !document.getElementById("cbPing").checked;
    chart.data.datasets[1].hidden = !document.getElementById("cbDownload").checked;
    chart.data.datasets[2].hidden = !document.getElementById("cbUpload").checked;

    chart.update();
}

function loadSummary() {
    const tz = -new Date().getTimezoneOffset();
    return fetch("/api/data/summary?tz=" + tz)
        .then(r => r.json())
        .then(s => {
            lastSummary = s;
            rangeInfo = s.dates;

            if (s.count === 0) {
                updateChart([]);
                document.getElementById("dataBox").innerText = "Keine Daten vorhanden.";
                return;
            }

            buildDateSelectors();
            updateStartHourSelector();
            updateEndHourSelector();
            applyDateHourRangeFilter();
            loadRecent();
        });
}

function loadRecent() {
    fetch("/api/data?limit=100")
        .then(r => r.json())
        .then(d => {
            const extra = lastSummary
                ? "\\n\\n(letzte " + d.length + " von " + lastSummary.count + " Messungen)"
                : "";
            document.getElementById("dataBox").innerText = JSON.stringify(d, null, 2) + extra;
        });
}

function clearData() {
    fetch("/api/data/clear", {method: "POST"})
        .then(() => { loadSummary(); loadRecent(); });
}

function downloadData() {
    window.location.href = "/api/data/download";
}

updateStatus();
loadConfig();
loadSummary();

setInterval(updateStatus, 5000);
setInterval(loadSummary, 120000);
</script>

<footer>&copy; 2026 Fr3akOverflow &middot; MIT License</footer>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML)


# ---------------------------------------------------------
# START
# ---------------------------------------------------------

if __name__ == "__main__":
    print("Webinterface: http://0.0.0.0:8080")
    cfg = load_config()
    print(f"Login: {cfg['web_username']} / {cfg['web_password']}")
    app.run(host="0.0.0.0", port=8080)
