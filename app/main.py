from fastapi import FastAPI
from app.submit import router as submit_router
from app.worker import router as worker_router

app = FastAPI(title="Cloudhire AI API (bootstrap)")

@app.get("/health")
def health():
    return {"ok": True}

app.include_router(submit_router)
app.include_router(worker_router)
