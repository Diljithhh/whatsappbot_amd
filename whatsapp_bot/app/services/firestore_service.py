import os
from firebase_admin import credentials, firestore, initialize_app, storage
import json
import base64
import uuid
from datetime import datetime
import requests
from io import BytesIO

firebase_creds_base64 = os.getenv("FIREBASE_CREDENTIALS_BASE64")
if firebase_creds_base64:
    creds_json = json.loads(base64.b64decode(firebase_creds_base64).decode("utf-8"))
    cred = credentials.Certificate(creds_json)
    initialize_app(cred, {
        'storageBucket': os.getenv('FIREBASE_STORAGE_BUCKET', 'whatsapp-bot-images')
    })
    print("Firebase Admin SDK initialized successfully", creds_json)

    db = firestore.client()
    bucket = storage.bucket()
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

def get_partner_doc_ref(phone_number: str):
    """Get the Firestore document reference for a partner by phone number."""
    query = db.collection("partners").where("contactNumber", "==", phone_number).limit(1).get()

    if query:
        return query[0].reference

    return None

async def store_image_in_firestore(phone_number: str, image_url: str, image_id: str, caption: str = None):
    """
    Store image metadata in Firestore and the actual image in Firebase Storage.

    Args:
        phone_number: The partner's phone number
        image_url: The URL of the image from WhatsApp
        image_id: The WhatsApp image ID
        caption: Optional caption for the image

    Returns:
        dict: Status of the operation
    """
    try:
        # Get partner document reference
        partner_doc_ref = get_partner_doc_ref(phone_number)

        if not partner_doc_ref:
            return {
                "status": "error",
                "message": "Partner not found in database"
            }

        # Download the image from WhatsApp
        response = requests.get(image_url)
        if response.status_code != 200:
            return {
                "status": "error",
                "message": f"Failed to download image: {response.status_code}"
            }

        # Generate a unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_extension = "jpg"  # Default to jpg for WhatsApp images
        filename = f"{phone_number}_{timestamp}_{uuid.uuid4().hex}.{file_extension}"

        # Upload to Firebase Storage
        blob = bucket.blob(f"partner_images/{filename}")
        blob.upload_from_string(
            response.content,
            content_type=response.headers.get('content-type', 'image/jpeg')
        )

        # Make the blob publicly accessible
        blob.make_public()

        # Store metadata in Firestore
        photos_collection = partner_doc_ref.collection("photos")
        photo_doc = photos_collection.document()

        photo_data = {
            "imageId": image_id,
            "caption": caption or "",
            "uploadedAt": firestore.SERVER_TIMESTAMP,
            "storageUrl": blob.public_url,
            "filename": filename
        }

        photo_doc.set(photo_data)

        return {
            "status": "success",
            "message": "Image uploaded successfully",
            "data": {
                "photoId": photo_doc.id,
                "storageUrl": blob.public_url
            }
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Error storing image: {str(e)}"
        }

