from fastapi import FastAPI
from whatsapp_bot.app.routes.webhook import router as webhook_router

app = FastAPI()

# Include webhook router
app.include_router(webhook_router, prefix="/api/v1")
