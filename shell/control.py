from utils.enums import ProcessState
import time
import readline
import rlcompleter 
import os
import select
import sys

readline.parse_and_bind("bind ^I rl_complete")

HISTORY_FILE = os.path.expanduser("~/.taskmaster_history")  

class ControlShell: 
    def __init__(self, manager):  
        try:
            readline.read_history_file(HISTORY_FILE) 
        except FileNotFoundError:
            pass
        self.manager = manager  
        self.running = True 
        readline.set_history_length(100) 

        self.commands = ["start", "stop", "restart", "reload", "status", "exit"] 
        readline.parse_and_bind("tab: complete")  
        readline.set_completer(self.complete)  
        readline.parse_and_bind("set show-all-if-ambiguous on") 
        readline.parse_and_bind("set completion-ignore-case on") 
        readline.parse_and_bind("set completion-query-items 100") 
        self.manager.prompt_redraw = self._redraw_prompt
    
    def _redraw_prompt(self):
        sys.stdout.write("taskmaster> ")
        sys.stdout.flush()

    def complete(self, text, state): 
        buffer = readline.get_line_buffer()  
        parts = buffer.split()  

        if len(parts) == 1: 
            options = [c for c in self.commands if c.startswith(parts[0])] 
        elif len(parts) == 2 and parts[0] in ("start", "stop", "restart", "status"): 
            options = [
                name for name in self.manager.programs.keys() 
                if name.startswith(parts[1]) 
            ]
        else:
            options = []  

        try:
            return options[state] 
        except IndexError:  
            return None 


    def run(self):
        try:
            sys.stdout.write("taskmaster> ")
            sys.stdout.flush()
            while self.running:
                self.manager.process_exited()

                if self.manager.reload_requested:
                    self.manager.reload_requested = False
                    self.manager.log("[TaskMaster] SIGHUP received, reloading...", level="INFO")
                    self.manager.reload_config()

                ready, _, _ = select.select([sys.stdin], [], [], 0.5)
                if not ready:
                    continue

                try:
                    cmd = sys.stdin.readline()
                    if cmd == "": 
                        print()
                        for name in self.manager.programs.keys():
                            self.manager.stop_program(name)
                            self.manager.prompt_redraw = None
                        break
                    cmd = cmd.strip()
                except KeyboardInterrupt:
                    print()
                    for name in self.manager.programs.keys():
                        self.manager.stop_program(name)
                        self.manager.prompt_redraw = None
                    break

                if not cmd:
                    sys.stdout.write("taskmaster> ")
                    sys.stdout.flush()
                    continue

                readline.add_history(cmd)

                if cmd == "exit":
                    for name in self.manager.programs.keys():
                        self.manager.stop_program(name)
                    self.running = False
                    self.manager.prompt_redraw = None
                    continue 
                elif cmd.startswith("start "):
                    name = cmd.split(maxsplit=1)[1].strip()
                    self.manager.start_program(name)

                elif cmd.startswith("stop "):
                    name = cmd.split(maxsplit=1)[1].strip()
                    self.manager.stop_program(name)

                elif cmd.startswith("restart "):
                    name = cmd.split(maxsplit=1)[1].strip()
                    self.manager.restart_program(name)

                elif cmd.startswith("status"):
                    parts = cmd.split()
                    if len(parts) == 1:
                        for pname, program in self.manager.programs.items():
                            print(self.format_status(pname, program))
                    else:
                        pname = parts[1]
                        program = self.manager.programs.get(pname)
                        if not program:
                            print(f"Unknown program: {pname}")
                        else:
                            print(self.format_status(pname, program))

                elif cmd == "reload":
                    self.manager.reload_config()
                    continue

                else:
                    print(f"Unknown command: '{cmd}'")

                sys.stdout.write("taskmaster> ")
                sys.stdout.flush()

        finally:
            readline.write_history_file(HISTORY_FILE)
                    
    def format_status(self, name, program):
        running = [p for p in program.processes if p.state == ProcessState.RUNNING] 
        stopped = [p for p in program.processes if p.state == ProcessState.STOPPED]  

        retries = max((p.retry_count for p in program.processes), default=0)
        uptime = None 
        for p in running: 
            if p.start_time: 
                uptime = int(time.time() - p.start_time)  
                break 

        state = "RUNNING" if running else "STOPPED" 
        uptime_str = f"{uptime}s" if uptime is not None else "-"  

        return ( 
            f"{name}: {state} "  
            f"({len(running)}/{len(program.processes)}) " 
            f"retries={retries} uptime={uptime_str}"  
        )