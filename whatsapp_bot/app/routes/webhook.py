from fastapi import APIRouter, Request, Response, HTTPException
from whatsapp_bot.  app.services.firestore_service import get_partner_greeting, store_image_in_firestore, is_partner_registered
from whatsapp_bot.app.services.nlp_service import DealerAgent
from whatsapp_bot. app.services.whatsapp_service import send_whatsapp_message, send_service_menu, send_button_message
import json
import os
import logging
import hmac
import hashlib
from datetime import datetime
from typing import Dict
from whatsapp_bot.app.services.sessions import SessionManager

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
        message_type = message.get("type", "text")

        # Fetch session data
        session = SessionManager().get_session(phone_number)

        # Check if partner_info is not in session, verify partner status
        if "partner_info" not in session:
            logger.info(f"Checking partner status for phone_number: {phone_number}")
            is_partner = is_partner_registered(phone_number)

            if is_partner:
                # Get partner greeting to extract name
                greeting_message = get_partner_greeting(phone_number)
                partner_name = greeting_message[3:-1]  # Remove "Hi " and "!"
                session["partner_info"] = {"name": partner_name}
                logger.info(f"Partner verified: {partner_name} for phone_number: {phone_number}")
            else:
                session["partner_info"] = None
                logger.info(f"Not a registered partner: {phone_number}")

        # Check if this is an image message
        if message_type == "image":
            return await handle_image_message(message, phone_number, session)

        # Check if this is an interactive message response
        if message_type == "interactive":
            return await handle_interactive_response(message, phone_number)

        # Handle text messages
        message_text = message["text"]["body"].lower()
        logger.info(f"Processing message from {phone_number}: {message_text}")

        # Check if the user is in a specific flow (like product request)
        if session.get("current_flow") == "product_request":
            return await handle_product_request_flow(message_text, phone_number, session)

        # Generate response
        if session["partner_info"]:
            partner_name = session["partner_info"]["name"]

            # Check if the message is asking for assistance or services
            if any(keyword in message_text for keyword in ["help", "assist", "service", "menu", "options", "hi", "hello"]):
                # Send a greeting message first
                greeting = f"Hello {partner_name}! Here are the services I can help you with:"
                await send_whatsapp_message(phone_number, greeting)

                # Then send the interactive service menu
                await send_service_menu(phone_number, "AMD Partner Services")
                return {"status": "success", "message": "Service menu sent"}
            else:
                # For other messages, send a standard response
                response = f"Hello {partner_name}! How can I assist you today? Type 'menu' to see available services."
                await send_whatsapp_message(phone_number, response)
                return {"status": "success", "message": response}
        else:
            response = "Please contact our sales team to register as a partner."
            await send_whatsapp_message(phone_number, response)
            return {"status": "success", "message": response}

    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return {"status": "error", "message": str(e)}

async def handle_image_message(message, phone_number, session):
    """Handle incoming image messages"""
    try:
        # Extract image data
        image_data = message.get("image", {})
        image_id = image_data.get("id")
        image_caption = message.get("caption", "")

        logger.info(f"Processing image from phone_number: {phone_number}, image_id: {image_id}")

        # Check if the user is a registered partner - we should already have this info from the main handler
        if not session.get("partner_info"):
            logger.info(f"Not a registered partner: {phone_number}")
            await send_whatsapp_message(
                phone_number,
                "I noticed you sent an image, but you're not registered as a partner. Please contact our sales team to register."
            )
            return {"status": "success", "message": "Non-partner image notification sent"}

        # User is a registered partner, proceed with saving the image
        logger.info(f"Partner info found in session for phone_number: {phone_number}, proceeding to save image")

        # Get image URL from WhatsApp
        from whatsapp_bot.app.services.whatsapp_service import get_media_url

        # Get the media URL
        media_url_result = await get_media_url(image_id)

        if media_url_result.get("status") == "error":
            error_message = media_url_result.get('message')
            logger.error(f"Error getting media URL: {error_message}")
            await send_whatsapp_message(
                phone_number,
                "Sorry, I couldn't process your image. Please try again."
            )
            return {"status": "error", "message": error_message}

        # Log media information for debugging
        logger.info(f"Media information: mime_type={media_url_result.get('mime_type')}, file_size={media_url_result.get('file_size')}")

        # Store the image in Firestore
        result = await store_image_in_firestore(
            phone_number,
            media_url_result.get("url"),
            image_id,
            image_caption
        )

        if result.get("status") == "success":
            # Send success message with storage details
            storage_path = result.get("data", {}).get("storagePath", "")
            logger.info(f"Image successfully stored at path: {storage_path}")

            await send_whatsapp_message(
                phone_number,
                "Your image has been uploaded successfully! You can send more images or type 'menu' to see other services."
            )
            return {"status": "success", "message": "Image uploaded successfully", "storage_path": storage_path}
        else:
            # Send error message with more details
            error_message = result.get('message')
            logger.error(f"Error storing image: {error_message}")

            # Send a more user-friendly message based on the error type
            user_message = "Sorry, there was an error uploading your image. Please try again later."

            if "download" in error_message.lower():
                user_message = "Sorry, I had trouble downloading your image. Please try sending it again with a smaller file size."
            elif "storage" in error_message.lower() or "bucket" in error_message.lower() or "404" in error_message:
                user_message = "Sorry, I had trouble saving your image to our storage system. Our team has been notified of this issue."
                # Log additional details for storage errors
                logger.error(f"Storage error details: {error_message}")
            elif "metadata" in error_message.lower() or "firestore" in error_message.lower():
                user_message = "Your image was uploaded but we couldn't save the information about it. Please try again."

            await send_whatsapp_message(
                phone_number,
                user_message
            )
            return {"status": "error", "message": error_message}

    except Exception as e:
        logger.error(f"Error handling image message: {e}")
        await send_whatsapp_message(
            phone_number,
            "Sorry, I encountered an error processing your image. Please try again later."
        )
        return {"status": "error", "message": str(e)}

