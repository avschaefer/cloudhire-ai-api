import os, uuid
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

router = APIRouter()
AUTH_TOKEN = os.environ.get("SUBMIT_BEARER_TOKEN")

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
    if AUTH_TOKEN:
        if req.headers.get("authorization") != f"Bearer {AUTH_TOKEN}":
            raise HTTPException(status_code=401, detail="unauthorized")
    # For bootstrap: no queue yet; just return a stable fake job id
    job_id = str(uuid.uuid4())
    return {"job_id": job_id, "status": "queued (bootstrap)"}
