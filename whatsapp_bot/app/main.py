from fastapi import FastAPI
from whatsapp_bot.app.routes.webhook import router as webhook_router
import os
import base64
import json
from firebase_admin import credentials
import firebase_admin

app = FastAPI()

# Include webhook router
app.include_router(webhook_router, prefix="/api/v1")
# firebase_creds = os.getenv("FIREBASE_CREDENTIALS_BASE64")

# if firebase_creds:
#     decoded_creds = base64.b64decode(firebase_creds).decode("utf-8")
#     creds_dict = json.loads(decoded_creds)

#     cred = credentials.Certificate(creds_dict)
#     firebase_admin.initialize_app(cred)
# else:
#     raise ValueError("FIREBASE_CREDENTIALS not found in environment variables!")