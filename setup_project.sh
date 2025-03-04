#!/bin/bash

# Define project structure
PROJECT_NAME="whatsapp-bot"
APP_DIR="$PROJECT_NAME/app"
MODELS_DIR="$APP_DIR/models"
SERVICES_DIR="$APP_DIR/services"
ROUTES_DIR="$APP_DIR/routes"

# Create project directories
echo "Creating project directories..."
mkdir -p $MODELS_DIR $SERVICES_DIR $ROUTES_DIR

# Create __init__.py files for Python modules
echo "Creating __init__.py files..."
touch $APP_DIR/__init__.py
touch $MODELS_DIR/__init__.py
touch $SERVICES_DIR/__init__.py
touch $ROUTES_DIR/__init__.py

# Create main.py
echo "Creating main.py..."
cat <<EOL > $APP_DIR/main.py
from fastapi import FastAPI
from routes.webhook import router as webhook_router

app = FastAPI()

# Include webhook router
app.include_router(webhook_router, prefix="/api/v1")
EOL

# Create firestore_service.py
echo "Creating firestore_service.py..."
cat <<EOL > $SERVICES_DIR/firestore_service.py
from firebase_admin import credentials, firestore, initialize_app

# Initialize Firebase Admin SDK
cred = credentials.Certificate("path/to/your/firebase/credentials.json")
initialize_app(cred)
db = firestore.client()

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
EOL

# Create nlp_service.py
echo "Creating nlp_service.py..."
cat <<EOL > $SERVICES_DIR/nlp_service.py
import google.generativeai as genai

class DealerAgent:
    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-pro')
        self.context = {
            "dealer_services": {
                "product_categories": [
                    "Processors (AMD Ryzen Series)",
                    "Graphics Cards (Radeon RX Series)",
                    "Motherboards",
                    "Memory",
                    "Storage"
                ],
                "support_services": [
                    "Technical Support",
                    "Warranty Claims",
                    "Product Returns",
                    "Order Status"
                ]
            }
        }
        self.conversation = self.model.start_chat(history=[
            {"role": "user", "parts": [self._create_system_prompt()]}
        ])

    def _create_system_prompt(self) -> str:
        return f"""
        You are an AMD dealer's assistant. Here are the services and products you can help with:
        Product Categories: {', '.join(self.context['dealer_services']['product_categories'])}
        Support Services: {', '.join(self.context['dealer_services']['support_services'])}
        Follow these rules:
        1. Always start with a welcome message and ask for the customer's name.
        2. Keep context of the conversation and refer back to previous information.
        3. Guide through categories before showing specific products.
        """

    async def process_message(self, message: str) -> str:
        try:
            response = await self.conversation.send_message_async(message)
            return response.text
        except Exception as e:
            return f"Error processing message: {str(e)}"
EOL

# Create webhook.py
echo "Creating webhook.py..."
cat <<EOL > $ROUTES_DIR/webhook.py
from fastapi import APIRouter, Request, HTTPException
from services.firestore_service import is_partner_registered, get_partner_name
from services.nlp_service import DealerAgent

router = APIRouter()
agent = DealerAgent(api_key="your_gemini_api_key_here")

@router.post("/webhook")
async def webhook(request: Request):
    data = await request.json()

    # Verify webhook secret (optional)
    if data.get("secret") != "your_webhook_secret_here":
        raise HTTPException(status_code=403, detail="Invalid secret")

    # Extract phone number and message from payload
    phone_number = data["entry"][0]["changes"][0]["value"]["messages"][0]["from"]
    message_text = data["entry"][0]["changes"][0]["value"]["messages"][0]["text"]["body"]

    # Check if partner is registered in Firestore DB
    if is_partner_registered(phone_number):
        partner_name = get_partner_name(phone_number)
        reply_text = f"Hello {partner_name}, how can I assist you today?"
    else:
        reply_text = "You are not registered as a partner. Please contact support."

    # Process NLP response (optional)
    nlp_response = await agent.process_message(message_text)

    # Return response to WhatsApp (Meta API handles this part)
    return {"text": reply_text}
EOL

# Create .env file
echo "Creating .env file..."
cat <<EOL > $PROJECT_NAME/.env
GEMINI_API_KEY=your_gemini_api_key_here
FIREBASE_CREDENTIALS_PATH=path/to/your/firebase/credentials.json
WEBHOOK_SECRET=your_webhook_secret_here
EOL

# Print success message
echo "Project setup complete! Navigate to the '$PROJECT_NAME' directory to start working on your bot."
