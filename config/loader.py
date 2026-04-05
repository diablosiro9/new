import yaml
from config.program_config import ProgramConfig  # Importe la classe de configuration d’un programme
from process.program import Program  # Importe la classe Program (qui contient les instances)

class ConfigLoader:  # Classe responsable de charger et parser le fichier de config
    def __init__(self, path: str):  # Constructeur avec chemin du fichier YAML
        self.path = path  # Stocke le chemin du fichier

    def load(self):  # Méthode principale pour charger la config
        with open(self.path, "r") as f:  # Ouvre le fichier en lecture
            data = yaml.safe_load(f)  # Charge le YAML en dictionnaire Python

        programs = []  # Liste qui contiendra les objets Program

        for name, cfg in data.get("programs", {}).items():  # Parcourt chaque programme dans la clé "programs"
            program_cfg = ProgramConfig(  # Crée un objet de configuration
                name=name,  # Nom du programme (clé du YAML)
                cmd=cfg["cmd"],  # Commande à exécuter (obligatoire)
                user=cfg.get("user"),  # Utilisateur (optionnel)
                numprocs=cfg.get("numprocs", 1),  # Nombre de process (1 par défaut)
                autostart=cfg.get("autostart", False),  # Démarrage auto ou non
                autorestart=cfg.get("autorestart", "never"),  # Politique de restart
                exitcodes=self._parse_exitcodes(cfg.get("exitcodes")),  # Parse les exit codes
                startretries=cfg.get("startretries", 3),  # Nombre de retries
                starttime=cfg.get("starttime", 1),  # Temps minimum pour considérer un start réussi
                stopsignal=self._parse_signal(cfg.get("stopsignal", "TERM")),  # Convertit signal texte → signal réel
                stoptime=cfg.get("stoptime", 10),  # Temps avant arrêt forcé
                stdout=cfg.get("stdout"),  # Fichier stdout
                stderr=cfg.get("stderr"),  # Fichier stderr
                env=cfg.get("env"),  # Variables d’environnement
                workingdir=cfg.get("workingdir"),  # Répertoire de travail
                umask=self._parse_umask(cfg.get("umask")),  # Convertit umask
                attachable=cfg.get("attachable", False)  # Si attach possible
            )
            programs.append(Program(program_cfg))  # Crée un Program et l’ajoute à la liste

        return programs  # Retourne la liste des programmes chargés

    def _parse_signal(self, sig):  # Convertit un signal YAML en signal Unix
        import signal  # Importe module signal localement

        if isinstance(sig, int):  # Si déjà un entier
            return sig  # Retourne tel quel

        return getattr(signal, f"SIG{sig}", signal.SIGTERM)  
        # Transforme "TERM" → signal.SIGTERM
        # Si inconnu → fallback SIGTERM

    def _parse_umask(self, umask):  # Convertit la valeur umask
        if umask is None:  # Si non défini
            return None  # Retourne None

        # YAML peut fournir un int (ex: 022 -> 18)
        if isinstance(umask, int):  # Si déjà converti en entier
            return umask  # Retourne directement

        # string explicite ("022")
        return int(umask, 8)  # Convertit une string octale en entier base 8

    def _parse_exitcodes(self, exitcodes):  # Normalise les exit codes
        if exitcodes is None:  # Si non défini
            return [0]  # Par défaut 0 = succès

        # YAML: exitcodes: 0
        if isinstance(exitcodes, int):  # Si un seul entier
            return [exitcodes]  # Le transforme en liste

        # YAML: exitcodes: [0, 2]
        if isinstance(exitcodes, list):  # Si déjà une liste
            return exitcodes  # Retourne tel quel

        # fallback défensif
        return [int(exitcodes)]  # Convertit en int puis liste