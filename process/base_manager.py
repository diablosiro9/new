import os  
import signal  
from process.program import Program 
from process.instance import ProcessInstance 
from utils.enums import ProcessState 

class BaseProcessManager:
    def __init__(self, config_path=None):
        self.programs = {}  
        self.config_path = config_path  

    def add_program(self, program: Program):
        self.programs[program.config.name] = program  

    def start_program(self, name, log=True): 
        program = self.programs.get(name) 
        if not program:  
            return 

        for instance in program.processes: 
            if instance.state == ProcessState.STOPPED:  
                pid = os.fork()  

                if pid == 0: 
                  
                    try:
                        if program.config.stdout:  
                            fd_out = os.open(program.config.stdout, os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o644)  
                            os.dup2(fd_out, 1)  
                            os.close(fd_out)  

                        if program.config.stderr: 
                            fd_err = os.open(program.config.stderr, os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o644) 
                            os.dup2(fd_err, 2)  
                            os.close(fd_err)  

                        if program.config.workingdir:
                            os.chdir(program.config.workingdir)  

                        if program.config.umask is not None:
                            os.umask(program.config.umask)  

                        os.execv("/bin/sh", ["sh", "-c", program.config.cmd])  
                    except Exception as e: 
                        print(f"Failed to exec {program.config.cmd}: {e}")  
                        os._exit(1) 

                else:  
                    instance.mark_started(pid)  
                    if log:  
                        print(f"Started '{name}' with pid {pid}") 

    def stop_program(self, name, log=True):
        prog = self.programs.get(name) 
        if not prog:  
            return  

        for inst in prog.processes:  
            if inst.state == ProcessState.RUNNING:  
                try:
                    os.kill(inst.pid, signal.SIGTERM)  
                    os.waitpid(inst.pid, 0) 
                    print(f"Stopped '{name}' pid={inst.pid}") 
                except Exception:  
                    pass  

                inst.mark_exited() 