import os
import httpx
import logging
import base64
import json
from firebase_admin import credentials, initialize_app, firestore

logger = logging.getLogger(__name__)

# # Initialize Firebase Admin SDK
# firebase_creds_base64 = os.getenv("FIREBASE_CREDENTIALS_BASE64")
# if firebase_creds_base64:
#     creds_json = json.loads(base64.b64decode(firebase_creds_base64).decode("utf-8"))
#     cred = credentials.Certificate(creds_json)
#     initialize_app(cred)
#     db = firestore.client()
# else:
#     raise ValueError("Firebase credentials not found.")


async def send_whatsapp_message(to: str, message: str):
    """Send message to WhatsApp"""
    phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    api_key = os.getenv("WHATSAPP_API_KEY")

    url = f"https://graph.facebook.com/v17.0/{phone_number_id}/messages"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    data = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": message}
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=data, headers=headers)
            response.raise_for_status()
            logger.info(f"WhatsApp API response: {response.json()}")
            return response.json()

    except httpx.HTTPStatusError as e:
        logger.error(f"WhatsApp API error: {e.response.status_code} - {e.response.text}")
        return {"status": "error", "message": "WhatsApp API request failed"}

    except Exception as e:
        logger.error(f"Unexpected error sending WhatsApp message: {e}")
        return {"status": "error", "message": "Unexpected error"}


async def send_service_menu(to: str, header_text: str = "Available Services"):
    """Send an interactive list message with service options"""
    phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    api_key = os.getenv("WHATSAPP_API_KEY")

    url = f"https://graph.facebook.com/v17.0/{phone_number_id}/messages"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    data = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {
                "type": "text",
                "text": header_text
            },
            "body": {
                "text": "Please select a service from the list below:"
            },
            "footer": {
                "text": "AMD Partner Services"
            },
            "action": {
                "button": "View Services",
                "sections": [
                    {
                        "title": "Product Services",
                        "rows": [
                            {
                                "id": "upload_product_images",
                                "title": "Upload Product Images",
                                "description": "Upload images for your AMD products"
                            },
                            {
                                "id": "request_new_product",
                                "title": "Request a New Product",
                                "description": "Request to add a new AMD product to your inventory"
                            }
                        ]
                    },
                    {
                        "title": "Support Services",
                        "rows": [
                            {
                                "id": "technical_support",
                                "title": "Technical Support",
                                "description": "Get technical assistance for AMD products"
                            },
                            {
                                "id": "order_status",
                                "title": "Order Status",
                                "description": "Check the status of your orders"
                            }
                        ]
                    }
                ]
            }
        }
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=data, headers=headers)
            response.raise_for_status()
            logger.info(f"WhatsApp API response for service menu: {response.json()}")
            return response.json()

    except httpx.HTTPStatusError as e:
        logger.error(f"WhatsApp API error sending service menu: {e.response.status_code} - {e.response.text}")
        return {"status": "error", "message": "WhatsApp API request failed"}

    except Exception as e:
        logger.error(f"Unexpected error sending service menu: {e}")
        return {"status": "error", "message": "Unexpected error"}


async def send_whatsapp_media_message(to: str, media_id: str):
    """Send media message to WhatsApp."""
    phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    api_key = os.getenv("WHATSAPP_API_KEY")
    url = f"https://graph.facebook.com/v17.0/{phone_number_id}/messages"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    data = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "image",
        "image": {"id": media_id}
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=data, headers=headers)
        response.raise_for_status()
        return response.json()

async def send_button_message(to: str, message_text: str, buttons: list):
    """Send an interactive button message"""
    phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    api_key = os.getenv("WHATSAPP_API_KEY")

    url = f"https://graph.facebook.com/v17.0/{phone_number_id}/messages"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    # Format buttons for WhatsApp API
    formatted_buttons = []
    for button in buttons:
        formatted_buttons.append({
            "type": "reply",
            "reply": {
                "id": button.get("id", ""),
                "title": button.get("title", "")
            }
        })

    data = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {
                "text": message_text
            },
            "action": {
                "buttons": formatted_buttons
            }
        }
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=data, headers=headers)
            response.raise_for_status()
            logger.info(f"WhatsApp API response for button message: {response.json()}")
            return response.json()

    except httpx.HTTPStatusError as e:
        logger.error(f"WhatsApp API error sending button message: {e.response.status_code} - {e.response.text}")
        return {"status": "error", "message": "WhatsApp API request failed"}

    except Exception as e:
        logger.error(f"Unexpected error sending button message: {e}")
        return {"status": "error", "message": "Unexpected error"}

async def get_media_url(media_id: str):
    """
    Get the URL for a media file from WhatsApp.

    Args:
        media_id: The WhatsApp media ID

    Returns:
        dict: Status and URL of the media
    """
    try:
        phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
        api_key = os.getenv("WHATSAPP_API_KEY")

        if not api_key or not phone_number_id:
            logger.error("Missing WhatsApp API key or phone number ID")
            return {
                "status": "error",
                "message": "Missing WhatsApp API configuration"
            }

        url = f"https://graph.facebook.com/v17.0/{media_id}"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        logger.info(f"Requesting media URL for media_id: {media_id}")
        async with httpx.AsyncClient(timeout=60.0) as client:  # Increase timeout
            response = await client.get(url, headers=headers)
            response.raise_for_status()

            media_data = response.json()
            logger.info(f"Media data received: {media_data}")

            media_url = media_data.get("url")
            mime_type = media_data.get("mime_type", "image/jpeg")
            file_size = media_data.get("file_size", 0)

            if not media_url:
                logger.error(f"Media URL not found in response: {media_data}")
                return {
                    "status": "error",
                    "message": "Media URL not found in response"
                }

            # Return the URL and additional metadata
            return {
                "status": "success",
                "url": media_url,
                "mime_type": mime_type,
                "file_size": file_size,
                "media_id": media_id
            }

    except httpx.HTTPStatusError as e:
        logger.error(f"WhatsApp API error getting media: {e.response.status_code} - {e.response.text}")
        return {
            "status": "error",
            "message": f"WhatsApp API request failed: {e.response.status_code}"
        }

    except Exception as e:
        logger.error(f"Unexpected error getting media URL: {e}")
        return {
            "status": "error",
            "message": f"Unexpected error: {str(e)}"
        }

# async def send_whatsapp_message(to: str, message: str):
#     """Send message to WhatsApp"""
#     phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
#     api_key = os.getenv("WHATSAPP_API_KEY")

#     url = f"https://graph.facebook.com/v17.0/{phone_number_id}/messages"

#     headers = {
#         "Authorization": f"Bearer {api_key}",
#         "Content-Type": "application/json"
#     }

#     data = {
#         "messaging_product": "whatsapp",
#         "to": to,
#         "type": "text",
#         "text": {"body": message}
#     }

#     try:
#         async with httpx.AsyncClient() as client:
#             response = await client.post(url, json=data, headers=headers)
#             logger.info(f"WhatsApp API response: {response.json()}")
#             response.raise_for_status()
#             return response.json()
#     except Exception as e:
#         logger.error(f"Error sending WhatsApp message: {e}")
#         raise


