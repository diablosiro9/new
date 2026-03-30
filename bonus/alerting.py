# bonus/alerting.py
import json
import time

ALERT_FILE = "/tmp/taskmaster_alerts.log"

def send_alert(event: str, payload: dict):
    alert = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "event": event,
        "payload": payload,
    }

    with open(ALERT_FILE, "a") as f:
        f.write(json.dumps(alert) + "\n")
