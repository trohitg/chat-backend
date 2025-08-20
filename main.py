from app.main import app

# This file is the entry point for the application
# It imports the FastAPI app from the app module

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)