# process/manager.py  # Indique le chemin du fichier dans le projet

import os  # Module pour gérer les processus et le système (fork, exec, etc.)
import signal  # Module pour gérer les signaux Unix (SIGTERM, SIGCHLD, etc.)
import time  # Module pour gérer le temps (sleep, timestamps)
from process.program import Program  # Importe la classe Program (regroupe plusieurs instances)
from process.instance import ProcessInstance  # Importe la classe représentant une instance de process
from utils.enums import ProcessState  # Importe les états possibles d’un process
from config.loader import ConfigLoader  # Importe le loader de configuration
from datetime import datetime  # Module pour gérer les dates et heures

LOG_FILE = "/tmp/taskmaster.log"  # Fichier où seront écrits les logs

class ProcessManager:  # Classe principale qui gère tous les processus
    LOG_COLORS = {  # Dictionnaire pour colorer les logs dans le terminal
        "DEBUG": "\033[94m",   # bleu clair
        "INFO": "\033[92m",    # vert
        "WARNING": "\033[93m", # jaune
        "ERROR": "\033[91m",   # rouge
    }
    LOG_RESET = "\033[0m"  # Code pour reset la couleur du terminal


    def __init__(self, config_path=None, log_level="DEBUG"):  # Constructeur
        self.programs = {}  # Dictionnaire des programmes (nom -> Program)
        self.config_path = config_path  # Chemin du fichier de config
        self.reloading = False  # Indique si un reload est en cours
        self._exited_pids = []  # Liste des processus terminés (PID + code)
        self.manual_stop_pids = set()  # 🔹 Ensemble des PIDs arrêtés manuellement
        self.reload_requested = False  # Flag déclenché par SIGHUP
        self.log_level = log_level  # Niveau de log actuel
        self.log_file = open(LOG_FILE, "a")  # Ouvre le fichier de log en mode append

        # signaux
        signal.signal(signal.SIGCHLD, self.handle_sigchld)  # Appelé quand un process enfant se termine
        signal.signal(signal.SIGHUP, self.handle_sighup)  # Appelé pour recharger la config

    def log(self, message, level="INFO"):  # Fonction de logging
        levels_order = ["DEBUG", "INFO", "WARNING", "ERROR"]  # Ordre des niveaux
        if levels_order.index(level) < levels_order.index(self.log_level):  # Si niveau trop faible
            return  # Ignore le message
        timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")  # Génère un timestamp
        color = self.LOG_COLORS.get(level, "")  # Récupère la couleur associée
        reset = self.LOG_RESET  # Reset couleur
        print(f"{color}{timestamp} [{level}] {message}{reset}", flush=True)  # Affiche dans le terminal
        self.log_file.write(message + "\n")  # Écrit dans le fichier log
        self.log_file.flush()  # Force l’écriture immédiate

    # =========================
    # Program management
    # =========================

    def add_program(self, program: Program):  # Ajoute un programme
        self.programs[program.config.name] = program  # Stocke dans le dict

    def start_program(self, name: str):  # Démarre un programme
        program = self.programs.get(name)  # Récupère le programme
        if not program:  # Si inexistant
            self.log(f"Program '{name}' not found")  # Log erreur
            return
        for inst in program.processes:  # Parcourt les instances
            if inst.state == ProcessState.STOPPED:  # Si arrêtée
                self._start_instance(program, inst)  # Lance l’instance

    def _start_instance(self, program, inst):  # Lance une instance spécifique
        pid = os.fork()  # Fork (crée un process enfant)
        if pid == 0:  # Code exécuté dans le processus enfant
            # Child
            try:
                # stdout/stderr
                if program.config.stdout:  # Si stdout défini
                    fd_out = os.open(program.config.stdout, os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o644)  # Ouvre fichier
                    os.dup2(fd_out, 1)  # Redirige stdout
                    os.close(fd_out)  # Ferme descripteur

                if program.config.stderr:  # Si stderr défini
                    fd_err = os.open(program.config.stderr, os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o644)
                    os.dup2(fd_err, 2)  # Redirige stderr
                    os.close(fd_err)

                # working dir / umask
                if program.config.workingdir:  # Si répertoire défini
                    os.chdir(program.config.workingdir)  # Change dossier

                if program.config.umask is not None:  # Si umask défini
                    os.umask(program.config.umask)  # Applique permissions

                # env vars
                if hasattr(program.config, "env") and program.config.env:  # Si variables d’environnement
                    os.environ.update(program.config.env)  # Les ajoute

                os.execv("/bin/sh", ["sh", "-c", program.config.cmd])  # Lance la commande
            except Exception as e:  # Si erreur
                print(f"Failed to exec {program.config.cmd}: {e}", flush=True)  # Affiche erreur
                os._exit(1)  # Quitte immédiatement
        else:
            # Parent
            inst.mark_started(pid)  # Enregistre PID dans l’instance
            # inst.retry_count += 1
            self.log(f"Started '{program.config.name}' with pid {pid}")  # Log démarrage

    def stop_program(self, name: str):  # Stop un programme
        program = self.programs.get(name)  # Récupère programme
        if not program:
            self.log(f"Program '{name}' not found")
            return
        for inst in program.processes:  # Parcourt instances
            if inst.state == ProcessState.RUNNING and inst.pid:  # Si actif
                pid = inst.pid
                self.manual_stop_pids.add(pid)  # 🔹 Marque comme stoppé manuellement
                try:
                    signal_to_send = getattr(program.config, "stopsignal", signal.SIGTERM)  # Choisit signal
                    os.kill(pid, signal_to_send)  # Envoie signal
                except ProcessLookupError:  # Si process déjà mort
                    pass
                inst.state = ProcessState.STOPPED  # Force état STOPPED
                inst.stop_reason = "user"  # Raison arrêt
                self.log(f"Stopped '{name}' pid={pid}")  # Log

    def restart_program(self, name: str):  # Restart = stop + start
        self.stop_program(name)
        self.start_program(name)

    def get_status(self):
        # 🔹 Traitement des processus terminés avant de renvoyer le status
        self.process_exited()

        status_lines = []
        for prog in self.programs.values():
            running = sum(1 for inst in prog.processes if inst.state == ProcessState.RUNNING)
            total = len(prog.processes)
            retries = sum(inst.retry_count for inst in prog.processes)
            line = f"{prog.config.name}: { 'RUNNING' if running else 'STOPPED' } ({running}/{total}) retries={retries}"
            status_lines.append(line)
        return "\n".join(status_lines)

    # 🔹 nouvelle méthode dans ProcessManager
    def update_status(self):
        """
        Force le traitement des processus terminés en attente (SIGCHLD)
        pour que le status reflète immédiatement l'état réel.
        """
        self.process_exited()
    # =========================
    # SIGCHLD
    # =========================

    def handle_sigchld(self, signum, frame):  # Handler appelé quand un child meurt
        while True:
            try:
                pid, status = os.waitpid(-1, os.WNOHANG)  # Récupère PID terminé sans bloquer
                if pid == 0:
                    break
                exit_code = os.WEXITSTATUS(status) if os.WIFEXITED(status) else None  # Code sortie
                self._exited_pids.append((pid, exit_code))  # Stocke
            except ChildProcessError:
                break

    def process_exited(self):  # Traite les processus terminés
        while self._exited_pids:  # Tant qu’il y a des PIDs
            pid, exit_code = self._exited_pids.pop(0)  # Récupère premier

            # Chercher l’instance correspondante au PID
            matched_inst = None
            for prog in self.programs.values():
                for inst in prog.processes:
                    if inst.pid == pid:
                        matched_inst = inst
                        matched_prog = prog
                        break
                if matched_inst:
                    break

            if not matched_inst:
                self.log(f"[SIGCHLD] Unknown PID {pid} exited with {exit_code}", level="DEBUG")
                continue

            # 🔹 ignore les PIDs stoppés manuellement
            if pid in self.manual_stop_pids:
                self.manual_stop_pids.remove(pid)
                matched_inst.stop_reason = "user"
                self.log(f"Process {pid} stopped manually, not restarting")
                continue

            self.log(
                f"[SIGCHLD] pid={pid} exit_code={exit_code} reloading={self.reloading}",
                level="DEBUG"
            )

            matched_inst.mark_exited(exit_code)
            prog = matched_prog
            inst = matched_inst

            self.log(
                f"[INSTANCE] program={prog.config.name} pid={pid} "
                f"state={inst.state} stop_reason={inst.stop_reason}", level="DEBUG"
            )

            startsecs = getattr(prog.config, "startsecs", 0)
            retries = getattr(prog.config, "startretries", 0)
            exitcodes = getattr(prog.config, "exitcodes", [0])
            now = time.time()
            alive_time = (now - inst.start_time) if inst.start_time else 0

            self.log(
                f"[LIFETIME] program={prog.config.name} pid={pid} "
                f"alive_time={alive_time:.2f}s startsecs={startsecs}", level="DEBUG"
            )

            restart_needed = False

            if exit_code not in exitcodes and alive_time < startsecs:
                if inst.retry_count < retries:
                    inst.retry_count += 1
                    self.log(f"Retrying '{prog.config.name}' attempt {inst.retry_count}/{retries}")
                    restart_needed = True
                else:
                    self.log(f"Max retries reached for '{prog.config.name}'")

            elif prog.config.autorestart == "always":
                if exit_code not in exitcodes:
                    restart_needed = True

            elif prog.config.autorestart == "unexpected":
                if exit_code not in exitcodes or alive_time < startsecs:
                    restart_needed = True

            self.log(
                f"[DECISION] program={prog.config.name} pid={pid} "
                f"restart_needed={restart_needed} "
                f"autorestart={prog.config.autorestart} "
                f"exit_code={exit_code} exitcodes={exitcodes}", level="DEBUG"
            )

            if restart_needed:
                if inst.retry_count >= prog.config.startretries:
                    self.log(
                        f"Giving up restarting '{prog.config.name}' after {inst.retry_count} retries",
                        level="WARNING"
                    )
                    inst.state = ProcessState.STOPPED
                    inst.stop_reason = "fatal"
                    continue

                inst.retry_count += 1
                self._start_instance(prog, inst)

    # =========================
    # Reload config
    # =========================

    def reload_config(self):
        self.log("[TaskMaster] Reloading configuration...")
        self.reloading = True

        if not self.config_path:
            self.log("No config file to reload")
            self.reloading = False
            return

        loader = ConfigLoader(self.config_path)
        loaded_programs = loader.load()
        new_programs = {p.config.name: p for p in loaded_programs}

        for name in list(self.programs.keys()):
            if name not in new_programs:
                self.log(f"Stopping removed program '{name}'")
                self.stop_program(name)
                del self.programs[name]

        for name, new_prog in new_programs.items():
            if name in self.programs:
                old_prog = self.programs[name]
                if not self.same_config(old_prog.config, new_prog.config):
                    self.log(f"Config changed for '{name}'")
                    self.stop_program(name)
                    old_prog.config = new_prog.config
                    old_prog.processes = [ProcessInstance() for _ in range(new_prog.config.numprocs)]
                    if old_prog.config.autostart:
                        self.start_program(name)
            else:
                self.programs[name] = new_prog
                if new_prog.config.autostart:
                    self.start_program(name)

        self.reloading = False

    def same_config(self, a, b):
        return (
            a.cmd == b.cmd and
            a.autorestart == b.autorestart and
            a.autostart == b.autostart and
            a.numprocs == b.numprocs and
            getattr(a, "stdout", None) == getattr(b, "stdout", None) and
            getattr(a, "stderr", None) == getattr(b, "stderr", None)
        )

    # =========================
    # SIGHUP handler
    # =========================

    def handle_sighup(self, signum, frame):
        self.reload_requested = True