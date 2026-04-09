import json 
import threading 
from http.server import HTTPServer, BaseHTTPRequestHandler 
from socketserver import ThreadingMixIn  

ALERTS = [] 

class WebhookHandler(BaseHTTPRequestHandler):  
    def do_POST(self): 
        length = int(self.headers.get("content-length", 0))  
        body = self.rfile.read(length) 
        try:  
            alert = json.loads(body) 
            ALERTS.append(alert) 
            print(f"📩 WEBHOOK RECEIVED: {alert}") 
        except Exception: 
            print(f"⚠️ Malformed webhook: {body.decode()}")  
        self.send_response(200)  
        self.end_headers()  
        self.wfile.write(b"OK") 

    def do_GET(self): 
        self.send_response(200)  
        self.send_header("Content-Type", "text/html")  
        self.end_headers()  

        html = """  
        <html>
        <head>
            <title>TaskMaster Alerts</title>  
            <meta http-equiv="refresh" content="2"> 
            <style>  # Début des styles CSS
                body { font-family: monospace; background: #111; color: #eee; }  
                li.start { color: #0f0; }  # Couleur verte pour événements de type start
                li.stop { color: #f00; }  # Couleur rouge pour événements de type stop
                li.exit { color: #ff0; }  # Couleur jaune pour événements de type exit
                ul { list-style-type: none; padding: 0; }  # Supprime les puces et padding
            </style>
        </head>
        <body>
            <h1>TaskMaster Alerts (latest 50)</h1>  # Titre affiché sur la page
            <ul>  # Début de la liste des alertes
        """
        for a in ALERTS[-50:]:  
            event = a.get("event", "")  
            cls = "start" if "started" in event else "stop" if "stopped" in event else "exit" if "exited" in event else "" 
            html += f"<li class='{cls}'>{json.dumps(a)}</li>"  
        html += "</ul></body></html>"  
        try: 
            self.wfile.write(html.encode()) 
        except BrokenPipeError: 
            pass  

    def log_message(self, format, *args):
        return  

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):  
    daemon_threads = True  

if __name__ == "__main__": 
    PORT = 8080 
    print(f"🌐 Webhook browser server listening on http://localhost:{PORT}")  
    server = ThreadedHTTPServer(("localhost", PORT), WebhookHandler)  
    try:  
        server.serve_forever() 
    except KeyboardInterrupt:  
        print("\n🛑 Server stopped cleanly") 
        server.server_close()  