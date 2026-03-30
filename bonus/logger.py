import os
import time

LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
DAEMON_LOG = os.path.join(LOG_DIR, "daemon.log")

def log_msg(message: str, level: str = "INFO") -> str:
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    return f"[{timestamp}] [{level}] {message}"

def log(message: str, level: str = "INFO", is_daemon: bool = False, print_stdout: bool = True):
    """Logger simple, seulement si is_daemon=True"""
    if not is_daemon:
        return
    line = log_msg(message, level)
    with open(DAEMON_LOG, "a+", buffering=1) as f:
        f.write(line + "\n")
    if print_stdout:
        print(line, flush=True)
