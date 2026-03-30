from typing import Optional, Dict, List  # Importe des types pour annoter les variables (optionnel, dict, liste)

class ProgramConfig:  # Classe qui représente la configuration d’un programme
    def __init__(  # Constructeur de la classe
        self,
        name: str,  # Nom du programme (obligatoire)
        cmd: str,  # Commande à exécuter (ex: "python app.py")
        user: Optional[str] = None,  # Utilisateur sous lequel lancer le programme (optionnel)
        numprocs: int = 1,  # Nombre d’instances à lancer
        autostart: bool = False,  # Indique si le programme démarre automatiquement
        autorestart: str = "never",  # Politique de redémarrage ("never", "always", "unexpected")
        exitcodes: Optional[List[int]] = None,  # Codes de sortie considérés comme normaux
        startretries: int = 3,  # Nombre de tentatives de redémarrage
        starttime: int = 1,  # Temps minimum pour considérer un démarrage réussi
        stopsignal: int = 15,  # Signal utilisé pour arrêter le process (15 = SIGTERM)
        stoptime: int = 10,  # Temps maximum avant forcer l’arrêt
        stdout: Optional[str] = None,  # Fichier pour rediriger la sortie standard
        stderr: Optional[str] = None,  # Fichier pour rediriger les erreurs
        env: Optional[Dict[str, str]] = None,  # Variables d’environnement (clé=valeur)
        workingdir: Optional[str] = None,  # Répertoire de travail du programme
        umask: Optional[int] = None,  # Masque de permissions par défaut
        attachable: Optional[bool] = False,  # Indique si on peut s’attacher au process (ex: debug)
    ):
        self.name = name  # Stocke le nom du programme
        self.cmd = cmd  # Stocke la commande à exécuter
        self.user = user  # Stocke l’utilisateur (non utilisé ici mais prévu)
        self.numprocs = numprocs  # Stocke le nombre d’instances
        self.autostart = autostart  # Stocke l’option autostart
        self.autorestart = autorestart  # Stocke la politique de restart
        self.exitcodes = exitcodes or [0]  # Si None → met [0] par défaut
        self.startretries = startretries  # Nombre de tentatives
        self.starttime = starttime  # Temps minimum pour considérer le process stable
        self.stopsignal = stopsignal  # Signal utilisé pour arrêter
        self.stoptime = stoptime  # Temps avant kill forcé
        self.stdout = stdout  # Fichier de sortie standard
        self.stderr = stderr  # Fichier d’erreur
        self.env = env or {}  # Variables d’environnement (vide si None)
        self.workingdir = workingdir  # Répertoire de travail
        self.umask = umask  # Umask (permissions)
        self.attachable = attachable  # Indique si attach possible