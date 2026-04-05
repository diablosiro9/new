import os  # Importe le module os pour interagir avec le système (PID, fichiers, etc.)
import sys  # Importe le module sys pour accéder aux arguments du programme et contrôler l'exécution
from config.loader import ConfigLoader
from process.manager import ProcessManager
from shell.control import ControlShell  # Importe une classe qui gère le shell interactif (interface utilisateur)

PID_FILE = "/tmp/taskmaster.pid"  # Définit le chemin d’un fichier où sera stocké le PID du programme

def main():  # Définit la fonction principale du programme
    if len(sys.argv) != 2:  # Vérifie qu'il y a exactement 2 arguments (script + fichier config)
        print("Usage: python3 main.py <config.yaml>")  # Affiche comment utiliser correctement le script
        return  # Quitte la fonction si les arguments sont incorrects

    config_path = sys.argv[1]  # Récupère le chemin du fichier de configuration passé en argument

    # Écrit le PID pour reload_monitor.py
    with open(PID_FILE, "w") as f:  # Ouvre (ou crée) le fichier PID en écriture
        f.write(str(os.getpid()))  # Écrit le PID (identifiant du processus actuel) dans le fichier
    print(f"[TaskMaster] PID = {os.getpid()}")  # Affiche le PID dans le terminal

    # Crée le manager
    manager = ProcessManager(config_path=config_path)  # Crée une instance du gestionnaire de processus avec le chemin de config

    # Charge la config initiale
    loader = ConfigLoader(config_path)  # Crée un chargeur de configuration avec le fichier donné
    programs = loader.load()  # Charge les programmes définis dans le fichier config
    for program in programs:  # Parcourt chaque programme récupéré
        manager.add_program(program)  # Ajoute le programme au gestionnaire
        if program.config.autostart:  # Vérifie si le programme doit démarrer automatiquement
            manager.start_program(program.config.name)  # Lance le programme si autostart est activé

    # Lance le shell
    shell = ControlShell(manager)  # Crée un shell interactif en lui passant le manager
    try:
        shell.run()  # Lance la boucle du shell (attend des commandes utilisateur)
    except KeyboardInterrupt:  # Capture l'interruption clavier (Ctrl+C)
        print("\n[TaskMaster] Interrupted by user, shutting down cleanly")  # Affiche un message propre d’arrêt
        sys.exit(0)  # Quitte proprement le programme avec code de sortie 0 (succès)


if __name__ == "__main__":  # Vérifie que le script est exécuté directement (et non importé)
    main()  # Appelle la fonction principale