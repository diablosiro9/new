import json  # Module pour manipuler des données au format JSON
import urllib.request  # Module pour effectuer des requêtes HTTP

WEBHOOK_URL = "http://localhost:8080/webhook"  # URL du serveur webhook cible

def send_webhook(event: dict):  # Fonction qui envoie un événement sous forme de dictionnaire
    try:  # Bloc pour gérer les erreurs éventuelles lors de l'envoi HTTP
        req = urllib.request.Request(  # Création d'une requête HTTP
            WEBHOOK_URL,  # URL vers laquelle envoyer la requête
            data=json.dumps(event).encode(),  # Conversion du dictionnaire en JSON puis encodage en bytes
            headers={"Content-Type": "application/json"},  # Header indiquant que le body est du JSON
            method="POST",  # Méthode HTTP utilisée (POST)
        )
        urllib.request.urlopen(req, timeout=1)  # Envoi de la requête avec un timeout de 1 seconde
    except Exception:  # Capture toute erreur (réseau, timeout, etc.)
        pass  # Ignore silencieusement les erreurs