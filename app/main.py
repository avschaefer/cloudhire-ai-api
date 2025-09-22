import logging
import os
from fastapi import FastAPI
from app.submit import router as submit_router
from app.worker import router as worker_router

# Configure logging
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

def validate_environment():
    """Validate that all required environment variables are set"""
    required_vars = [
        "SUPABASE_URL",
        "SUPABASE_SERVICE_KEY",
        "GEMINI_API_KEY",
        "SUBMIT_BEARER_TOKEN",
        "GCP_PROJECT",
        "GCP_LOCATION",
        "WORKER_URL",
        "TASKS_SERVICE_ACCOUNT_EMAIL"
    ]

    missing = []
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)

    if missing:
        error_msg = f"Missing required environment variables: {', '.join(missing)}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)

    logger.info("Environment validation passed")

# Validate environment on startup
validate_environment()

app = FastAPI(title="Cloudhire AI API")

@app.get("/health")
def health():
    return {"ok": True}

app.include_router(submit_router)
app.include_router(worker_router)
