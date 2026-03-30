# # main_bonus.py (Bonus Daemon)
# import os
# import sys
# import time
# import atexit
# from process.manager_bonus import ProcessManagerDaemon
# from shell.control import ControlShell

# LOG_FILE = "/tmp/taskmaster_daemon.log"
# PID_FILE = "/tmp/taskmaster_daemon.pid"
# CONFIG_FILE = "example_config.yaml"

# def daemonize(log_file=LOG_FILE, pid_file=PID_FILE):
#     if os.path.exists(pid_file):
#         with open(pid_file) as f:
#             pid = int(f.read().strip())
#         try:
#             os.kill(pid, 0)
#             print(f"Daemon already running (PID={pid})")
#             sys.exit(0)
#         except ProcessLookupError:
#             os.remove(pid_file)

#     if os.fork() > 0: exit(0)
#     os.setsid()
#     if os.fork() > 0: exit(0)

#     # redirige stdout/stderr vers log
#     sys.stdin.flush()
#     sys.stdout.flush()
#     sys.stderr.flush()
#     with open('/dev/null', 'r') as f: os.dup2(f.fileno(), sys.stdin.fileno())
#     log_fd = open(log_file, 'a+', buffering=1)
#     os.dup2(log_fd.fileno(), sys.stdout.fileno())
#     os.dup2(log_fd.fileno(), sys.stderr.fileno())

#     with open(pid_file, "w") as f: f.write(str(os.getpid()))
#     atexit.register(lambda: os.path.exists(pid_file) and os.remove(pid_file))

# def main():
#     daemonize(LOG_FILE, PID_FILE)
#     manager = ProcessManagerDaemon(CONFIG_FILE, log_file=LOG_FILE)
#     print(f"[TaskMaster] Daemon started, logs in {LOG_FILE}")
#     while True:
#         manager.check_reload()
#         time.sleep(1)

# if __name__ == "__main__":
#     main()
