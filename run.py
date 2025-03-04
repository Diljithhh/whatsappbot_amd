import uvicorn

def main():
    """Run the application using uvicorn."""
    uvicorn.run(
        "whatsapp_bot.app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )

if __name__ == "__main__":
    main()