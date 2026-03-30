#!/bin/bash

CONFIG_FILE="example_config.yaml"

start() {  # Déclare une fonction appelée "start"
    echo "🔹 Starting TaskMaster (mandatory foreground)..."  # Affiche un message dans le terminal
    # Foreground direct, ignore SIGHUP sur le shell parent
    trap '' HUP  # Ignore le signal HUP (fermeture du terminal parent) pour éviter l'arrêt du script
    python3 main.py "$CONFIG_FILE"  # Lance le script Python principal avec le fichier de config
}

case "$1" in  # Analyse le premier argument passé au script (ex: ./script.sh start)
    start)  # Si l'argument est "start"
        start  # Appelle la fonction start définie plus haut
        ;;
    *)  # Si l'argument ne correspond à rien de prévu
        echo "Usage: $0 start"  # Affiche comment utiliser le script
        ;;
esac  # Fin du bloc case