import os  # Module pour interactions avec le système de fichiers et OS
import socket  # Module pour la communication réseau (ici sockets Unix)
import threading  # Module pour gérer les threads (exécution concurrente)
from socket_protocol import handle_command  # Fonction qui traite les commandes reçues
from logger import log  # Fonction de logging personnalisée

SOCKET_PATH = "/tmp/taskmaster.sock"  # Chemin du socket Unix utilisé pour la communication

class SocketServer(threading.Thread):  # Classe serveur qui tourne dans un thread
    def __init__(self, manager):  # Constructeur prenant un manager en paramètre
        super().__init__(daemon=True)  # Initialise le thread en mode daemon (s'arrête avec le programme principal)
        self.manager = manager  # Stocke le manager pour accéder aux programmes
        self.running = True  # Flag pour contrôler la boucle principale du serveur

        if os.path.exists(SOCKET_PATH):  # Vérifie si un ancien socket existe déjà
            os.remove(SOCKET_PATH)  # Supprime l'ancien socket pour éviter conflit

        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)  # Crée un socket Unix en mode TCP
        self.server.bind(SOCKET_PATH)  # Lie le socket à un chemin fichier
        self.server.listen(5)  # Met le serveur en écoute avec une file d'attente de 5 connexions

        log("[Socket] Listening on /tmp/taskmaster.sock")  # Log indiquant que le serveur est prêt

    def run(self):  # Méthode exécutée automatiquement quand le thread démarre
        while self.running:  # Boucle principale tant que le serveur est actif
            try:  # Bloc de gestion des erreurs
                conn, _ = self.server.accept()  # Accepte une nouvelle connexion client

                data = conn.recv(1024)  # Lit jusqu'à 1024 bytes envoyés par le client
                if not data:  # Si aucune donnée reçue
                    conn.close()  # Ferme la connexion
                    continue  # Passe à l'itération suivante

                command = data.decode().strip()  # Décode les bytes en string et supprime espaces
                log(f"[Socket] Command received: {command}")  # Log de la commande reçue

                # --- ATTACH ---
                if command.startswith("attach"):  # Vérifie si la commande est un attach
                    parts = command.split()  # Découpe la commande en parties
                    if len(parts) != 2:  # Vérifie le format attendu
                        conn.sendall(b"ERR usage: attach <program>\n")  # Envoie message d'erreur
                        conn.close()  # Ferme la connexion
                        continue  # Passe à la suite

                    prog_name = parts[1]  # Récupère le nom du programme
                    program = self.manager.programs.get(prog_name)  # Récupère le programme depuis le manager

                    if not program:  # Si le programme n'existe pas
                        conn.sendall(b"Program not found\n")  # Envoie erreur
                        conn.close()  # Ferme connexion
                        continue  # Continue la boucle

                    for inst in program.processes:  # Parcourt toutes les instances du programme
                        if inst.state.name == "RUNNING" and getattr(inst, "is_attachable", False):  # Vérifie état + attachable
                            self.manager.pty_manager.attach(inst.pid, conn)  # Attache le client au process via PTY
                            return  # Sort de la méthode run (le thread est "pris" par l'attach)

                    conn.sendall(b"No running attachable instance\n")  # Aucun process attachable trouvé
                    conn.close()  # Ferme la connexion
                    continue  # Passe à l'itération suivante

                # --- COMMANDES NORMALES ---
                response = handle_command(self.manager, command)  # Traite la commande via le handler
                conn.sendall((response + "\n").encode())  # Envoie la réponse au client

                if command.strip() == "shutdown":  # Si commande shutdown
                    log("[Socket] Shutdown requested")  # Log de l'arrêt
                    self.running = False  # Arrête la boucle serveur
                    self.cleanup()  # Nettoie les ressources
                    os._exit(0)  # Termine immédiatement le processus

                conn.close()  # Ferme la connexion client

            except Exception as e:  # Capture toute erreur
                log(f"[Socket] Error: {e}", level="ERROR")  # Log l'erreur avec niveau ERROR

    def cleanup(self):  # Méthode de nettoyage du serveur
        try:  # Tentative de nettoyage
            self.server.close()  # Ferme le socket serveur
            os.remove(SOCKET_PATH)  # Supprime le fichier socket
        except Exception:  # Si une erreur survient
            pass  # Ignore silencieusement