import os  # Module pour interagir avec le système (fork, fichiers, processus, etc.)
import signal  # Module pour envoyer des signaux aux processus (SIGTERM, etc.)
from process.program import Program  # Importe la classe Program (représente un programme à exécuter)
from process.instance import ProcessInstance  # Importe la classe ProcessInstance (une instance d’un programme)
from utils.enums import ProcessState  # Importe les états possibles des processus (RUNNING, STOPPED, etc.)

class BaseProcessManager:  # Déclare la classe qui gère les processus
    def __init__(self, config_path=None):  # Constructeur avec chemin de config optionnel
        self.programs = {}  # Dictionnaire qui stocke les programmes (clé = nom, valeur = objet Program)
        self.config_path = config_path  # Stocke le chemin du fichier de configuration

    def add_program(self, program: Program):  # Méthode pour ajouter un programme
        self.programs[program.config.name] = program  # Ajoute le programme dans le dictionnaire avec son nom

    def start_program(self, name, log=True):  # Méthode pour démarrer un programme
        program = self.programs.get(name)  # Récupère le programme par son nom
        if not program:  # Si le programme n'existe pas
            return  # Quitte la fonction

        for instance in program.processes:  # Parcourt toutes les instances du programme
            if instance.state == ProcessState.STOPPED:  # Si l’instance est arrêtée
                pid = os.fork()  # Crée un nouveau processus (fork)

                if pid == 0:  # Si on est dans le processus enfant
                    # Child
                    try:
                        if program.config.stdout:  # Si un fichier stdout est défini
                            fd_out = os.open(program.config.stdout, os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o644)  # Ouvre/crée le fichier
                            os.dup2(fd_out, 1)  # Redirige la sortie standard (stdout) vers ce fichier
                            os.close(fd_out)  # Ferme le descripteur de fichier

                        if program.config.stderr:  # Si un fichier stderr est défini
                            fd_err = os.open(program.config.stderr, os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o644)  # Ouvre/crée le fichier
                            os.dup2(fd_err, 2)  # Redirige la sortie d’erreur (stderr)
                            os.close(fd_err)  # Ferme le descripteur

                        if program.config.workingdir:  # Si un dossier de travail est défini
                            os.chdir(program.config.workingdir)  # Change le répertoire courant

                        if program.config.umask is not None:  # Si un umask est défini
                            os.umask(program.config.umask)  # Applique les permissions par défaut

                        os.execv("/bin/sh", ["sh", "-c", program.config.cmd])  # Exécute la commande via un shell
                    except Exception as e:  # Si une erreur survient
                        print(f"Failed to exec {program.config.cmd}: {e}")  # Affiche l’erreur
                        os._exit(1)  # Quitte immédiatement le processus enfant avec code d’erreur

                else:  # Si on est dans le processus parent
                    instance.mark_started(pid)  # Met à jour l’instance avec le PID du processus enfant
                    if log:  # Si logging activé
                        print(f"Started '{name}' with pid {pid}")  # Affiche un message

    def stop_program(self, name, log=True):  # Méthode pour arrêter un programme
        prog = self.programs.get(name)  # Récupère le programme
        if not prog:  # Si inexistant
            return  # Quitte

        for inst in prog.processes:  # Parcourt toutes les instances
            if inst.state == ProcessState.RUNNING:  # Si en cours d’exécution
                try:
                    os.kill(inst.pid, signal.SIGTERM)  # Envoie un signal SIGTERM (arrêt propre)
                    os.waitpid(inst.pid, 0)  # Attend la fin du processus
                    print(f"Stopped '{name}' pid={inst.pid}")  # Affiche message
                except Exception:  # Si erreur (process déjà mort, etc.)
                    pass  # Ignore l’erreur

                inst.mark_exited()  # Met à jour l’état de l’instance (STOPPED)