from utils.enums import ProcessState  # Importe les états possibles d’un processus
import time  # Module pour gérer le temps

class ProcessInstance:  # Classe représentant une instance d’un programme
    def __init__(self):  # Constructeur
        self.pid = None  # PID du processus (None au début)
        self.state = ProcessState.STOPPED  # État initial = STOPPED
        self.exited_flag = False  # Indique si le process s’est terminé
        self.exit_code = None  # Code de sortie du processus
        self.start_time = None      # Timestamp du moment où le process a été lancé
        self.retry_count = 0        # Nombre de tentatives de redémarrage
        self.stop_reason = None  # Raison de l’arrêt (optionnel)
        self.pty_master_fd = None  # File descriptor pour un pseudo-terminal (si utilisé)
        self.is_attachable = False  # Indique si on peut s’attacher au process
        self.is_attached = False  # Indique si on est actuellement attaché au process

    def mark_started(self, pid):  # Méthode appelée quand le process démarre
        self.pid = pid  # Enregistre le PID
        self.state = ProcessState.RUNNING  # Passe l’état à RUNNING
        self.exited_flag = False  # Reset le flag de sortie
        self.start_time = time.time()  # Enregistre le timestamp actuel
        self.exit_code = None  # Reset le code de sortie

    def mark_exited(self, exit_code=None, manual=False):  # Méthode appelée quand le process s’arrête
        self.state = ProcessState.STOPPED  # Passe l’état à STOPPED
        self.exited_flag = True  # Marque que le process est terminé
        self.exit_code = exit_code  # Enregistre le code de sortie (si fourni)
        self.manual_stop = manual  # Indique si l’arrêt est manuel ou non

        # on ne reset start_time ici, car il sert pour le calcul de alive_time
        # il sera réinitialisé uniquement si on relance le process