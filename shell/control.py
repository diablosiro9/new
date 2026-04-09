from utils.enums import ProcessState  # Importe un enum représentant les états possibles d’un process
import time  # Module pour gérer le temps (sleep, uptime, etc.)
import readline  # Module pour gérer l’entrée utilisateur avec historique et autocomplétion
import rlcompleter  # Module pour l’autocomplétion
import os  # Module pour interagir avec le système (fichiers, chemins, etc.)
import select
import sys

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
        self.manager.prompt_redraw = self._redraw_prompt
    
    def _redraw_prompt(self):
        sys.stdout.write("taskmaster> ")
        sys.stdout.flush()

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


    def run(self):
        try:
            sys.stdout.write("taskmaster> ")
            sys.stdout.flush()
            while self.running:
                self.manager.process_exited()

                if self.manager.reload_requested:
                    self.manager.reload_requested = False
                    self.manager.log("[TaskMaster] SIGHUP received, reloading...", level="INFO")
                    self.manager.reload_config()

                ready, _, _ = select.select([sys.stdin], [], [], 0.5)
                if not ready:
                    continue

                try:
                    cmd = sys.stdin.readline()
                    if cmd == "":  # EOF Ctrl+D
                        print()
                        for name in self.manager.programs.keys():
                            self.manager.stop_program(name)
                            self.manager.prompt_redraw = None
                        break
                    cmd = cmd.strip()
                except KeyboardInterrupt:
                    print()
                    for name in self.manager.programs.keys():
                        self.manager.stop_program(name)
                        self.manager.prompt_redraw = None
                    break

                if not cmd:
                    sys.stdout.write("taskmaster> ")
                    sys.stdout.flush()
                    continue

                readline.add_history(cmd)

                if cmd == "exit":
                    for name in self.manager.programs.keys():
                        self.manager.stop_program(name)
                    self.running = False
                    self.manager.prompt_redraw = None
                    continue 
                elif cmd.startswith("start "):
                    name = cmd.split(maxsplit=1)[1].strip()
                    self.manager.start_program(name)

                elif cmd.startswith("stop "):
                    name = cmd.split(maxsplit=1)[1].strip()
                    self.manager.stop_program(name)

                elif cmd.startswith("restart "):
                    name = cmd.split(maxsplit=1)[1].strip()
                    self.manager.restart_program(name)

                elif cmd.startswith("status"):
                    parts = cmd.split()
                    if len(parts) == 1:
                        for pname, program in self.manager.programs.items():
                            print(self.format_status(pname, program))
                    else:
                        pname = parts[1]
                        program = self.manager.programs.get(pname)
                        if not program:
                            print(f"Unknown program: {pname}")
                        else:
                            print(self.format_status(pname, program))

                elif cmd == "reload":
                    self.manager.reload_config()
                    continue

                else:
                    print(f"Unknown command: '{cmd}'")

                sys.stdout.write("taskmaster> ")
                sys.stdout.flush()

        finally:
            readline.write_history_file(HISTORY_FILE)
                    
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