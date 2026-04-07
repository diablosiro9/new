from utils.enums import ProcessState  # Importe un enum représentant les états possibles d’un process
import time  # Module pour gérer le temps (sleep, uptime, etc.)
import readline  # Module pour gérer l’entrée utilisateur avec historique et autocomplétion
import rlcompleter  # Module pour l’autocomplétion
import os  # Module pour interagir avec le système (fichiers, chemins, etc.)

readline.parse_and_bind("bind ^I rl_complete")  # Active l’autocomplétion avec la touche TAB

HISTORY_FILE = os.path.expanduser("~/.taskmaster_history")  # Définit le fichier où l’historique sera sauvegardé

class ControlShell:  # Déclare la classe ControlShell (le shell interactif)
    def __init__(self, manager):  # Constructeur de la classe avec un manager en paramètre
        try:
            readline.read_history_file(HISTORY_FILE)  # Charge l’historique des commandes précédentes
        except FileNotFoundError:  # Si le fichier n’existe pas
            pass  # Ignore l’erreur
        self.manager = manager  # Stocke le manager pour gérer les process
        self.running = True  # Indique que le shell est actif
        readline.set_history_length(100)  # Limite l’historique à 100 commandes

        self.commands = ["start", "stop", "restart", "reload", "status", "exit"]  # Liste des commandes disponibles
        readline.parse_and_bind("tab: complete")  # Active l’autocomplétion
        readline.set_completer(self.complete)  # Définit la fonction de complétion personnalisée
        readline.parse_and_bind("set show-all-if-ambiguous on")  # Affiche toutes les options si ambigu
        readline.parse_and_bind("set completion-ignore-case on")  # Ignore la casse (maj/min)
        readline.parse_and_bind("set completion-query-items 100")  # Nombre max d’options affichées

    def complete(self, text, state):  # Fonction appelée pour l’autocomplétion
        buffer = readline.get_line_buffer()  # Récupère le contenu actuel de la ligne
        parts = buffer.split()  # Découpe la ligne en mots

        if len(parts) == 1:  # Si on tape la première partie de la commande
            options = [c for c in self.commands if c.startswith(parts[0])]  # Propose les commandes correspondantes
        elif len(parts) == 2 and parts[0] in ("start", "stop", "restart", "status"):  # Si commande + argument
            options = [
                name for name in self.manager.programs.keys()  # Récupère les noms des programmes
                if name.startswith(parts[1])  # Filtre selon ce que l’utilisateur tape
            ]
        else:
            options = []  # Sinon aucune suggestion

        try:
            return options[state]  # Retourne l’option correspondant à l’index demandé
        except IndexError:  # Si aucune option
            return None  # Ne retourne rien


    def run(self):  # Fonction principale du shell (boucle interactive)
        try:
            while self.running:  # Boucle tant que le shell est actif
                # Gestion des process terminés
                self.manager.process_exited()  # Vérifie les process terminés

                # Traitement du reload demandé par SIGHUP (SAFE)
                if self.manager.reload_requested:  # Si un reload a été demandé
                    self.manager.reload_requested = False  # Reset du flag
                    self.manager.log(
                        "[TaskMaster] SIGHUP received, reloading configuration...",  # Message de log
                        level="INFO"
                    )
                    self.manager.reload_config()  # Recharge la configuration

                try:
                    cmd = input("taskmaster> ").strip()  # Lit la commande utilisateur
                    if cmd:  # Si la commande n’est pas vide
                        readline.add_history(cmd)  # Ajoute à l’historique
                except (KeyboardInterrupt, EOFError):  # Si Ctrl+C ou Ctrl+D
                    print()  # Saut de ligne propre
                    for name in self.manager.programs.keys():  # Parcourt tous les programmes
                        self.manager.stop_program(name)  # Stoppe chaque programme
                    break  # Sort de la boucle

                if cmd == "":  # Si commande vide
                    continue  # Reboucle
                elif cmd == "exit":  # Si commande exit
                    for name in self.manager.programs.keys():  # Parcourt les programmes
                        self.manager.stop_program(name)  # Les stoppe
                    self.running = False  # Arrête la boucle
                elif cmd.startswith("start "):  # Si commande start
                    name = cmd.split(maxsplit=1)[1]  # Récupère le nom du programme
                    self.manager.start_program(name)  # Lance le programme
                elif cmd.startswith("stop "):  # Si commande stop
                    name = cmd.split(maxsplit=1)[1]  # Récupère le nom
                    self.manager.stop_program(name)  # Stoppe le programme
                elif cmd.startswith("status"):
                    # 🔹 Traite immédiatement les SIGCHLD avant de calculer le status
                    self.manager.process_exited()
                    
                    parts = cmd.split()
                    if len(parts) == 1:
                        for name, program in self.manager.programs.items():
                            print(self.format_status(name, program))
                    else:
                        name = parts[1]
                        program = self.manager.programs.get(name)
                        if not program:
                            print(f"Unknown program: {name}")
                        else:
                            print(self.format_status(name, program))  # Affiche son statut
                elif cmd == "reload":  # Si commande reload
                    self.manager.reload_config()  # Recharge la config
                elif cmd.startswith("restart "):  # Si restart
                    name = cmd.split(maxsplit=1)[1]  # Nom du programme
                    self.manager.restart_program(name)  # Redémarre le programme
                else:
                    print(f"Unknown command: '{cmd}'")  # Commande inconnue

                time.sleep(0.1)  # Petite pause pour éviter de surcharger le CPU

        finally:
            # 🔹 Toujours sauvegarder l’historique
            readline.write_history_file(HISTORY_FILE)  # Sauvegarde l’historique dans le fichier

                
    def format_status(self, name, program):  # Fonction pour formater l’affichage d’un programme
        running = [p for p in program.processes if p.state == ProcessState.RUNNING]  # Liste des process actifs
        stopped = [p for p in program.processes if p.state == ProcessState.STOPPED]  # Liste des process stoppés

        retries = max((p.retry_count for p in program.processes), default=0)  # Nombre max de retries
        uptime = None  # Initialise uptime
        for p in running:  # Parcourt les process actifs
            if p.start_time:  # Si heure de démarrage connue
                uptime = int(time.time() - p.start_time)  # Calcule le temps écoulé
                break  # Prend le premier trouvé

        state = "RUNNING" if running else "STOPPED"  # Détermine l’état global
        uptime_str = f"{uptime}s" if uptime is not None else "-"  # Formate l’uptime

        return (  # Retourne une chaîne formatée
            f"{name}: {state} "  # Nom + état
            f"({len(running)}/{len(program.processes)}) "  # Nombre de process actifs / total
            f"retries={retries} uptime={uptime_str}"  # Infos supplémentaires
        )