import os
import threading 
import time  
import pwd  
import grp
import json  
import fcntl 
import termios  
from process.manager import ProcessManager 
from utils.enums import ProcessState 
from bonus.logger import log  
from bonus.webhook import send_webhook  
from bonus.pty_manager import PTYManager 

ALERT_FILE = os.path.join(os.path.dirname(__file__), "logs/alerts.log") 
os.makedirs(os.path.dirname(ALERT_FILE), exist_ok=True) 

class ManagerWrapper:  
    def __init__(self, config_path, is_daemon=False): 
        self.manager = ProcessManager(config_path) 
        self.disabled_programs = set()  
        self._child_threads = {} 
        self._exited_pids = set()  
        self.is_daemon = is_daemon  
        self.pty_manager = PTYManager() 
        self.manager.pty_manager = self.pty_manager

    def log(self, message, level="INFO"):  
        log(message, level, is_daemon=self.is_daemon) 

    def send_alert(self, event, payload):  
        if not self.is_daemon: 
            return  

        alert = {  
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), 
            "event": event, 
            "payload": payload,
        }

        with open(ALERT_FILE, "a+", buffering=1) as f:  
            f.write(json.dumps(alert) + "\n") 

        self.log(f"[ALERT] {event} {payload}", level="WARNING")  
        send_webhook(alert)  

    def start_program(self, name):
        if name in self.disabled_programs:
            self.log(f"Program '{name}' is disabled, not starting")
            return

        program = self.manager.programs.get(name)
        if not program:
            self.log(f"Program '{name}' not found")
            return

        self.manager.start_program(name)

    def _tail_child(self, pid, fd, prog_name):
        seen = set()
        while True:
            try:
                data = os.read(fd, 1024)
                if not data:
                    break
                for line in data.decode(errors="ignore").splitlines():
                    line_clean = line.strip()
                    if line_clean not in seen:
                        self.log(f"[Child {pid}] {line_clean}")
                        seen.add(line_clean)
                        
                        try:
                            from bonus.alerting import send_alert
                            send_alert(
                                event="program_log",
                                payload={
                                    "program": prog_name,
                                    "pid": pid,
                                    "line": line_clean
                                }
                            )
                        except Exception as e:
                            print(f"⚠️ Failed to send program log alert: {e}", flush=True)
            except OSError:
                break

        os.close(fd)

        if pid not in self._exited_pids:  
            self._exited_pids.add(pid)
            self.send_alert("process_exited", {"program": prog_name, "pid": pid})

    def stop_program(self, name): 
        self.disabled_programs.add(name) 

        program = self.manager.programs.get(name)
        if program:
            for inst in program.processes:
                if inst.state == ProcessState.RUNNING and inst.pid:
                    self.send_alert("process_stopped", {"program": name, "pid": inst.pid})

        self.manager.stop_program(name)  

    def reload_config(self):  
        self.manager.reload_config() 

        for name, prog in self.manager.programs.items():
            if name in self.disabled_programs:
                self.log(f"[Bonus] '{name}' disabled, ignoring reload")
                continue

            desired = prog.config.numprocs  
            running = len([p for p in prog.processes if p.state == ProcessState.RUNNING])  # Nombre actuel

            if running < desired:
                self.log(f"[Bonus] Increasing '{name}' {running} -> {desired}")
                for _ in range(desired - running):
                    self.start_program(name)

            elif running > desired:
                self.log(f"[Bonus] Decreasing '{name}' {running} -> {desired}")
                self.manager.stop_program(name)

    def __getattr__(self, attr): 
        return getattr(self.manager, attr) 