from process.instance import ProcessInstance  # Importe la classe représentant une instance de process
from config.program_config import ProgramConfig  # Importe la config d’un programme

class Program:  # Classe représentant un programme (peut avoir plusieurs instances)
    def __init__(self, config: ProgramConfig):  # Constructeur avec config
        self.config = config  # Stocke la configuration du programme
        self.processes = [  # Crée une liste d’instances
            ProcessInstance()  # Crée une nouvelle instance
            for _ in range(config.numprocs)  # Répète selon le nombre de processus voulu
        ]