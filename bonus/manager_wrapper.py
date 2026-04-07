import os  # Module système (fork, fichiers, pipes, etc.)
import threading  # Permet de lancer des threads (pour lire les logs)
import time  # Gestion du temps
import pwd  # Permet de récupérer infos utilisateur Linux
import grp  # (non utilisé ici mais permet gestion groupes)
import json  # Pour écrire les alertes en JSON
import fcntl  # Pour manipuler les descripteurs (pty notamment)
import termios  # Gestion terminal (pty)
from process.manager import ProcessManager  # Manager principal des process
from utils.enums import ProcessState  # États des process (RUNNING, STOPPED)
from bonus.logger import log  # Logger custom
from bonus.webhook import send_webhook  # Envoi webhook (alertes externes)
from bonus.pty_manager import PTYManager  # Gestion des pseudo-terminaux

ALERT_FILE = os.path.join(os.path.dirname(__file__), "logs/alerts.log")  # Fichier des alertes
os.makedirs(os.path.dirname(ALERT_FILE), exist_ok=True)  # Crée dossier si besoin

class ManagerWrapper:  # Wrapper autour du ProcessManager pour ajouter des features bonus
    def __init__(self, config_path, is_daemon=False):  # Constructeur
        self.manager = ProcessManager(config_path)  # Initialise manager principal
        self.disabled_programs = set()  # Liste des programmes désactivés
        self._child_threads = {}  # pid -> thread (lecture logs)
        self._exited_pids = set()  # PIDs déjà traités
        self.is_daemon = is_daemon  # Mode daemon ou non
        self.pty_manager = PTYManager()  # Initialise gestionnaire PTY
        self.manager.pty_manager = self.pty_manager

    def log(self, message, level="INFO"):  # Wrapper log
        log(message, level, is_daemon=self.is_daemon)  # Appelle logger custom

    def send_alert(self, event, payload):  # Envoie une alerte
        if not self.is_daemon:  # Si pas en daemon
            return  # Ignore

        alert = {  # Construit l’objet alerte
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),  # Timestamp
            "event": event,  # Type d’événement
            "payload": payload,  # Données associées
        }

        with open(ALERT_FILE, "a+", buffering=1) as f:  # Ouvre fichier alertes
            f.write(json.dumps(alert) + "\n")  # Écrit en JSON

        self.log(f"[ALERT] {event} {payload}", level="WARNING")  # Log local
        send_webhook(alert)  # Envoie webhook

    # --- start / stop / reload / tail_child comme avant ---
    def start_program(self, name):
        if name in self.disabled_programs:
            self.log(f"Program '{name}' is disabled, not starting")
            return

        program = self.manager.programs.get(name)
        if not program:
            self.log(f"Program '{name}' not found")
            return

        # 👉 UTILISE le vrai manager
        self.manager.start_program(name)

    def _tail_child(self, pid, fd, prog_name):
        seen = set()
        while True:
            try:
                data = os.read(fd, 1024)
                if not data:
                    break
                for line in data.decode(errors="ignore").splitlines():
                    line_clean = line.strip()
                    if line_clean not in seen:
                        self.log(f"[Child {pid}] {line_clean}")
                        seen.add(line_clean)
                        
                        # Envoi au webhook HTTP
                        try:
                            from bonus.alerting import send_alert
                            send_alert(
                                event="program_log",
                                payload={
                                    "program": prog_name,
                                    "pid": pid,
                                    "line": line_clean
                                }
                            )
                        except Exception as e:
                            print(f"⚠️ Failed to send program log alert: {e}", flush=True)
            except OSError:
                break

        os.close(fd)

        if pid not in self._exited_pids:  # Évite double alerte
            self._exited_pids.add(pid)
            self.send_alert("process_exited", {"program": prog_name, "pid": pid})

    def stop_program(self, name):  # Stop programme
        self.disabled_programs.add(name)  # Marque comme désactivé

        program = self.manager.programs.get(name)
        if program:
            for inst in program.processes:
                if inst.state == ProcessState.RUNNING and inst.pid:
                    self.send_alert("process_stopped", {"program": name, "pid": inst.pid})

        self.manager.stop_program(name)  # Appelle vrai stop

    def reload_config(self):  # Reload config
        self.manager.reload_config()  # Recharge

        for name, prog in self.manager.programs.items():
            if name in self.disabled_programs:
                self.log(f"[Bonus] '{name}' disabled, ignoring reload")
                continue

            desired = prog.config.numprocs  # Nombre voulu
            running = len([p for p in prog.processes if p.state == ProcessState.RUNNING])  # Nombre actuel

            if running < desired:
                self.log(f"[Bonus] Increasing '{name}' {running} -> {desired}")
                for _ in range(desired - running):
                    self.start_program(name)

            elif running > desired:
                self.log(f"[Bonus] Decreasing '{name}' {running} -> {desired}")
                self.manager.stop_program(name)

    def __getattr__(self, attr):  # Proxy vers manager
        return getattr(self.manager, attr)  # Redirige appel