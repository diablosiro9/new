import os  # Module système (fork, fichiers, PID, etc.)
import sys  # Accès aux arguments et contrôle du programme
import time  # Gestion du temps (sleep)
import signal  # Gestion des signaux Unix
import atexit  # Permet d’exécuter du code à la fin du programme
import fcntl  # Gestion des locks fichiers (éviter plusieurs daemons)
from socket_server import SocketServer  # Serveur socket pour communication client
from bonus.manager_wrapper import ManagerWrapper  # Wrapper autour du ProcessManager

PID_FILE = "/tmp/taskmaster_daemon.pid"  # Fichier pour stocker le PID du daemon
LOCK_FILE = "/tmp/taskmaster_daemon.lock"  # Fichier de lock pour éviter double instance
LOG_FILE = os.path.join(os.path.dirname(__file__), "logs/daemon.log")  # Fichier de log du daemon

IS_DAEMON = False  # Flag global indiquant si on est en mode daemon

def daemonize(log_file=None):  # Fonction pour transformer le process en daemon
    global IS_DAEMON  # Permet de modifier la variable globale

    if os.fork() > 0:  # Premier fork
        sys.exit(0)  # Le parent quitte

    os.setsid()  # Crée une nouvelle session (détache du terminal)

    if os.fork() > 0:  # Deuxième fork (évite réattachement terminal)
        sys.exit(0)

    os.umask(0)  # Reset umask

    if log_file:  # Si fichier de log fourni
        os.makedirs(os.path.dirname(log_file), exist_ok=True)  # Crée dossier logs si besoin
        log_f = open(log_file, "a+", buffering=1)  # Ouvre fichier log en append (line buffered)
        os.dup2(log_f.fileno(), 1)  # Redirige stdout vers log
        os.dup2(log_f.fileno(), 2)  # Redirige stderr vers log

    with open(PID_FILE, "w") as f:  # Écrit le PID dans un fichier
        f.write(str(os.getpid()))

    atexit.register(lambda: os.path.exists(PID_FILE) and os.remove(PID_FILE))  # Supprime PID à la sortie
    atexit.register(lambda: os.path.exists(LOCK_FILE) and os.remove(LOCK_FILE))  # Supprime lock à la sortie

    IS_DAEMON = True  # Active le mode daemon

def acquire_lock():  # Empêche plusieurs instances du daemon
    fd = os.open(LOCK_FILE, os.O_CREAT | os.O_RDWR)  # Ouvre/crée fichier lock
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)  # Lock exclusif non bloquant
    except BlockingIOError:  # Si lock déjà pris
        print("[TaskMaster] Daemon already running")  # Message erreur
        sys.exit(1)  # Quitte
    return fd  # Retourne descripteur

def main():  # Fonction principale
    if len(sys.argv) < 2:  # Vérifie arguments
        print("Usage: daemon.py <config.yaml> [--no-daemon]")
        sys.exit(1)

    config_path = sys.argv[1]  # Récupère fichier config
    no_daemon = len(sys.argv) == 3 and sys.argv[2] == "--no-daemon"  # Mode debug sans daemon

    lock_fd = acquire_lock()  # Prend le lock

    if not no_daemon:  # Si mode daemon actif
        daemonize(log_file=LOG_FILE)  # Lance en daemon

    manager = ManagerWrapper(config_path, is_daemon=IS_DAEMON)  # Initialise manager wrapper
    manager.manager.log("[Daemon] Loading configuration without autostart")  # Log

    from config.loader import ConfigLoader  # Import local
    from process.instance import ProcessInstance
    from utils.enums import ProcessState

    # Charger la config
    loader = ConfigLoader(config_path)  # Initialise loader
    programs = loader.load()  # Charge programmes

    for program in programs:  # Ajoute chaque programme
        manager.add_program(program)

    # # 1️⃣ Initialiser toutes les instances avant autostart
    # for prog in manager.manager.programs.values():  # Parcourt programmes
    #     prog.processes = [ProcessInstance() for _ in range(prog.config.numprocs)]  # Crée instances
    #     for inst in prog.processes:
    #         inst.state = ProcessState.STOPPED  # Met état STOPPED

    # 2️⃣ Lancer les programmes avec autostart
    for prog in manager.manager.programs.values():
        if prog.config.autostart:  # Si autostart activé
            print(f"[DEBUG] Starting program {prog.config.name} as {prog.config.user}")
            manager.start_program(prog.config.name)  # Démarre

    manager.send_alert("daemon_started", {"pid": os.getpid()})  # Envoie event

    # Socket server pour communication
    socket_server = SocketServer(manager)  # Initialise serveur socket
    socket_server.start()  # Démarre serveur

    # Gestion SIGTERM / SIGHUP
    def handle_term(signum, frame):
        manager.send_alert("daemon_stopping", {"signal": signum})
        manager.log("[Daemon] SIGTERM received, stopping all programs...")
        for prog in manager.programs.values():  # ← manager ici est un ManagerWrapper
            manager.stop_program(prog.config.name)
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_term)  # Associe SIGTERM
    signal.signal(signal.SIGHUP, lambda s,f: manager.reload_config())  # Reload config

    # Boucle principale
    while True:
        try:
            manager.process_exited()  # Gère les process terminés
            time.sleep(0.5)  # Pause
        except Exception as e:
            manager.send_alert("daemon_exception", {"error": str(e)})  # Alerte
            manager.log(f"[Daemon] Exception caught: {e}", level="ERROR")  # Log erreur

if __name__ == "__main__":  # Si exécuté directement
    main()  # Lance main