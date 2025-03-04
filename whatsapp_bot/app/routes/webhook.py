
from fastapi import APIRouter, Request, Response, HTTPException
from whatsapp_bot.  app.services.firestore_service import get_partner_greeting
from whatsapp_bot.app.services.nlp_service import DealerAgent
from whatsapp_bot. app.services.whatsapp_service import send_whatsapp_message
import json
import os
import logging
import hmac
import hashlib
from datetime import datetime
from typing import Dict
from whatsapp_bot.app.services.sessions import SessionManager as session_manager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()
agent = DealerAgent(api_key=os.getenv("GEMINI_API_KEY"))

# Session management


@router.get("/webhook")
async def verify_webhook(request: Request):
    """Handle WhatsApp webhook verification"""
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    logger.info(f"Received webhook verification request: mode={mode}, token={token}")

    if mode == "subscribe" and token == os.getenv("WHATSAPP_VERIFY_TOKEN"):
        if not challenge:
            raise HTTPException(status_code=400, detail="No challenge received")
        return Response(content=challenge, media_type="text/plain")
    raise HTTPException(status_code=403, detail="Verification failed")







@router.post("/webhook")
async def webhook_handler(request: Request):
    """Handle incoming WhatsApp messages"""
    try:
        body = await request.body()
        data = json.loads(body)
        logger.info(f"Received webhook data: {data}")

        entry = data.get("entry", [])
        if not entry:
            raise ValueError("Missing 'entry' in webhook data")

        changes = entry[0].get("changes", [])
        if not changes:
            raise ValueError("Missing 'changes' in webhook data")

        value = changes[0].get("value", {})
        messages = value.get("messages", [])

        if not messages:
            return {"status": "no_messages"}  # No messages in this webhook

        message = messages[0]
        phone_number = message["from"]
        message_text = message["text"]["body"]

        logger.info(f"Processing message from {phone_number}: {message_text}")

        # Fetch session data
        session = session_manager.get_session(phone_number)

        # Check if the user is a registered partner
        if "partner_info" not in session:
            greeting_message = get_partner_greeting(phone_number)

            # Extract partner name from the response
            if greeting_message.startswith("Hi "):  # Means partner exists
                partner_name = greeting_message[3:-1]  # Remove "Hi " and "!"
                session["partner_info"] = {"name": partner_name}
            else:
                session["partner_info"] = None  # Not a registered partner

        # Generate response
        if session["partner_info"]:
            partner_name = session["partner_info"]["name"]
            response = f"Hello {partner_name}! How can I assist you today?"
        else:
            response = "Please contact our sales team to register as a partner."

        # Send WhatsApp reply
        await send_whatsapp_message(phone_number, response)
        return {"status": "success", "message": response}

    except json.JSONDecodeError:
        logger.error("Invalid JSON payload received")
        raise HTTPException(status_code=400, detail="Invalid JSON format")

    except ValueError as e:
        logger.error(f"Error processing webhook: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# @router.post("/webhook")
# async def webhook_handler(request: Request):
#     """Handle incoming WhatsApp messages"""
#     body = await request.body()
#     logger.info(f"Received raw webhook body: {body.decode()}")
#     signature = request.headers.get("X-Hub-Signature-256", "")

#     # Verify signature
#     expected_signature = hmac.new(
#         os.getenv("WHATSAPP_API_KEY").encode(),
#         body,
#         hashlib.sha256
#     ).hexdigest()

#     if not hmac.compare_digest(f"sha256={expected_signature}", signature):
#         logger.warning("Invalid signature received")
#         # We'll continue processing as Meta doesn't always send signatures correctly

#     data = json.loads(body)
#     logger.info(f"Received webhook data: {data}")

#     try:
#         entry = data["entry"][0]
#         changes = entry["changes"][0]
#         value = changes["value"]

#         if "messages" in value:
#             message = value["messages"][0]
#             phone_number = message["from"]
#             message_text = message["text"]["body"]
#             logger.info(f"Processing message from {phone_number}: {message_text}")

#             # Get or create session
#             session = session_manager.get_session(phone_number)

#             # Check if this is the user's first message in this session
#             is_first_message = len(session["context"]) == 0

#             # If it's the first message, check if the user is a registered partner
#             if is_first_message:
#                 partner_registered = is_partner_registered(phone_number)

#                 if partner_registered:
#                     # User is a registered partner
#                     partner_name = get_partner_name(phone_number)
#                     greeting = f"Hello {partner_name}! Welcome back. How can I assist you today?"
#                     await send_whatsapp_message(phone_number, greeting)

#                     # Update context with greeting
#                     session_manager.update_context(phone_number, greeting, "assistant")

#                     # Store partner info in session
#                     session["partner_info"] = {"name": partner_name}
#                 else:
#                     # User is not a registered partner
#                     response = "Hi! You are not a registered partner. Please contact our sales team to register."
#                     await send_whatsapp_message(phone_number, response)

#                     # Update context with response
#                     session_manager.update_context(phone_number, response, "assistant")
#                     return {"status": "ok"}

#             # Update context with user message
#             session_manager.update_context(phone_number, message_text, "user")

#             # Process with AI agent only if the user is a registered partner
#             if "partner_info" in session:
#                 response = await agent.process_message(message_text)
#             else:
#                 # For non-partners, provide a standard response
#                 response = "Please contact our sales team to register as a partner."

#             # Update context with AI response
#             session_manager.update_context(phone_number, response, "assistant")

#             # Send response to WhatsApp
#             await send_whatsapp_message(phone_number, response)

#     except Exception as e:
#         logger.error(f"Error processing webhook: {e}")

#     return {"status": "ok"}

