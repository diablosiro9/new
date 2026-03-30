# bonus/logging_utils.py
from datetime import datetime
import time

def timestamp():
    """Retourne le timestamp ISO pour les logs."""
    return datetime.now().isoformat(sep=' ', timespec='seconds')

def log_msg(message: str) -> str:
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    return f"[{timestamp}] {message}"
