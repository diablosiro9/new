import sys 
import os 

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  
sys.path.insert(0, ROOT)  

from utils.enums import ProcessState 

def handle_command(manager, command: str) -> str:  
    parts = command.strip().split()  
    if not parts:  
        return "ERR empty command"  

    cmd = parts[0] 

    if cmd == "status":

        if hasattr(manager, 'manager'):
            manager.manager.process_exited()
        elif hasattr(manager, 'process_exited'):
            manager.process_exited()
        
        lines = []
        for name, prog in manager.programs.items():
            running = len([p for p in prog.processes if p.state == ProcessState.RUNNING])
            desired = prog.config.numprocs
            state = "RUNNING" if running > 0 else "STOPPED"
            lines.append(f"{name} {state} {running}/{desired}")
        return "\n".join(lines) if lines else "OK no programs"

    elif cmd == "start":  
        if len(parts) != 2: 
            return "ERR usage: start <program>"  
        manager.start_program(parts[1])  
        return f"OK started {parts[1]}" 

    elif cmd == "stop": 
        if len(parts) != 2:  
            return "ERR usage: stop <program>" 
        manager.stop_program(parts[1])  
        return f"OK stopped {parts[1]}"  

    elif cmd == "reload": 
        manager.reload_config()  
        return "OK reload done"  

    elif cmd == "shutdown":  
        return "OK shutdown"  

    # elif cmd.startswith("attach"):  # Commande attach
    #     parts = cmd.split()  # Découpe la commande

    #     if len(parts) != 2:  # Vérifie format
    #         client_socket.sendall(b"Usage: attach <program[:index]>\n")  # Message usage
    #         return  # Stop

    #     target = parts[1]  # Cible (programme ou instance)

    #     # --- parse program:index ---
    #     if ":" in target:  # Si index précisé
    #         prog_name, idx = target.split(":", 1)  # Sépare nom et index
    #         try:  # Conversion index
    #             index = int(idx)  # Convertit en entier
    #         except ValueError:  # Si invalide
    #             client_socket.sendall(b"Invalid instance index\n")  # Message erreur
    #             return  # Stop
    #     else:  # Sinon
    #         prog_name = target  # Nom du programme
    #         index = 0  # Instance par défaut

    #     program = manager.programs.get(prog_name)  # Récupère le programme

    #     if not program:  # Si introuvable
    #         client_socket.sendall(b"Program not found\n")  # Erreur
    #         return  # Stop

    #     if index >= len(program.processes):  # Vérifie index
    #         client_socket.sendall(b"Instance index out of range\n")  # Erreur
    #         return  # Stop

    #     inst = program.processes[index]  # Récupère l’instance

    #     if inst.state != ProcessState.RUNNING:  # Vérifie qu’elle tourne
    #         client_socket.sendall(b"Instance not running\n")  # Erreur
    #         return  # Stop

    #     if not getattr(inst, "is_attachable", False):  # Vérifie si attachable
    #         client_socket.sendall(b"Instance not attachable\n")  # Erreur
    #         return  # Stop

    #     manager.pty_manager.attach(inst.pid, client_socket)  # Attache le client au process
    #     return  # Fin

    # client_socket.sendall(b"No running attachable instance\n")  # Message si aucune instance valide

    # return "ERR unknown command"  # Commande inconnue