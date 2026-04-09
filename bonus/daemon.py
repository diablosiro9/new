import os
import sys 
import time 
import signal 
import atexit  
import fcntl  
from socket_server import SocketServer  
from bonus.manager_wrapper import ManagerWrapper  

PID_FILE = "/tmp/taskmaster_daemon.pid" 
LOCK_FILE = "/tmp/taskmaster_daemon.lock"  
LOG_FILE = os.path.join(os.path.dirname(__file__), "logs/daemon.log")

IS_DAEMON = False 

def daemonize(log_file=None):  
    global IS_DAEMON  

    if os.fork() > 0:  
        sys.exit(0)  

    os.setsid()  

    if os.fork() > 0:  
        sys.exit(0)

    os.umask(0)  

    if log_file: 
        os.makedirs(os.path.dirname(log_file), exist_ok=True)  
        log_f = open(log_file, "a+", buffering=1)  
        os.dup2(log_f.fileno(), 1)  
        os.dup2(log_f.fileno(), 2)  

    with open(PID_FILE, "w") as f:  
        f.write(str(os.getpid()))

    atexit.register(lambda: os.path.exists(PID_FILE) and os.remove(PID_FILE))
    atexit.register(lambda: os.path.exists(LOCK_FILE) and os.remove(LOCK_FILE))  

    IS_DAEMON = True  

def acquire_lock(): 
    fd = os.open(LOCK_FILE, os.O_CREAT | os.O_RDWR) 
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)  
    except BlockingIOError:  
        print("[TaskMaster] Daemon already running") 
        sys.exit(1)  
    return fd  

def main(): 
    if len(sys.argv) < 2: 
        print("Usage: daemon.py <config.yaml> [--no-daemon]")
        sys.exit(1)

    config_path = sys.argv[1] 
    no_daemon = len(sys.argv) == 3 and sys.argv[2] == "--no-daemon"

    lock_fd = acquire_lock()

    if not no_daemon: 
        daemonize(log_file=LOG_FILE) 

    manager = ManagerWrapper(config_path, is_daemon=IS_DAEMON) 
    manager.manager.log("[Daemon] Loading configuration without autostart") 

    from config.loader import ConfigLoader  
    from process.instance import ProcessInstance
    from utils.enums import ProcessState

    
    loader = ConfigLoader(config_path)  
    programs = loader.load()  

    for program in programs:  
        manager.add_program(program)


    for prog in manager.manager.programs.values():
        if prog.config.autostart: 
            print(f"[DEBUG] Starting program {prog.config.name} as {prog.config.user}")
            manager.start_program(prog.config.name) 

    manager.send_alert("daemon_started", {"pid": os.getpid()}) 

   
    socket_server = SocketServer(manager)  
    socket_server.start()  


    def handle_term(signum, frame):
        manager.send_alert("daemon_stopping", {"signal": signum})
        manager.log("[Daemon] SIGTERM received, stopping all programs...")
        for prog in manager.programs.values():
            manager.stop_program(prog.config.name)
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_term) 
    signal.signal(signal.SIGHUP, lambda s,f: manager.reload_config()) 


    while True:
        try:
            manager.process_exited()  
            time.sleep(0.5)  
        except Exception as e:
            manager.send_alert("daemon_exception", {"error": str(e)}) 
            manager.log(f"[Daemon] Exception caught: {e}", level="ERROR")

if __name__ == "__main__":  
    main()  