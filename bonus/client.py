import socket  # Module pour communication réseau (ici Unix socket)
import sys  # Accès aux arguments
import tty  # Mode terminal brut
import termios  # Gestion paramètres terminal
import sys  # (import doublon, mais sans effet)
import os  # Accès système
import select  # Permet d’écouter plusieurs flux (stdin + socket)

SOCKET_PATH = "/tmp/taskmaster.sock"  # Chemin du socket Unix
def interactive_mode(sock):
    old_settings = termios.tcgetattr(sys.stdin.fileno())
    try:
        tty.setraw(sys.stdin.fileno())

        while True:
            rlist, _, _ = select.select([sys.stdin, sock], [], [])

            if sys.stdin in rlist:
                data = os.read(sys.stdin.fileno(), 1024)
                if not data:
                    break
                sock.sendall(data)

            if sock in rlist:
                try:
                    data = sock.recv(4096)
                    if not data:
                        break
                    os.write(sys.stdout.fileno(), data)
                    # Détecte la fin de session envoyée par le serveur
                    if b"\r\nDetached.\r\n" in data:
                        break
                except (ConnectionResetError, OSError):
                    break
    finally:
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_settings)
        # Assure un retour propre à la ligne après raw mode
        print()
        
def main():  # Fonction principale
    if len(sys.argv) < 2:  # Vérifie arguments
        print("Usage: client.py <command>")
        sys.exit(1)

    command = " ".join(sys.argv[1:])  # Construit commande complète

    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)  # Crée socket Unix
    client.settimeout(2)  # Timeout de 2 secondes

    try:
        client.connect(SOCKET_PATH)  # Connexion au daemon
    except (FileNotFoundError, ConnectionRefusedError):  # Si daemon absent
        print("ERR daemon not running or socket closed")
        sys.exit(1)

    if command.startswith("attach"):  # Si commande attach
        program = command.split()[1]  # Récupère nom programme
        client.sendall(f"attach {program}\n".encode())  # Envoie commande
        interactive_mode(client)  # Lance mode interactif
        return

    client.sendall((command + "\n").encode())  # Envoie commande simple

    try:
        response = client.recv(4096).decode()  # Lit réponse
        print(response.strip())  # Affiche
    except socket.timeout:
        print("ERR timeout: no response from daemon")  # Timeout
    except ConnectionResetError:
        print("Connection closed by daemon")  # Connexion coupée

    client.close()  # Ferme socket

if __name__ == "__main__":  # Si exécuté directement
    main()  # Lance programme