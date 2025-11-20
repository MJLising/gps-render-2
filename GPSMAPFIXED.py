#!/usr/bin/env python3
"""
GPSMAPFIXED.py
Serve a live Leaflet map (HTTP) with position read from gpsd.
Access: http://localhost:8000  (or http://<raspi-ip>:8000 on LAN)
"""

import time
import threading
from flask import Flask, jsonify, render_template_string
import gps
import logging

# Configuration
HOST = "127.1.1.1"     # "127.0.0.1" for localhost only, "0.0.0.0" for LAN access
PORT = 8081
UPDATE_INTERVAL = 2.0  # seconds between front-end polls
ZOOM = 16

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

app = Flask(__name__)

# Shared GPS state
state = {
    "lat": None,
    "lon": None,
    "mode": 0,
    "time": None,
}

# HTML template for Leaflet map
HTML_PAGE = """<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>GPS Map — live</title>
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
  <style>html,body,#map{{height:100%;margin:0;padding:0}}#map{{height:100vh}}</style>
</head>
<body>
<div id="map"></div>
<div id="info" style="position:fixed;z-index:999;background:#fff;padding:6px;border-radius:6px;left:10px;top:10px;box-shadow:0 0 6px rgba(0,0,0,.15);font-family:Arial,Helvetica,sans-serif">
  <b>Lat:</b> <span id="lat">n/a</span> &nbsp; <b>Lon:</b> <span id="lon">n/a</span> &nbsp; <small id="ts"></small>
</div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
  var map = L.map('map').setView([0, 0], 2);
  L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
    maxZoom: 19,
    attribution: '© OpenStreetMap contributors'
  }}).addTo(map);

  var marker = null;
  function updatePos(obj) {{
    if (!obj || obj.mode < 2 || obj.lat === null) {{
      document.getElementById('lat').textContent = 'n/a';
      document.getElementById('lon').textContent = 'n/a';
      document.getElementById('ts').textContent = '';
      return;
    }}
    var lat = obj.lat;
    var lon = obj.lon;
    document.getElementById('lat').textContent = lat.toFixed(6);
    document.getElementById('lon').textContent = lon.toFixed(6);
    document.getElementById('ts').textContent = obj.time ? '(' + obj.time + ')' : '';
    if (!marker) {{
      marker = L.marker([lat, lon]).addTo(map);
      map.setView([lat, lon], {zoom});
      marker.bindPopup('Lat: ' + lat.toFixed(6) + '<br>Lon: ' + lon.toFixed(6));
    }} else {{
      marker.setLatLng([lat, lon]);
      marker.getPopup().setContent('Lat: ' + lat.toFixed(6) + '<br>Lon: ' + lon.toFixed(6));
    }}
  }}

  async function poll() {{
    try {{
      const res = await fetch('/pos');
      const j = await res.json();
      updatePos(j);
    }} catch (err) {{
      console.error('poll error', err);
    }}
  }}

  poll();
  setInterval(poll, {poll_ms});
</script>
</body>
</html>
""".format(zoom=ZOOM, poll_ms=int(UPDATE_INTERVAL * 1000))


def gps_thread():
    """Background thread that reads gpsd and updates shared state."""
    try:
        session = gps.gps(mode=gps.WATCH_ENABLE | gps.WATCH_NEWSTYLE)
    except Exception as e:
        logging.error("Unable to connect to gpsd: %s", e)
        return

    logging.info("GPS thread started, listening to gpsd...")
    while True:
        try:
            report = session.next()
        except StopIteration:
            time.sleep(0.2)
            continue
        except Exception as e:
            logging.debug("gps read exception: %s", e)
            time.sleep(0.5)
            continue

        # handle both dict and object types
        cls = getattr(report, "class", None) or report.get("class", None)
        if cls == "TPV":
            lat = getattr(report, "lat", None) or report.get("lat", None)
            lon = getattr(report, "lon", None) or report.get("lon", None)
            mode = getattr(report, "mode", 0) or report.get("mode", 0)
            t = getattr(report, "time", None) or report.get("time", None)

            if lat is not None and lon is not None:
                state["lat"] = float(lat)
                state["lon"] = float(lon)
                state["mode"] = int(mode)
                state["time"] = str(t) if t else None

        time.sleep(0.01)


@app.route("/")
def index():
    return render_template_string(HTML_PAGE)


@app.route("/pos")
def pos():
    return jsonify(state)


def main():
    # start GPS thread
    t = threading.Thread(target=gps_thread, daemon=True)
    t.start()

    logging.info("Starting Flask server on %s:%d", HOST, PORT)
    app.run(host=HOST, port=PORT, debug=False, threaded=True)


if __name__ == "__main__":
    main()