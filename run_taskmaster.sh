#!/bin/bash

CONFIG_FILE="example_config.yaml"
VENV_DIR="venv"

start() {
    echo "🔹 Starting TaskMaster (mandatory foreground)..."

    # Créer venv si absent
    if [ ! -d "$VENV_DIR" ]; then
        echo "📦 Creating virtual environment..."
        python3 -m venv "$VENV_DIR"
    fi

    # Activer venv
    source "$VENV_DIR/bin/activate"

    # Installer deps si besoin
    pip install -q -r requirements.txt

    trap '' HUP

    python main.py "$CONFIG_FILE"
}

case "$1" in
    start)
        start
        ;;
    *)
        echo "Usage: $0 start"
        ;;
esac