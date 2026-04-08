import os
import socket
import threading
from socket_protocol import handle_command
from logger import log

SOCKET_PATH = "/tmp/taskmaster.sock"

class SocketServer(threading.Thread):
    def __init__(self, manager):
        super().__init__(daemon=True)
        self.manager = manager
        self.running = True

        if os.path.exists(SOCKET_PATH):
            os.remove(SOCKET_PATH)

        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.bind(SOCKET_PATH)
        self.server.listen(5)

        log("[Socket] Listening on /tmp/taskmaster.sock")

    def run(self):
        while self.running:
            try:
                conn, _ = self.server.accept()

                data = conn.recv(1024)
                if not data:
                    conn.close()
                    continue

                command = data.decode().strip()
                log(f"[Socket] Command received: {command}")

                # --- ATTACH ---
                if command.startswith("attach"):
                    parts = command.split()
                    if len(parts) < 2:
                        conn.sendall(b"ERR usage: attach <program[:index]>\n")
                        conn.close()
                        continue

                    target = parts[1]

                    # Parse optionnel program:index
                    if ":" in target:
                        prog_name, idx_str = target.split(":", 1)
                        try:
                            index = int(idx_str)
                        except ValueError:
                            conn.sendall(b"ERR invalid instance index\n")
                            conn.close()
                            continue
                    else:
                        prog_name = target
                        index = None  # Première instance RUNNING attachable

                    program = self.manager.programs.get(prog_name)
                    if not program:
                        conn.sendall(b"ERR program not found\n")
                        conn.close()
                        continue

                    # Chercher l'instance cible
                    attached = False
                    if index is not None:
                        # Instance précise demandée
                        if index >= len(program.processes):
                            conn.sendall(b"ERR instance index out of range\n")
                            conn.close()
                            continue
                        inst = program.processes[index]
                        if inst.state.name != "RUNNING":
                            conn.sendall(b"ERR instance not running\n")
                            conn.close()
                            continue
                        if not getattr(inst, 'is_attachable', False):
                            conn.sendall(b"ERR instance not attachable (not started with PTY)\n")
                            conn.close()
                            continue
                        self.manager.pty_manager.attach(inst.pid, conn)
                        attached = True
                    else:
                        # Première instance RUNNING + attachable
                        for inst in program.processes:
                            if inst.state.name == "RUNNING" and getattr(inst, 'is_attachable', False):
                                self.manager.pty_manager.attach(inst.pid, conn)
                                attached = True
                                break

                    if not attached:
                        conn.sendall(b"ERR no running attachable instance\n")
                        conn.close()

                    # Dans tous les cas on passe à la connexion suivante.
                    # Si attached=True, conn est maintenant gérée par le thread bridge du PTYManager.
                    continue

                # --- COMMANDES NORMALES ---
                response = handle_command(self.manager, command)
                conn.sendall((response + "\n").encode())

                if command.strip() == "shutdown":
                    log("[Socket] Shutdown requested")
                    self.running = False
                    self.cleanup()
                    os._exit(0)

                conn.close()

            except Exception as e:
                log(f"[Socket] Error: {e}", level="ERROR")

    def cleanup(self):
        try:
            self.server.close()
            os.remove(SOCKET_PATH)
        except Exception:
            pass