async def handle_interactive_response(message, phone_number):
    """Handle responses from interactive messages"""
    try:
        interactive_data = message.get("interactive", {})
        interactive_type = interactive_data.get("type")

        # Fetch session data
        session = SessionManager().get_session(phone_number)

        if interactive_type == "list_reply":
            selected_id = interactive_data.get("list_reply", {}).get("id")
            selected_title = interactive_data.get("list_reply", {}).get("title")

            logger.info(f"User {phone_number} selected: {selected_id} - {selected_title}")

            # Handle different service selections
            if selected_id == "upload_product_images":
                # Directly instruct the user to send images
                response = "Please send your product images as attachments. You can also add a caption to describe each image. I'll automatically save them to your partner account."
                await send_whatsapp_message(phone_number, response)
                return {"status": "success", "message": "Upload instructions sent"}

            elif selected_id == "request_new_product":
                response = "To request a new product, please provide the following details:\n\n1. Product name\n2. Product category\n3. Specifications\n4. Quantity needed"
                await send_whatsapp_message(phone_number, response)

                # Ask if they want to proceed with a form
                buttons = [
                    {"id": "start_product_request", "title": "Start Request"},
                    {"id": "back_to_menu", "title": "Back to Menu"}
                ]
                await send_button_message(
                    phone_number,
                    "Would you like to start a new product request now?",
                    buttons
                )
                return {"status": "success", "message": "Product request info sent"}

            elif selected_id == "technical_support":
                response = "For technical support, please describe your issue in detail. Our support team will get back to you within 24 hours."
                await send_whatsapp_message(phone_number, response)

                # Offer common support categories
                buttons = [
                    {"id": "hardware_support", "title": "Hardware Issue"},
                    {"id": "software_support", "title": "Software Issue"},
                    {"id": "other_support", "title": "Other Issue"}
                ]
                await send_button_message(
                    phone_number,
                    "What type of technical support do you need?",
                    buttons
                )
                return {"status": "success", "message": "Support options sent"}

            elif selected_id == "order_status":
                response = "To check your order status, please provide your order number. Format: ORD-XXXXX"
                await send_whatsapp_message(phone_number, response)
                return {"status": "success", "message": response}

            else:
                response = "I'm not sure how to process that selection. Please try again or type 'menu' to see available services."
                await send_whatsapp_message(phone_number, response)
                return {"status": "success", "message": response}

        elif interactive_type == "button_reply":
            button_id = interactive_data.get("button_reply", {}).get("id")
            button_title = interactive_data.get("button_reply", {}).get("title")

            logger.info(f"User {phone_number} clicked button: {button_id} - {button_title}")

            # Handle different button responses
            if button_id == "no_cancel" or button_id == "back_to_menu":
                response = "No problem. Is there anything else I can help you with?"
                await send_whatsapp_message(phone_number, response)

                # Send the main menu again
                await send_service_menu(phone_number, "AMD Partner Services")
                return {"status": "success", "message": "Service menu sent"}

            elif button_id == "start_product_request":
                response = "Let's start your product request. Please send the product name."
                await send_whatsapp_message(phone_number, response)

                # Update session to track product request state
                session["current_flow"] = "product_request"
                session["product_request_step"] = "name"

                return {"status": "success", "message": response}

            elif button_id.startswith("category_"):
                # Handle category selection for product request
                category = button_id.replace("category_", "")
                category_title = button_title

                # Save the category in the session
                session["product_category"] = category_title
                session["product_request_step"] = "specs"

                # Ask for specifications
                response = f"You've selected the category: {category_title}. Please provide the specifications for this product:"
                await send_whatsapp_message(phone_number, response)
                return {"status": "success", "message": response}

            elif button_id in ["hardware_support", "software_support", "other_support"]:
                support_type = button_id.split("_")[0].capitalize()
                response = f"You've selected {support_type} Support. Please describe your issue in detail, and our support team will assist you."
                await send_whatsapp_message(phone_number, response)
                return {"status": "success", "message": response}

            elif button_id == "need_more_help":
                response = "What else can I help you with today?"
                await send_whatsapp_message(phone_number, response)
                # Send the main menu again
                await send_service_menu(phone_number, "AMD Partner Services")
                return {"status": "success", "message": "Service menu sent"}

            elif button_id == "done_for_now":
                response = "Thank you for using AMD Partner Services. Have a great day! Feel free to message us anytime you need assistance."
                await send_whatsapp_message(phone_number, response)
                return {"status": "success", "message": response}

            else:
                response = "I'm not sure how to process that selection. Please try again or type 'menu' to see available services."
                await send_whatsapp_message(phone_number, response)
                return {"status": "success", "message": response}

        return {"status": "error", "message": "Unsupported interactive message type"}

    except Exception as e:
        logger.error(f"Error handling interactive response: {e}")
        return {"status": "error", "message": str(e)}

