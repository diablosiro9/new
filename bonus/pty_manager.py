import os  # Module pour interactions système (fichiers, process, etc.)
import pty  # Module pour gérer les pseudo-terminals
import tty  # Module pour manipuler les modes de terminal
import termios  # Module bas niveau pour configuration terminal
import select  # Permet de surveiller plusieurs flux I/O
import threading  # Permet l'exécution concurrente via threads

class PTYManager:  # Classe qui gère les sessions attachables via PTY
    def __init__(self):  # Constructeur de la classe
        self.sessions = {}  # Dictionnaire pid -> master_fd (PTY associé)
        self.attachable = set()  # Ensemble (non utilisé ici)
        self.attached = set()  # Ensemble des PIDs actuellement attachés

    def create_pty(self):  # Méthode pour créer un pseudo-terminal
        return pty.openpty()  # Retourne un tuple (master_fd, slave_fd)

    def register(self, pid, master_fd):  # Enregistre un process avec son PTY
        self.sessions[pid] = master_fd  # Associe le PID à son file descriptor master

    def attach(self, pid, client_socket):  # Attache un client à un process
        if pid not in self.sessions:  # Vérifie si le PID existe
            client_socket.sendall(b"Process not attachable\n")  # Informe le client
            return  # Stop si non attachable

        master_fd = self.sessions[pid]  # Récupère le PTY associé au process

        client_socket.sendall(b"Attached. Ctrl+X or type 'detach' to detach\n")  # Message d'information au client

        def bridge():  # Fonction interne qui fait le lien client ↔ process
            try:  # Début gestion d'erreurs
                buffer = b""  # Buffer pour accumuler les entrées client

                while True:  # Boucle principale
                    rlist, _, _ = select.select([client_socket, master_fd], [], [])  # Attend une activité sur l’un des deux

                    if client_socket in rlist:  # Si le client envoie des données
                        data = client_socket.recv(1024)  # Lit les données
                        if not data:  # Si connexion fermée
                            break  # Sort de la boucle

                        buffer += data  # Ajoute au buffer

                        # --- DETACH via Ctrl+X ---
                        if b"\x18" in buffer:  # Ctrl+X détecté
                            break  # Déconnexion

                        # --- DETACH via command ---
                        if b"\n" in buffer:  # Ligne complète reçue
                            line, buffer = buffer.split(b"\n", 1)  # Sépare la ligne
                            if line.strip() == b"detach":  # Si commande detach
                                break  # Déconnexion
                            os.write(master_fd, line + b"\n")  # Envoie au process
                        continue  # Continue la boucle

                    if master_fd in rlist:  # Si le process écrit
                        data = os.read(master_fd, 1024)  # Lit la sortie
                        if not data:  # Si rien (process terminé)
                            break  # Sort
                        client_socket.sendall(data)  # Envoie au client

            except (BrokenPipeError, ConnectionResetError):  # Erreurs de connexion
                pass  # Ignorées
            except Exception:  # Toute autre erreur
                pass  # Ignorée
            finally:  # Nettoyage
                self.attached.discard(pid)  # Retire le PID des attachés
                try:  # Tentative d'envoi message final
                    client_socket.sendall(b"\nDetached.\n")  # Informe le client
                except:  # Si échec
                    pass  # Ignore

        t = threading.Thread(target=bridge, daemon=True)  # Création d’un thread pour gérer la communication
        t.start()  # Démarrage du thread