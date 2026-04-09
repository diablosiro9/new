import os
import sys 
from config.loader import ConfigLoader
from process.manager import ProcessManager
from shell.control import ControlShell 

PID_FILE = "/tmp/taskmaster.pid" 

def main(): 
    if len(sys.argv) != 2: 
        print("Usage: python3 main.py <config.yaml>") 
        return  

    config_path = sys.argv[1] 

    with open(PID_FILE, "w") as f: 
        f.write(str(os.getpid())) 
    print(f"[TaskMaster] PID = {os.getpid()}") 

    manager = ProcessManager(config_path=config_path)  

    loader = ConfigLoader(config_path)
    programs = loader.load()
    for program in programs:
        manager.add_program(program)
        if program.config.autostart:  
            manager.start_program(program.config.name) 

    manager.update_status()
    shell = ControlShell(manager) 
    try:
        shell.run() 
    except KeyboardInterrupt: 
        print("\n[TaskMaster] Interrupted by user, shutting down cleanly") 
        sys.exit(0) 


if __name__ == "__main__": 
    main()