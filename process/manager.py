# process/manager.py

import os
import pty
import pwd
import signal
import time
from process.program import Program
from process.instance import ProcessInstance
from utils.enums import ProcessState
from config.loader import ConfigLoader
from datetime import datetime

LOG_FILE = "/tmp/taskmaster.log"

class ProcessManager:
    LOG_COLORS = {
        "DEBUG": "\033[94m",
        "INFO": "\033[92m",
        "WARNING": "\033[93m",
        "ERROR": "\033[91m",
    }
    LOG_RESET = "\033[0m"

    def __init__(self, config_path=None, log_level="DEBUG"):
        self.programs = {}
        self.config_path = config_path
        self.reloading = False
        self._exited_pids = []
        self.manual_stop_pids = set()
        self.reload_requested = False
        self.log_level = log_level
        self.log_file = open(LOG_FILE, "a")
        self.pty_manager = None  # Sera injecté par ManagerWrapper

        signal.signal(signal.SIGCHLD, self.handle_sigchld)
        signal.signal(signal.SIGHUP, self.handle_sighup)

    def log(self, message, level="INFO"):
        levels_order = ["DEBUG", "INFO", "WARNING", "ERROR"]
        if levels_order.index(level) < levels_order.index(self.log_level):
            return
        timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
        color = self.LOG_COLORS.get(level, "")
        reset = self.LOG_RESET
        print(f"{color}{timestamp} [{level}] {message}{reset}", flush=True)
        self.log_file.write(message + "\n")
        self.log_file.flush()

    # =========================
    # Program management
    # =========================

    def add_program(self, program: Program):
        self.programs[program.config.name] = program

    def start_program(self, name: str):
        program = self.programs.get(name)
        if not program:
            self.log(f"Program '{name}' not found")
            return
        for inst in program.processes:
            if inst.state == ProcessState.STOPPED:
                self._start_instance(program, inst)

    def _start_instance(self, program, inst):
        use_pty = getattr(program.config, 'attachable', False)

        master_fd = None
        slave_fd = None
        if use_pty:
            master_fd, slave_fd = pty.openpty()

        pid = os.fork()

        if pid == 0:
            # ── ENFANT ──────────────────────────────────────────
            try:
                # 1. Changer d'utilisateur si spécifié
                user = getattr(program.config, 'user', None)
                if user:
                    try:
                        pw = pwd.getpwnam(user)
                        os.setgid(pw.pw_gid)
                        os.setuid(pw.pw_uid)
                        os.environ['HOME'] = pw.pw_dir
                        os.environ['USER'] = pw.pw_name
                        os.environ['LOGNAME'] = pw.pw_name
                    except KeyError:
                        print(f"[ERROR] User '{user}' not found, running as current user", flush=True)
                    except PermissionError:
                        print(f"[ERROR] Cannot switch to user '{user}' (not root?), running as current user", flush=True)

                # 2. Redirections I/O
                if use_pty:
                    # Ferme le master dans l'enfant, branche le slave sur stdin/stdout/stderr
                    os.close(master_fd)
                    os.dup2(slave_fd, 0)
                    os.dup2(slave_fd, 1)
                    os.dup2(slave_fd, 2)
                    if slave_fd > 2:
                        os.close(slave_fd)
                else:
                    if program.config.stdout:
                        fd_out = os.open(program.config.stdout, os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o644)
                        os.dup2(fd_out, 1)
                        os.close(fd_out)
                    if program.config.stderr:
                        fd_err = os.open(program.config.stderr, os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o644)
                        os.dup2(fd_err, 2)
                        os.close(fd_err)

                # 3. Répertoire de travail
                if getattr(program.config, 'workingdir', None):
                    os.chdir(program.config.workingdir)

                # 4. Umask
                if getattr(program.config, 'umask', None) is not None:
                    os.umask(program.config.umask)

                # 5. Variables d'environnement
                if getattr(program.config, 'env', None):
                    os.environ.update(program.config.env)

                # 6. Exec
                os.execv("/bin/sh", ["sh", "-c", program.config.cmd])

            except Exception as e:
                print(f"[CHILD] Failed to exec '{program.config.cmd}': {e}", flush=True)
                os._exit(1)

        else:
            # ── PARENT ──────────────────────────────────────────
            if use_pty:
                os.close(slave_fd)           # Le parent n'a pas besoin du slave
                inst.is_attachable = True
                if self.pty_manager is not None:
                    self.pty_manager.register(pid, master_fd)
                else:
                    self.log(f"[WARNING] pty_manager not set, attach will not work for pid {pid}", level="WARNING")
            inst.mark_started(pid)
            self.log(f"Started '{program.config.name}' with pid {pid}")

    def stop_program(self, name: str):
        program = self.programs.get(name)
        if not program:
            self.log(f"Program '{name}' not found")
            return
        for inst in program.processes:
            if inst.state == ProcessState.RUNNING and inst.pid:
                pid = inst.pid
                self.manual_stop_pids.add(pid)
                try:
                    signal_to_send = getattr(program.config, "stopsignal", signal.SIGTERM)
                    os.kill(pid, signal_to_send)
                except ProcessLookupError:
                    pass
                inst.state = ProcessState.STOPPED
                inst.stop_reason = "user"
                self.log(f"Stopped '{name}' pid={pid}")

    def restart_program(self, name: str):
        self.stop_program(name)
        self.start_program(name)

    def get_status(self):
        self.process_exited()
        status_lines = []
        for prog in self.programs.values():
            running = sum(1 for inst in prog.processes if inst.state == ProcessState.RUNNING)
            total = len(prog.processes)
            retries = sum(inst.retry_count for inst in prog.processes)
            line = f"{prog.config.name}: {'RUNNING' if running else 'STOPPED'} ({running}/{total}) retries={retries}"
            status_lines.append(line)
        return "\n".join(status_lines)

    def update_status(self):
        self.process_exited()

    # =========================
    # SIGCHLD
    # =========================

    def handle_sigchld(self, signum, frame):
        while True:
            try:
                pid, status = os.waitpid(-1, os.WNOHANG)
                if pid == 0:
                    break
                exit_code = os.WEXITSTATUS(status) if os.WIFEXITED(status) else None
                self._exited_pids.append((pid, exit_code))
            except ChildProcessError:
                break

    def process_exited(self):
        while self._exited_pids:
            pid, exit_code = self._exited_pids.pop(0)

            matched_inst = None
            matched_prog = None
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

            # Nettoyer le PTY si le process était attachable
            if self.pty_manager and pid in self.pty_manager.sessions:
                try:
                    os.close(self.pty_manager.sessions.pop(pid))
                except OSError:
                    pass

            self.log(
                f"[INSTANCE] program={prog.config.name} pid={pid} "
                f"state={inst.state} stop_reason={inst.stop_reason}", level="DEBUG"
            )

            starttime = getattr(prog.config, "starttime", 0)
            retries = getattr(prog.config, "startretries", 0)
            exitcodes = getattr(prog.config, "exitcodes", [0])
            now = time.time()
            alive_time = (now - inst.start_time) if inst.start_time else 0

            self.log(
                f"[LIFETIME] program={prog.config.name} pid={pid} "
                f"alive_time={alive_time:.2f}s starttime={starttime}", level="DEBUG"
            )

            restart_needed = False

            if exit_code not in exitcodes and alive_time < starttime:
                if inst.retry_count < retries:
                    inst.retry_count += 1
                    self.log(f"Retrying '{prog.config.name}' attempt {inst.retry_count}/{retries}")
                    restart_needed = True
                else:
                    self.log(f"Max retries reached for '{prog.config.name}'")

            elif prog.config.autorestart == "always":
                restart_needed = True

            elif prog.config.autorestart == "unexpected":
                if exit_code not in exitcodes or alive_time < starttime:
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
                inst.state = ProcessState.STOPPED  # reset pour que _start_instance accepte l'instance
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
              
                    was_manually_stopped = all(inst.stop_reason == "user" for inst in old_prog.processes)

                    if old_prog.config.autostart and not was_manually_stopped:
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
            a.starttime == b.starttime and
            a.startretries == b.startretries and
            a.exitcodes == b.exitcodes and
            a.stopsignal == b.stopsignal and
            a.stoptime == b.stoptime and
            getattr(a, "attachable", False) == getattr(b, "attachable", False) and
            getattr(a, "stdout", None) == getattr(b, "stdout", None) and
            getattr(a, "stderr", None) == getattr(b, "stderr", None) and
            getattr(a, "env", None) == getattr(b, "env", None) and
            getattr(a, "workingdir", None) == getattr(b, "workingdir", None) and
            getattr(a, "umask", None) == getattr(b, "umask", None) and
            getattr(a, "user", None) == getattr(b, "user", None)
        )
    # =========================
    # SIGHUP handler
    # =========================

    def handle_sighup(self, signum, frame):
        self.reload_requested = True