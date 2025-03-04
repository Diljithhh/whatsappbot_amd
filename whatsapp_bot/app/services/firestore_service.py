import os
from firebase_admin import credentials, firestore, initialize_app

# Check if we're in development mode
DEV_MODE = os.getenv("DEV_MODE", "true").lower() == "true"

if DEV_MODE:
    # Mock implementation for development
    class MockFirestore:
        def collection(self, name):
            return self

        def document(self, id):
            return self

        def get(self):
            return self

        @property
        def exists(self):
            return True

        def to_dict(self):
            return {"name": "Test Partner"}

    db = MockFirestore()
    print("Running in development mode with mock Firestore")
else:
    # Initialize Firebase Admin SDK with credentials from environment
    firebase_creds_path = os.getenv("FIREBASE_CREDENTIALS_PATH")
    if firebase_creds_path and os.path.exists(firebase_creds_path):
        cred = credentials.Certificate(firebase_creds_path)
        initialize_app(cred)
        db = firestore.client()
    else:
        raise ValueError("Firebase credentials not found. Set FIREBASE_CREDENTIALS_PATH environment variable.")

def is_partner_registered(phone_number: str) -> bool:
    """Check if a phone number exists in the partners collection."""
    doc_ref = db.collection("partners").document(phone_number)
    doc = doc_ref.get()
    return doc.exists

def get_partner_name(phone_number: str) -> str:
    """Retrieve partner name by phone number."""
    doc_ref = db.collection("partners").document(phone_number)
    doc = doc_ref.get()
    if doc.exists:
        return doc.to_dict().get("name", "Partner")
    return None
