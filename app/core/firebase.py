import os
import firebase_admin
from firebase_admin import credentials, firestore, auth
from app.core.config import settings

# Initialize Firebase Admin SDK
def init_firebase():
    if not settings.FIREBASE_SERVICE_ACCOUNT_KEY_PATH or not os.path.exists(settings.FIREBASE_SERVICE_ACCOUNT_KEY_PATH):
        raise FileNotFoundError(f"Firebase service account key not found at {settings.FIREBASE_SERVICE_ACCOUNT_KEY_PATH}")
    
    cred = credentials.Certificate(settings.FIREBASE_SERVICE_ACCOUNT_KEY_PATH)
    firebase_admin.initialize_app(cred)
    
    return {
        "db": firestore.client(),
        "auth": auth
    }

# Initialize Firebase services
firebase_services = init_firebase()
db = firebase_services["db"]
firebase_auth = firebase_services["auth"] 