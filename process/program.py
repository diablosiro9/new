from process.instance import ProcessInstance  
from config.program_config import ProgramConfig 

class Program:  
    def __init__(self, config: ProgramConfig): 
        self.config = config  
        self.processes = [  
            ProcessInstance()  
            for _ in range(config.numprocs) 
        ]