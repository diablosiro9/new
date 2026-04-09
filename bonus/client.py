import socket  
import sys  
import tty 
import termios 
import sys  
import os 
import select 

SOCKET_PATH = "/tmp/taskmaster.sock" 
def interactive_mode(sock):
    old_settings = termios.tcgetattr(sys.stdin.fileno())
    try:
        tty.setraw(sys.stdin.fileno())

        while True:
            rlist, _, _ = select.select([sys.stdin, sock], [], [])

            if sys.stdin in rlist:
                data = os.read(sys.stdin.fileno(), 1024)
                if not data:
                    break
                sock.sendall(data)

            if sock in rlist:
                try:
                    data = sock.recv(4096)
                    if not data:
                        break
                    os.write(sys.stdout.fileno(), data)

                    if b"\r\nDetached.\r\n" in data:
                        break
                except (ConnectionResetError, OSError):
                    break
    finally:
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_settings)

        print()
        
def main(): 
    if len(sys.argv) < 2:  
        print("Usage: client.py <command>")
        sys.exit(1)

    command = " ".join(sys.argv[1:]) 

    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)  
    client.settimeout(2) 

    try:
        client.connect(SOCKET_PATH) 
    except (FileNotFoundError, ConnectionRefusedError):  
        print("ERR daemon not running or socket closed")
        sys.exit(1)

    if command.startswith("attach"):  
        program = command.split()[1]  
        client.sendall(f"attach {program}\n".encode()) 
        interactive_mode(client) 
        return

    client.sendall((command + "\n").encode()) 

    try:
        response = client.recv(4096).decode() 
        print(response.strip()) 
    except socket.timeout:
        print("ERR timeout: no response from daemon") 
    except ConnectionResetError:
        print("Connection closed by daemon")  

    client.close()  

if __name__ == "__main__": 
    main()  