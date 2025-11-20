#!/usr/bin/env python3
"""
Pi Client — reads GPS from gpsd and sends updates to the remote server
"""

import time
import gps
import requests
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

# URL of your Render server
SERVER_URL = "https://gps-render-1-5wka.onrender.com/update"
UPDATE_INTERVAL = 2.0  # seconds

def main():
    # Connect to local gpsd
    try:
        session = gps.gps(mode=gps.WATCH_ENABLE | gps.WATCH_NEWSTYLE)
    except Exception as e:
        logging.error("Failed to connect to gpsd: %s", e)
        return

    logging.info("Pi client started, sending GPS to server every %.1f seconds", UPDATE_INTERVAL)

    while True:
        try:
            report = session.next()
        except StopIteration:
            time.sleep(0.2)
            continue
        except Exception as e:
            logging.warning("gps read exception: %s", e)
            time.sleep(0.5)
            continue

        if getattr(report, "class", "") != "TPV":
            continue

        lat = getattr(report, "lat", None)
        lon = getattr(report, "lon", None)
        mode = getattr(report, "mode", 0)
        t = getattr(report, "time", None)

        if lat is not None and lon is not None:
            payload = {
                "lat": float(lat),
                "lon": float(lon),
                "mode": int(mode),
                "time": str(t) if t else None
            }
            try:
                res = requests.post(SERVER_URL, json=payload, timeout=5)
                if res.status_code == 200:
                    logging.info("Sent GPS: %.6f, %.6f", lat, lon)
                else:
                    logging.warning("Server response: %s", res.text)
            except Exception as e:
                logging.error("Failed to send to server: %s", e)

        time.sleep(UPDATE_INTERVAL)


if __name__ == "__main__":
    main()
