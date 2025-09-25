# Handles: POST /v1/grade_jobs/submit
# - Verifies app bearer token (SUBMIT_BEARER_TOKEN)
# - Enqueues Cloud Task with OIDC to hit /internal/tasks/grade

from __future__ import annotations
import os, json, uuid
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from google.cloud import tasks_v2
from google.api_core.exceptions import GoogleAPICallError, PermissionDenied, NotFound
from urllib.parse import urlparse

router = APIRouter()

# App-level auth (mode A: public ingress + our own token)
AUTH_TOKEN = os.getenv("SUBMIT_BEARER_TOKEN")

# Cloud Tasks / routing config
PROJECT = os.getenv("GCP_PROJECT")                   # project ID, e.g. "cloudhire-ai"
LOCATION = os.getenv("GCP_LOCATION")                 # e.g. "us-central1"
QUEUE = os.getenv("TASKS_QUEUE", "grading-jobs")
WORKER_URL = os.getenv("WORKER_URL")                 # e.g. "https://<service>/internal/tasks/grade"
TASKS_SA = os.getenv("TASKS_SERVICE_ACCOUNT_EMAIL")  # SA with run.invoker on this service

REQUIRED_ENVS = {
    "GCP_PROJECT": PROJECT,
    "GCP_LOCATION": LOCATION,
    "WORKER_URL": WORKER_URL,
    "TASKS_SERVICE_ACCOUNT_EMAIL": TASKS_SA,
}

def _require_envs() -> None:
    missing = [k for k,v in REQUIRED_ENVS.items() if not v]
    if missing:
        raise HTTPException(status_code=500, detail=f"Missing env vars: {', '.join(missing)}")

class SubmitPayload(BaseModel):
    attempt_id: str                # UUID from Rails at submit time
    user_id: str                   # public.user_info.id
    exam_id: str | None = None     # optional label if you want it
    attempt_no: int
    purpose: str = "final"
    rubric: dict | None = None
    section_map: dict | None = None  # { "multiple_choice": { "101": "Technical", ... }, ... }
    callback: dict | None = None     # { "url": "https://rails/..." }
    metadata: dict | None = None

@router.post("/v1/grade_jobs/submit")
async def submit(req: Request, payload: SubmitPayload):
    # App bearer check
    if AUTH_TOKEN and req.headers.get("authorization") != f"Bearer {AUTH_TOKEN}":
        raise HTTPException(status_code=401, detail="unauthorized")

    _require_envs()

    # Generate a job id now (idempotency is enforced in DB by attempt_id+purpose)
    job_id = str(uuid.uuid4())

    body = payload.model_dump()
    body["job_id"] = job_id

    try:
        client = tasks_v2.CloudTasksClient()
        parent = client.queue_path(PROJECT, LOCATION, QUEUE)
        
        # Extract base URL for OIDC audience
        parsed_url = urlparse(WORKER_URL)
        audience = f"{parsed_url.scheme}://{parsed_url.netloc}"

        task = {
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": WORKER_URL,  # Full URL for invocation
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps(body).encode(),
                "oidc_token": {
                    "service_account_email": TASKS_SA,
                    "audience": audience
                }
            }
        }
        client.create_task(parent=parent, task=task)
    
    except NotFound as e:
        raise HTTPException(status_code=500, detail=f"Queue not found: {PROJECT}/{LOCATION}/{QUEUE}") from e
    except PermissionDenied as e:
        raise HTTPException(status_code=500, detail="Permission denied creating task. Ensure the RUNTIME service account has 'Cloud Tasks Enqueuer'.") from e
    except GoogleAPICallError as e:
        raise HTTPException(status_code=500, detail=f"Cloud Tasks error: {e}") from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unhandled error: {e.__class__.__name__}: {e}")

    return {"job_id": job_id, "status": "queued"}