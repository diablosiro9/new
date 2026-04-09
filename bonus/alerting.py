# bonus/alerting.py
import json
import time
import requests

ALERT_FILE = "/tmp/taskmaster_alerts.log"
WEBHOOK_URL = "http://localhost:8080"

def send_alert(event, payload):
    alert = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "event": event,
        "payload": payload,
    }

    with open(ALERT_FILE, "a") as f:
        f.write(json.dumps(alert) + "\n")

    try:
        requests.post(WEBHOOK_URL, json=alert, timeout=0.5)
    except Exception as e:
        print(f"⚠️ Failed to send alert to webhook: {e}")