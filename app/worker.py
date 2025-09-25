# Handles: POST /internal/tasks/grade (Cloud Tasks target)
# Flow:
# - Upsert grade_jobs (processing)
# - Fetch latest answers for user from public.user_responses
# - Grade via Gemini (2.5-flash by default via env)
# - Insert grade_results (with section), grade_overall
# - Render and upload PDF, insert artifact
# - Mark completed; POST signed webhook to Rails if provided

from __future__ import annotations
import os, time, hmac, hashlib, json
from fastapi import APIRouter, Request, HTTPException
import httpx

from app.supa import (
    upsert_job, set_job_status,
    fetch_answers_for_user, insert_results, upload_pdf
)
from app.grading import grade
from app.pdf import render_report_pdf

router = APIRouter()

# Shared HMAC secret for webhook signing (must match Rails AI_WEBHOOK_SECRET)
AI_WEBHOOK_SECRET = os.getenv("AI_WEBHOOK_SECRET")  # optional but recommended

def _hmac_headers(raw: bytes) -> dict:
    if not AI_WEBHOOK_SECRET:
        return {}
    sig = hmac.new(AI_WEBHOOK_SECRET.encode(), raw, hashlib.sha256).hexdigest()
    return {
        "X-Signature": f"sha256={sig}",
        "X-Timestamp": str(int(time.time())),
        "X-Key-Id": "python-v1"
    }

def _section_lookup(section_map: dict | None, qtype: str, qid: int) -> str | None:
    if not section_map:
        return None
    m = section_map.get(qtype) or {}
    return m.get(str(qid)) or m.get(int(qid)) or None

@router.post("/internal/tasks/grade")
async def grade_task(req: Request):
    payload = await req.json()

    # Required minimal fields from submit
    try:
        job_id = payload["job_id"]
        attempt_id = payload["attempt_id"]
        user_id = payload["user_id"]
    except KeyError as e:
        raise HTTPException(status_code=422, detail=f"Missing key: {e}")

    purpose = payload.get("purpose", "final")
    section_map = payload.get("section_map") or {}
    triggered_by = (payload.get("metadata") or {}).get("triggered_by")

    # Upsert job row: processing
    upsert_job(job_id=job_id, attempt_id=attempt_id, user_id=user_id,
               purpose=purpose, triggered_by=triggered_by)

    try:
        answers = fetch_answers_for_user(user_id)
        if not answers:
            raise HTTPException(status_code=422, detail=f"No answers found for user {user_id}")

        # Grade with Gemini (or dummy if env says otherwise)
        per_q, overall, cost = grade(answers, payload.get("rubric") or {})

        # Attach section label to each result from section_map
        for r, a in zip(per_q, answers):
            r["section"] = _section_lookup(section_map, a["question_type"], a["question_id"])
            r["question_type"] = a["question_type"]
            r["question_id"] = a["question_id"]

        # Persist results
        insert_results(job_id, per_q, overall)

        # Render and upload PDF (group the results by section in the template)
        pdf_bytes = render_report_pdf(attempt_id, per_q, overall)
        pdf_path = upload_pdf(job_id, pdf_bytes)

        # Mark completed
        set_job_status(job_id, "completed",
                       finished_at=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                       cost_input_tokens=cost.get("input_tokens", 0),
                       cost_output_tokens=cost.get("output_tokens", 0),
                       cost_usd=cost.get("usd", 0.0))

        # Optional webhook back to Rails
        cb = payload.get("callback")
        if cb and cb.get("url"):
            body = {
                "job_id": job_id,
                "attempt_id": attempt_id,
                "user_id": user_id,
                "status": "succeeded",
                "grades": per_q,
                "overall": overall,
                "artifacts": {"pdf_path": pdf_path}
            }
            raw = json.dumps(body, separators=(",", ":")).encode()
            headers = {"Content-Type": "application/json"} | _hmac_headers(raw)
            async with httpx.AsyncClient(timeout=15) as hc:
                r = await hc.post(cb["url"], content=raw, headers=headers)
                if r.status_code >= 300:
                    # Let Cloud Tasks retry webhook transiently
                    raise HTTPException(status_code=502, detail=f"Webhook failed {r.status_code}")

        return {"status": "ok", "job_id": job_id, "pdf_path": pdf_path}

    except Exception as e:
        set_job_status(job_id, "failed", error_message=str(e))
        # Re-raise so Cloud Tasks can retry according to queue settings
        raise
