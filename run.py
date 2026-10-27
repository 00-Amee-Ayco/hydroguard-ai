"""Start HydroGuard: python run.py. Process environment overrides local .env."""
from dotenv import load_dotenv
import uvicorn

if __name__ == "__main__":
    load_dotenv()
    uvicorn.run("hydroguard.api:app", host="127.0.0.1", port=8000, access_log=False)
