import os, json, uuid
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from google.cloud import tasks_v2

router = APIRouter()

AUTH_TOKEN = os.environ.get("SUBMIT_BEARER_TOKEN")

PROJECT = os.environ["GCP_PROJECT"]               # e.g., 842859587314 or project-id
LOCATION = os.environ["GCP_LOCATION"]             # e.g., us-central1
QUEUE = os.environ.get("TASKS_QUEUE", "grading-jobs")
WORKER_URL = os.environ["WORKER_URL"]             # https://cloudhire-ai-api-842859587314.us-central1.run.app/internal/tasks/grade
TASKS_SA = os.environ["TASKS_SERVICE_ACCOUNT_EMAIL"]  # 842859587314-compute@developer.gserviceaccount.com

class SubmitPayload(BaseModel):
    attempt_id: str
    exam_id: str
    user_id: str
    attempt_no: int
    purpose: str = "final"
    rubric: dict | None = None
    model: dict | None = None
    callback: dict | None = None
    metadata: dict | None = None

@router.post("/v1/grade_jobs/submit")
async def submit(req: Request, payload: SubmitPayload):
    if AUTH_TOKEN and req.headers.get("authorization") != f"Bearer {AUTH_TOKEN}":
        raise HTTPException(status_code=401, detail="unauthorized")

    job_id = str(uuid.uuid4())

    tclient = tasks_v2.CloudTasksClient()
    parent = tclient.queue_path(PROJECT, LOCATION, QUEUE)

    body = payload.model_dump()
    body["job_id"] = job_id

    task = {
        "http_request": {
            "http_method": tasks_v2.HttpMethod.POST,
            "url": WORKER_URL,
            "headers": {"Content-Type": "application/json"},
            "oidc_token": {
                "service_account_email": TASKS_SA,
                "audience": WORKER_URL
            },
            "body": json.dumps(body).encode(),
        }
    }

    tclient.create_task(parent=parent, task=task)
    return {"job_id": job_id, "status": "queued"}
