from fastapi import APIRouter

router = APIRouter()

@router.post("/internal/tasks/grade")
async def grade_stub():
    # Stub endpoint so the URL exists; will be implemented later
    return {"status": "accepted (bootstrap)"}
