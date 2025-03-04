
import os
import httpx
import logging

logger = logging.getLogger(__name__)


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


