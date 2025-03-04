
from fastapi import APIRouter, Request, Response, HTTPException
from whatsapp_bot.  app.services.firestore_service import is_partner_registered, get_partner_name
from whatsapp_bot.app.services.nlp_service import DealerAgent
from whatsapp_bot. app.services.whatsapp_service import send_whatsapp_message
import json
import os
import logging
import hmac
import hashlib
from datetime import datetime
from typing import Dict

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()
agent = DealerAgent(api_key=os.getenv("GEMINI_API_KEY"))

# Session management
class SessionManager:
    def __init__(self):
        self.sessions: Dict[str, Dict] = {}

    def get_session(self, phone_number: str) -> Dict:
        if phone_number not in self.sessions:
            self.sessions[phone_number] = {
                "phone_number": phone_number,
                "start_time": datetime.now(),
                "context": [],
                "last_message": None
            }
        return self.sessions[phone_number]

    def update_context(self, phone_number: str, message: str, role: str = "user"):
        session = self.get_session(phone_number)
        session["context"].append({
            "role": role,
            "content": message,
            "timestamp": datetime.now().isoformat()
        })
        session["last_message"] = datetime.now()

session_manager = SessionManager()

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
    body = await request.body()
    logger.info(f"Received raw webhook body: {body.decode()}")
    signature = request.headers.get("X-Hub-Signature-256", "")

    # Verify signature
    expected_signature = hmac.new(
        os.getenv("WHATSAPP_API_KEY").encode(),
        body,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(f"sha256={expected_signature}", signature):
        logger.warning("Invalid signature received")
        # We'll continue processing as Meta doesn't always send signatures correctly

    data = json.loads(body)
    logger.info(f"Received webhook data: {data}")

    try:
        entry = data["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]

        if "messages" in value:
            message = value["messages"][0]
            phone_number = message["from"]
            message_text = message["text"]["body"]
            logger.info(f"Processing message from {phone_number}: {message_text}")

            # Get or create session
            session = session_manager.get_session(phone_number)

            # Check if this is the user's first message in this session
            is_first_message = len(session["context"]) == 0

            # If it's the first message, check if the user is a registered partner
            if is_first_message:
                partner_registered = is_partner_registered(phone_number)

                if partner_registered:
                    # User is a registered partner
                    partner_name = get_partner_name(phone_number)
                    greeting = f"Hello {partner_name}! Welcome back. How can I assist you today?"
                    await send_whatsapp_message(phone_number, greeting)

                    # Update context with greeting
                    session_manager.update_context(phone_number, greeting, "assistant")

                    # Store partner info in session
                    session["partner_info"] = {"name": partner_name}
                else:
                    # User is not a registered partner
                    response = "Hi! You are not a registered partner. Please contact our sales team to register."
                    await send_whatsapp_message(phone_number, response)

                    # Update context with response
                    session_manager.update_context(phone_number, response, "assistant")
                    return {"status": "ok"}

            # Update context with user message
            session_manager.update_context(phone_number, message_text, "user")

            # Process with AI agent only if the user is a registered partner
            if "partner_info" in session:
                response = await agent.process_message(message_text)
            else:
                # For non-partners, provide a standard response
                response = "Please contact our sales team to register as a partner."

            # Update context with AI response
            session_manager.update_context(phone_number, response, "assistant")

            # Send response to WhatsApp
            await send_whatsapp_message(phone_number, response)

    except Exception as e:
        logger.error(f"Error processing webhook: {e}")

    return {"status": "ok"}