async def handle_product_request_flow(message_text: str, phone_number: str, session: dict):
    """Handle the product request flow based on the current step"""
    current_step = session.get("product_request_step", "name")

    if current_step == "name":
        # Save the product name
        session["product_name"] = message_text
        session["product_request_step"] = "category"

        # Ask for category
        response = f"Great! You're requesting the product: {message_text}\n\nNow, please select the product category:"
        await send_whatsapp_message(phone_number, response)

        # Send category options as buttons
        buttons = [
            {"id": "category_processor", "title": "Processor"},
            {"id": "category_graphics", "title": "Graphics Card"},
            {"id": "category_motherboard", "title": "Motherboard"}
        ]
        await send_button_message(phone_number, "Select a category:", buttons)
        return {"status": "success", "message": "Category options sent"}

    elif current_step == "category" and not message_text.startswith("category_"):
        # If they typed the category instead of using buttons
        session["product_category"] = message_text
        session["product_request_step"] = "specs"

        # Ask for specifications
        response = "Please provide the specifications for this product:"
        await send_whatsapp_message(phone_number, response)
        return {"status": "success", "message": response}

    elif current_step == "specs":
        # Save the specifications
        session["product_specs"] = message_text
        session["product_request_step"] = "quantity"

        # Ask for quantity
        response = "How many units would you like to order?"
        await send_whatsapp_message(phone_number, response)
        return {"status": "success", "message": response}

    elif current_step == "quantity":
        # Save the quantity
        session["product_quantity"] = message_text

        # Complete the product request
        product_name = session.get("product_name", "Unknown")
        product_category = session.get("product_category", "Unknown")
        product_specs = session.get("product_specs", "Not provided")
        product_quantity = session.get("product_quantity", "Not specified")

        # Format the confirmation message
        confirmation = f"Thank you for your product request. Here's a summary:\n\n" \
                      f"Product: {product_name}\n" \
                      f"Category: {product_category}\n" \
                      f"Specifications: {product_specs}\n" \
                      f"Quantity: {product_quantity}\n\n" \
                      f"Your request has been submitted. Our team will review it and get back to you within 48 hours."

        await send_whatsapp_message(phone_number, confirmation)

        # Reset the flow
        session.pop("current_flow", None)
        session.pop("product_request_step", None)

        # Ask if they need anything else
        buttons = [
            {"id": "need_more_help", "title": "Need More Help"},
            {"id": "done_for_now", "title": "Done for Now"}
        ]
        await send_button_message(phone_number, "Is there anything else I can help you with?", buttons)
        return {"status": "success", "message": "Product request completed"}

    # Default response if something goes wrong
    response = "I'm not sure what information you're providing. Let's start over. Type 'menu' to see available services."
    await send_whatsapp_message(phone_number, response)

    # Reset the flow
    session.pop("current_flow", None)
    session.pop("product_request_step", None)

    return {"status": "success", "message": response}

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

