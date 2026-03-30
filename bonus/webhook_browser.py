import json  # Module pour encoder/décoder du JSON
import threading  # Module pour gérer les threads (non utilisé directement ici mais importé)
from http.server import HTTPServer, BaseHTTPRequestHandler  # Classes pour créer un serveur HTTP simple
from socketserver import ThreadingMixIn  # Permet de rendre le serveur multi-threadé

# Stockage en mémoire des alertes pour affichage navigateur
ALERTS = []  # Liste globale qui contient toutes les alertes reçues

class WebhookHandler(BaseHTTPRequestHandler):  # Classe qui gère les requêtes HTTP entrantes
    def do_POST(self):  # Méthode appelée lors d'une requête POST
        length = int(self.headers.get("content-length", 0))  # Récupère la taille du body HTTP
        body = self.rfile.read(length)  # Lit le corps de la requête
        try:  # Bloc de gestion d'erreur pour parsing JSON
            alert = json.loads(body)  # Convertit le JSON reçu en dictionnaire Python
            ALERTS.append(alert)  # Ajoute l'alerte à la liste globale
            print(f"📩 WEBHOOK RECEIVED: {alert}")  # Affiche l'alerte reçue dans la console
        except Exception:  # Si le JSON est invalide ou erreur de parsing
            print(f"⚠️ Malformed webhook: {body.decode()}")  # Affiche le contenu brut reçu
        self.send_response(200)  # Envoie un statut HTTP 200 (OK)
        self.end_headers()  # Termine les headers HTTP
        self.wfile.write(b"OK")  # Envoie une réponse simple au client

    def do_GET(self):  # Méthode appelée lors d'une requête GET
        self.send_response(200)  # Statut HTTP OK
        self.send_header("Content-Type", "text/html")  # Indique que la réponse est du HTML
        self.end_headers()  # Termine les headers HTTP

        # page HTML simple + auto-refresh toutes les 2s
        html = """  # Début du contenu HTML envoyé au navigateur
        <html>
        <head>
            <title>TaskMaster Alerts</title>  # Titre de la page
            <meta http-equiv="refresh" content="2">  # Auto-refresh de la page toutes les 2 secondes
            <style>  # Début des styles CSS
                body { font-family: monospace; background: #111; color: #eee; }  # Style global de la page
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
        for a in ALERTS[-50:]:  # Parcourt les 50 dernières alertes
            event = a.get("event", "")  # Récupère le type d'événement
            cls = "start" if "started" in event else "stop" if "stopped" in event else "exit" if "exited" in event else ""  # Détermine la classe CSS selon le type d'événement
            html += f"<li class='{cls}'>{json.dumps(a)}</li>"  # Ajoute une ligne HTML avec l'alerte formatée en JSON
        html += "</ul></body></html>"  # Ferme les balises HTML
        try:  # Tentative d'envoi de la réponse HTML
            self.wfile.write(html.encode())  # Envoie le HTML encodé en bytes
        except BrokenPipeError:  # Si le client ferme la connexion avant la réponse
            pass  # Ignore l'erreur

    def log_message(self, format, *args):  # Override de la méthode de log HTTP par défaut
        return  # Désactive les logs HTTP standards pour éviter le bruit dans la console

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):  # Serveur HTTP multi-threadé
    daemon_threads = True  # Les threads clients s'arrêtent automatiquement avec le serveur

if __name__ == "__main__":  # Point d'entrée du script
    PORT = 8080  # Port sur lequel le serveur écoute
    print(f"🌐 Webhook browser server listening on http://localhost:{PORT}")  # Message de démarrage
    server = ThreadedHTTPServer(("localhost", PORT), WebhookHandler)  # Création du serveur HTTP
    try:  # Bloc principal d'exécution
        server.serve_forever()  # Lance le serveur en boucle infinie
    except KeyboardInterrupt:  # Si interruption clavier (Ctrl+C)
        print("\n🛑 Server stopped cleanly")  # Message d'arrêt propre
        server.server_close()  # Ferme proprement le serveur