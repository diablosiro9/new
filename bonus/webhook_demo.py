from http.server import BaseHTTPRequestHandler, HTTPServer  # Import des classes pour créer un serveur HTTP simple
import json  # Module pour manipuler du JSON

class Handler(BaseHTTPRequestHandler):  # Classe qui gère les requêtes HTTP reçues
    def do_POST(self):  # Méthode appelée lors d'une requête POST
        length = int(self.headers.get("Content-Length", 0))  # Récupère la taille du body envoyé par le client
        body = self.rfile.read(length).decode()  # Lit le body HTTP et le décode en string

        print("\n📩 WEBHOOK RECEIVED")  # Affiche un message indiquant qu'un webhook a été reçu
        try:  # Tentative de parsing JSON
            print(json.dumps(json.loads(body), indent=2))  # Parse le JSON puis le réaffiche formaté (indenté)
        except Exception:  # Si le body n'est pas un JSON valide
            print(body)  # Affiche le contenu brut

        self.send_response(200)  # Envoie un code HTTP 200 (OK)
        self.end_headers()  # Termine les headers HTTP
        self.wfile.write(b"OK")  # Envoie une réponse simple au client

    def log_message(self, format, *args):  # Override du logger HTTP par défaut
        return  # Désactive les logs automatiques du serveur pour éviter le bruit

if __name__ == "__main__":  # Point d'entrée du script
    print("🌐 Webhook demo listening on http://localhost:8080/webhook")  # Message indiquant que le serveur démarre
    server = HTTPServer(("localhost", 8080), Handler)  # Création du serveur HTTP sur localhost:8080 avec le handler défini
    try:  # Bloc principal d'exécution du serveur
        server.serve_forever()  # Lance le serveur en boucle infinie
    except KeyboardInterrupt:  # Interruption clavier (Ctrl+C)
        print("\n🛑 Webhook demo stopped cleanly")  # Message d'arrêt propre
        server.server_close()  # Ferme proprement le serveur HTTP