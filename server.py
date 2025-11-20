#!/usr/bin/env python3
"""server.py (fixed: template wrapped in {% raw %} to avoid Jinja parsing JS/CSS braces)"""
import os, logging
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string, abort

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
app = Flask(__name__)

store = {"lat": None, "lon": None, "mode": 0, "time": None, "updated_at": None}
API_KEY = os.environ.get("GPS_API_KEY")

# Wrap ENTIRE HTML in a raw block so Jinja won't try to interpret {s}, {z}, JS objects, or CSS braces.
HTML = """{% raw %}
<!doctype html>
<html>
<head><meta charset="utf-8"><title>GPS Map — live</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<style>html,body,#map{height:100%;margin:0;padding:0}#map{height:100vh}</style>
</head>
<body>
<div id="map"></div>
<div id="info" style="position:fixed;z-index:999;background:#fff;padding:6px;border-radius:6px;left:10px;top:10px;">
<b>Lat:</b> <span id="lat">n/a</span> &nbsp; <b>Lon:</b> <span id="lon">n/a</span> &nbsp; <small id="ts"></small>
</div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
  var map = L.map('map').setView([0,0],2);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19, attribution: '© OpenStreetMap contributors'
  }).addTo(map);
  var marker = null;

  async function poll() {
    try {
      const res = await fetch('/pos');
      const j = await res.json();
      if (j.lat !== null && j.mode >= 2) {
        document.getElementById('lat').textContent = j.lat.toFixed(6);
        document.getElementById('lon').textContent = j.lon.toFixed(6);
        document.getElementById('ts').textContent = j.time ? '(' + j.time + ')' : '';
        if (!marker) {
          marker = L.marker([j.lat, j.lon]).addTo(map);
          map.setView([j.lat, j.lon], 16);
        } else {
          marker.setLatLng([j.lat, j.lon]);
        }
      } else {
        document.getElementById('lat').textContent = 'n/a';
        document.getElementById('lon').textContent = 'n/a';
        document.getElementById('ts').textContent = '';
      }
    } catch (e) {
      console.error('poll error', e);
    }
  }

  poll();
  setInterval(poll, 2000);
</script>
</body>
</html>
{% endraw %}"""

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/pos")
def pos():
    return jsonify(store)

@app.route("/update", methods=["POST"])
def update():
    key = request.headers.get("X-GPS-API-KEY")
    if API_KEY and key != API_KEY:
        abort(403)
    data = request.get_json(silent=True)
    if not data:
        return ("bad json", 400)
    try:
        lat = float(data.get("lat"))
        lon = float(data.get("lon"))
        mode = int(data.get("mode", 0))
        t = data.get("time") or datetime.utcnow().isoformat() + "Z"
    except Exception:
        return ("invalid payload", 400)

    store.update({
        "lat": lat,
        "lon": lon,
        "mode": mode,
        "time": t,
        "updated_at": datetime.utcnow().isoformat() + "Z"
    })
    logging.info("Position updated: %s,%s mode=%s", lat, lon, mode)
    return ("ok", 200)

@app.route("/health")
def health():
    return "ok", 200

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 8081)))
