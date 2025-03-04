import os
from firebase_admin import credentials, firestore, initialize_app
import json
import base64

firebase_creds_base64 = os.getenv("FIREBASE_CREDENTIALS_BASE64")
if firebase_creds_base64:
    creds_json = json.loads(base64.b64decode(firebase_creds_base64).decode("utf-8"))
    cred = credentials.Certificate(creds_json)
    initialize_app(cred)
    print("Firebase Admin SDK initialized successfully", creds_json)

    db = firestore.client()
else:
    raise ValueError("Firebase credentials not found in environment variable.")

# def is_partner_registered(phone_number: str) -> bool:
#     """Check if a phone number exists in the partners collection."""
#     doc_ref = db.collection("partners").document(phone_number)
#     doc = doc_ref.get()
#     return doc.exists

def get_partner_greeting(phone_number: str) -> str:
    """Fetch partner's name by phone number and return a greeting message."""
    query = db.collection("partners").where("contactNumber", "==", phone_number).limit(1).get()

    if query:
        partner_name = query[0].to_dict().get("partnerName", "Partner")
        return f"Hi {partner_name}!"

    return "Hi! Your number is not registered as a partner."

