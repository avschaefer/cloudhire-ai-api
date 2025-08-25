import os, hashlib, time
from typing import Any, Dict, List
from supabase import create_client, Client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
REPORTS_BUCKET = os.environ.get("STORAGE_BUCKET", "reports")

def sb() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# --- grading tables helpers ---

def upsert_job(job_id: str, attempt_id: str, user_id: str, purpose: str, triggered_by: str | None) -> None:
    client = sb()
    client.table("grade_jobs").upsert({
        "id": job_id,
        "attempt_id": attempt_id,
        "user_id": user_id,
        "purpose": purpose,
        "status": "processing",
        "triggered_by": triggered_by,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }, on_conflict="id").execute()

def set_job_status(job_id: str, status: str, **fields) -> None:
    client = sb()
    client.table("grade_jobs").update({"status": status, **fields}).eq("id", job_id).execute()

def fetch_answers_for_user(user_id: str) -> List[Dict[str, Any]]:
    """
    Read the latest answer per (question_type, question_id) from public.user_responses.
    """
    client = sb()
    res = client.table("user_responses").select(
        "question_type,question_id,response_text,response_numerical,response_units,updated_at"
    ).eq("user_id", user_id).order("updated_at", desc=True).execute()

    rows = res.data or []
    seen = set()
    out: List[Dict[str, Any]] = []

    for r in rows:
        key = (r["question_type"], r["question_id"])
        if key in seen:
            continue
        seen.add(key)

        if r["response_text"]:
            txt = r["response_text"]
        elif r["response_numerical"] is not None:
            units = r.get("response_units") or ""
            txt = f"{r['response_numerical']}{(' ' + units) if units else ''}"
        else:
            txt = ""

        out.append({
            "question_type": r["question_type"],
            "question_id": r["question_id"],
            "answer_text": txt
        })
    return out

def insert_results(job_id: str, per_q: List[Dict[str, Any]], overall: Dict[str, Any]) -> None:
    client = sb()
    if per_q:
        client.table("grade_results").insert([
            {
                "job_id": job_id,
                "section": r.get("section"),
                "question_type": r["question_type"],
                "question_id": r["question_id"],
                "score": r["score"],
                "rationale": r.get("rationale"),
                "tags": r.get("tags"),
            } for r in per_q
        ]).execute()
    client.table("grade_overall").insert({"job_id": job_id, **overall}).execute()

def upload_pdf(job_id: str, pdf_bytes: bytes) -> str:
    client = sb()
    path = f"{time.strftime('%Y/%m')}/{job_id}.pdf"
    client.storage.from_(REPORTS_BUCKET).upload(path, pdf_bytes, {
        "content-type": "application/pdf",
        "upsert": "true"
    })
    sha = hashlib.sha256(pdf_bytes).hexdigest()
    client.table("artifacts").insert({
        "job_id": job_id, "kind": "pdf", "storage_path": path,
        "size_bytes": len(pdf_bytes), "sha256": sha
    }).execute()
    return path
