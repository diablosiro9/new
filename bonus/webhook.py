import json  
import urllib.request 

WEBHOOK_URL = "http://localhost:8080/webhook"  

def send_webhook(event: dict):  
    try: 
        req = urllib.request.Request( 
            WEBHOOK_URL, 
            data=json.dumps(event).encode(),  
            headers={"Content-Type": "application/json"},  
            method="POST",
        )
        urllib.request.urlopen(req, timeout=1) 
    except Exception: 
        pass  