import os
from firebase_admin import credentials, firestore, initialize_app, storage
import json
import base64
import uuid
from datetime import datetime
import requests
from io import BytesIO
import logging
import time
import httpx

logger = logging.getLogger(__name__)

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

def is_partner_registered(phone_number: str) -> bool:
    """Check if a phone number exists as a registered partner."""
    try:
        query = db.collection("partners").where("contactNumber", "==", phone_number).limit(1).get()
        return len(query) > 0
    except Exception as e:
        logger.error(f"Error checking partner registration: {e}")
        return False

def get_partner_greeting(phone_number: str) -> str:
    """Fetch partner's name by phone number and return a greeting message."""
    try:
        query = db.collection("partners").where("contactNumber", "==", phone_number).limit(1).get()

        if query:
            partner_name = query[0].to_dict().get("partnerName", "Partner")
            return f"Hi {partner_name}!"

        return "Hi! Your number is not registered as a partner."
    except Exception as e:
        logger.error(f"Error getting partner greeting: {e}")
        return "Hi! Your number is not registered as a partner."

def get_partner_doc_ref(phone_number: str):
    """Get the Firestore document reference for a partner by phone number."""
    try:
        query = db.collection("partners").where("contactNumber", "==", phone_number).limit(1).get()

        if query:
            return query[0].reference

        return None
    except Exception as e:
        logger.error(f"Error getting partner document reference: {e}")
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
        if not image_url or not image_id:
            logger.error(f"Missing image URL or ID: url={image_url}, id={image_id}")
            return {
                "status": "error",
                "message": "Missing image URL or ID"
            }

        # First verify this is a registered partner
        if not is_partner_registered(phone_number):
            logger.error(f"Attempted to store image for non-partner: {phone_number}")
            return {
                "status": "error",
                "message": "Phone number is not registered as a partner"
            }

        # Get partner document reference
        partner_doc_ref = get_partner_doc_ref(phone_number)

        if not partner_doc_ref:
            logger.error(f"Partner document not found for phone_number: {phone_number}")
            return {
                "status": "error",
                "message": "Partner not found in database"
            }

        logger.info(f"Downloading image from WhatsApp for phone_number: {phone_number}")

        # Get WhatsApp API key for authorization
        api_key = os.getenv("WHATSAPP_API_KEY")
        if not api_key:
            logger.error("Missing WhatsApp API key")
            return {
                "status": "error",
                "message": "Missing WhatsApp API configuration"
            }

        # Include the authorization header when downloading the image
        headers = {
            "Authorization": f"Bearer {api_key}"
        }

        # Try to download the image with retries
        max_retries = 3
        retry_delay = 2  # seconds
        image_content = None

        for attempt in range(max_retries):
            try:
                logger.info(f"Download attempt {attempt + 1} for image_id: {image_id}")

                # Try using httpx for async download
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.get(
                        image_url,
                        headers=headers,
                        follow_redirects=True  # Follow redirects automatically
                    )
                    response.raise_for_status()

                    # Check content length
                    content_length = response.headers.get('content-length')
                    if content_length and int(content_length) == 0:
                        logger.warning(f"Image has zero content length on attempt {attempt + 1}")
                        if attempt < max_retries - 1:
                            time.sleep(retry_delay)
                            continue
                        else:
                            return {
                                "status": "error",
                                "message": "Image has zero content length after multiple attempts"
                            }

                    image_content = response.content
                    if image_content and len(image_content) > 0:
                        logger.info(f"Successfully downloaded image on attempt {attempt + 1}, size: {len(image_content)} bytes")
                        break
                    else:
                        logger.warning(f"Empty image content on attempt {attempt + 1}")
                        if attempt < max_retries - 1:
                            time.sleep(retry_delay)

            except (httpx.HTTPStatusError, httpx.RequestError) as e:
                logger.error(f"Failed to download image on attempt {attempt + 1}: {str(e)}")
                if attempt < max_retries - 1:
                    logger.info(f"Retrying download in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    return {
                        "status": "error",
                        "message": f"Failed to download image after {max_retries} attempts: {str(e)}"
                    }

        if not image_content or len(image_content) == 0:
            logger.error("Downloaded image has no content after all attempts")
            return {
                "status": "error",
                "message": "Downloaded image has no content"
            }

        # Generate a unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_extension = "jpg"  # Default to jpg for WhatsApp images
        filename = f"{phone_number}_{timestamp}_{uuid.uuid4().hex}.{file_extension}"

        logger.info(f"Uploading image to Firebase Storage: {filename}")
        # Upload to Firebase Storage
        try:
            blob = bucket.blob(f"partner_images/{filename}")
            blob.upload_from_string(
                image_content,
                content_type=response.headers.get('content-type', 'image/jpeg')
            )

            # Make the blob publicly accessible
            blob.make_public()
        except Exception as e:
            logger.error(f"Failed to upload image to Firebase Storage: {str(e)}")
            return {
                "status": "error",
                "message": f"Failed to upload image to storage: {str(e)}"
            }

        logger.info(f"Storing image metadata in Firestore for phone_number: {phone_number}")
        # Store metadata in Firestore
        try:
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
        except Exception as e:
            logger.error(f"Failed to store image metadata in Firestore: {str(e)}")
            return {
                "status": "error",
                "message": f"Failed to store image metadata: {str(e)}"
            }

        logger.info(f"Image successfully stored for phone_number: {phone_number}")
        return {
            "status": "success",
            "message": "Image uploaded successfully",
            "data": {
                "photoId": photo_doc.id,
                "storageUrl": blob.public_url
            }
        }

    except Exception as e:
        logger.error(f"Error storing image: {str(e)}")
        return {
            "status": "error",
            "message": f"Error storing image: {str(e)}"
        }

