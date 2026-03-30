#!/bin/bash

DAEMON="bonus/daemon.py"
CONFIG_FILE="bonus.yaml"
PID_FILE="/tmp/taskmaster_daemon.pid"
LOCK_FILE="/tmp/taskmaster_daemon.lock"

start() {
    if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
        echo "[TaskMaster] Daemon already running (PID=$(cat $PID_FILE))"
        exit 0
    fi
    echo "🔹 Starting TaskMaster daemon..."
    python3 "$DAEMON" "$CONFIG_FILE" &
    sleep 1
    for i in {1..10}; do
        if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
            echo "[TaskMaster] Daemon started (PID=$(cat $PID_FILE))"
            return 0
        fi
        sleep 0.2
    done    

    echo "[TaskMaster] Failed to start daemon"
    exit 1

}

stop() {
    if [ ! -f "$PID_FILE" ]; then
        echo "[TaskMaster] Daemon not running"
        exit 0
    fi
    PID=$(cat "$PID_FILE")
    echo "[TaskMaster] Stopping daemon (PID=$PID)..."
    kill -TERM "$PID"
    sleep 1
    rm -f "$PID_FILE" "$LOCK_FILE"
    echo "[TaskMaster] Daemon stopped"
}

reload() {
    if [ ! -f "$PID_FILE" ]; then
        echo "[TaskMaster] Daemon not running, cannot reload"
        exit 1
    fi
    kill -HUP $(cat "$PID_FILE")
    echo "[TaskMaster] Reload sent"
}

status() {
    if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
        echo "[TaskMaster] Daemon running (PID=$(cat $PID_FILE))"
    else
        echo "[TaskMaster] Daemon not running"
    fi
}

case "$1" in
    start|stop|reload|status) "$1" ;;
    *) echo "Usage: $0 {start|stop|reload|status}" ;;
esac
