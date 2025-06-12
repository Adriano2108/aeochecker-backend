import os
import json
import firebase_admin
from firebase_admin import credentials, firestore, auth
from app.core.config import settings

# Initialize Firebase Admin SDK
def init_firebase():
    cred = None
    
    # Try to use JSON credentials from environment variable first (for Cloud Run)
    if settings.FIREBASE_SERVICE_ACCOUNT_JSON:
        try:
            # Parse the JSON string from environment variable
            service_account_info = json.loads(settings.FIREBASE_SERVICE_ACCOUNT_JSON)
            cred = credentials.Certificate(service_account_info)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in FIREBASE_SERVICE_ACCOUNT_JSON: {e}")
    
    # Fall back to file path if JSON not provided (for local development)
    elif settings.FIREBASE_SERVICE_ACCOUNT_KEY_PATH and os.path.exists(settings.FIREBASE_SERVICE_ACCOUNT_KEY_PATH):
        cred = credentials.Certificate(settings.FIREBASE_SERVICE_ACCOUNT_KEY_PATH)
    
    else:
        raise FileNotFoundError("Firebase credentials not found. Provide either FIREBASE_SERVICE_ACCOUNT_JSON or FIREBASE_SERVICE_ACCOUNT_KEY_PATH")
    
    firebase_admin.initialize_app(cred)
    
    return {
        "db": firestore.client(),
        "auth": auth
    }

# Initialize Firebase services
firebase_services = init_firebase()
db = firebase_services["db"]
firebase_auth = firebase_services["auth"] 