import os
import pty
import select
import threading
import socket

class PTYManager:
    def __init__(self):
        self.sessions = {}
        self.attached = set()

    def create_pty(self):
        return pty.openpty()

    def register(self, pid, master_fd):
        self.sessions[pid] = master_fd

    def attach(self, pid, client_socket):
        if pid not in self.sessions:
            client_socket.sendall(b"ERR process not found in PTY sessions\n")
            return

        if pid in self.attached:
            client_socket.sendall(b"ERR already attached to this process\n")
            return

        master_fd = self.sessions[pid]
        self.attached.add(pid)
        client_socket.sendall(b"Attached. Ctrl+X or type 'detach' to detach.\n")

        def bridge():
            input_buffer = b""
            try:
                while True:
                    try:
                        rlist, _, _ = select.select([client_socket, master_fd], [], [], 1.0)
                    except (ValueError, OSError):
                        break

                    if client_socket in rlist:
                        try:
                            data = client_socket.recv(1024)
                        except OSError:
                            break
                        if not data:
                            break

                        # Ctrl+X détache immédiatement
                        if b"\x18" in data:
                            break

                        # Accumule dans le buffer d'entrée
                        input_buffer += data

                        # Traite ligne par ligne
                        detach_requested = False
                        # Normalise \r et \r\n en \n
                        input_buffer = input_buffer.replace(b"\r\n", b"\n").replace(b"\r", b"\n")

                        while b"\n" in input_buffer:
                            line, input_buffer = input_buffer.split(b"\n", 1)
                            if line.strip() == b"detach":
                                detach_requested = True
                                break
                            else:
                                try:
                                    os.write(master_fd, line + b"\r\n")  # ← renvoie \r\n au shell PTY
                                except OSError:
                                    detach_requested = True
                                    break

                        if detach_requested:
                            break

                        # Forward ce qui reste (saisie partielle, pas encore \n)
                        if input_buffer and not detach_requested:
                            try:
                                os.write(master_fd, input_buffer)
                                input_buffer = b""
                            except OSError:
                                break

                    if master_fd in rlist:
                        try:
                            data = os.read(master_fd, 4096)
                        except OSError:
                            break
                        if not data:
                            break
                        try:
                            client_socket.sendall(data)
                        except OSError:
                            break

            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                self.attached.discard(pid)
                # \r\n pour reset le terminal + prompt explicite
                try:
                    client_socket.sendall(b"\r\nDetached.\r\n")
                    client_socket.shutdown(socket.SHUT_RDWR)  # ← ajout
                    client_socket.close()       
                except OSError:
                    pass
                # Signal de fin de session pour que le client rende la main
                # Si ton client écoute un sentinel, envoie-le ici
                # ex: client_socket.sendall(b"__DETACHED__\n")

        t = threading.Thread(target=bridge, daemon=True)
        t.start()
