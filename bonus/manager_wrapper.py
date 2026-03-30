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
    def start_program(self, name):  # Démarre un programme
        if name in self.disabled_programs:  # Si désactivé
            self.log(f"Program '{name}' is disabled, not starting")
            return

        program = self.manager.programs.get(name)  # Récupère programme
        if not program:
            self.log(f"Program '{name}' not found")
            return

        for inst in program.processes:  # Parcourt instances
            if inst.state != ProcessState.STOPPED:  # Ignore si déjà lancé
                continue

            if program.config.attachable:  # Si mode attachable (PTY)
                master_fd, slave_fd = self.pty_manager.create_pty()  # Crée PTY
                pid = os.fork()  # Fork process

                if pid == 0:  # Process enfant
                    try:
                        os.setsid()  # Nouvelle session
                        fcntl.ioctl(slave_fd, termios.TIOCSCTTY, 0)  # Associe terminal
                        os.dup2(slave_fd, 0)  # stdin
                        os.dup2(slave_fd, 1)  # stdout
                        os.dup2(slave_fd, 2)  # stderr
                        os.close(master_fd)  # Ferme master côté enfant
                        os.close(slave_fd)

                        if program.config.user:  # Si utilisateur défini
                            pw = pwd.getpwnam(program.config.user)  # Récupère infos user
                            os.setgid(pw.pw_gid)  # Change groupe
                            os.setuid(pw.pw_uid)  # Change user

                        os.execv("/bin/sh", ["sh", "-c", program.config.cmd])  # Exécute commande
                    except Exception as e:
                        print(f"PTY exec failed: {e}", flush=True)
                        os._exit(1)
                else:
                    os.close(slave_fd)  # Ferme slave côté parent
                    inst.mark_started(pid)  # Marque comme démarré
                    inst.pty_master_fd = master_fd  # Stocke master fd
                    inst.is_attachable = True  # Rend attachable
                    self.pty_manager.register(pid, master_fd)  # Enregistre session
                    self.log(f"[Daemon] Started attachable '{name}' pid={pid}")

            else:
                # 👇 ancien comportement pipe
                r, w = os.pipe()  # Crée pipe (lecture/écriture)
                pid = os.fork()

                if pid == 0:  # Enfant
                    try:
                        os.dup2(w, 1)  # Redirige stdout
                        os.dup2(w, 2)  # Redirige stderr
                        os.close(r)
                        os.close(w)

                        if program.config.user:
                            try:
                                pw = pwd.getpwnam(program.config.user)
                                os.setgid(pw.pw_gid)
                                os.setuid(pw.pw_uid)
                            except KeyError:
                                self.log(f"User '{program.config.user}' not found", level="ERROR")
                                os._exit(1)

                        os.execv("/bin/sh", ["sh", "-c", program.config.cmd])
                    except Exception as e:
                        print(f"Failed to exec {program.config.cmd}: {e}", flush=True)
                        os._exit(1)
                else:
                    os.close(w)
                    inst.mark_started(pid)
                    self.log(f"[Daemon] Started '{name}' with pid {pid}")

                    t = threading.Thread(target=self._tail_child, args=(pid, r, name), daemon=True)
                    t.start()  # Lance thread lecture logs

    def _tail_child(self, pid, fd, prog_name):  # Lit la sortie d’un process
        seen = set()  # Évite doublons
        while True:
            try:
                data = os.read(fd, 1024)  # Lit données
                if not data:
                    break
                for line in data.decode(errors="ignore").splitlines():  # Parse lignes
                    if line.strip() not in seen:
                        self.log(f"[Child {pid}] {line.strip()}")
                        seen.add(line.strip())
            except OSError:
                break

        os.close(fd)  # Ferme pipe

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