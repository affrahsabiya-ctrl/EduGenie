import os
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from services import EduGenieService

BASE_DIR = Path(__file__).resolve().parent
# The backend-local file is the source of truth, even when a parent shell has
# stale values from a previous project layout.
load_dotenv(BASE_DIR / ".env", override=True)

allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5500,http://127.0.0.1:5500",
    ).split(",")
    if origin.strip()
]

app = FastAPI(title="EduGenie API", description="AI learning tools.", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
service = EduGenieService(
    api_key=os.getenv("GEMINI_API_KEY"),
    gemini_model=os.getenv("GEMINI_MODEL", "gemini-3.8-flash"),
    fallback_models=os.getenv("GEMINI_FALLBACK_MODELS", "gemini-3.5-flash-lite").split(","),
    local_explanations=os.getenv("USE_LOCAL_EXPLANATION_MODEL", "false").lower() == "true",
    request_timeout_ms=int(os.getenv("GEMINI_TIMEOUT_MS", "30000")),
)

class LearningRequest(BaseModel):
    input: str = Field(min_length=2, max_length=20_000)

class LearningResponse(BaseModel):
    task: Literal["qa", "explain", "quiz", "summarize", "recommendations"]
    model: str
    result: str

@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    return {"name": "EduGenie API", "docs": "/docs", "health": "/health"}

@app.get("/health")
async def health() -> dict[str, str | bool]:
    return {"status": "ok", "gemini_configured": service.gemini_configured, "explanation_provider": service.explanation_provider}

async def run_task(task: str, user_input: str) -> LearningResponse:
    try:
        result, model = await service.run(task, user_input)
        return LearningResponse(task=task, model=model, result=result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

@app.post("/qa", response_model=LearningResponse)
async def question_answer(request: LearningRequest) -> LearningResponse:
    return await run_task("qa", request.input)

@app.post("/explain", response_model=LearningResponse)
async def explain(request: LearningRequest) -> LearningResponse:
    return await run_task("explain", request.input)

@app.post("/quiz", response_model=LearningResponse)
async def generate_quiz(request: LearningRequest) -> LearningResponse:
    return await run_task("quiz", request.input)

@app.post("/summarize", response_model=LearningResponse)
async def summarize(request: LearningRequest) -> LearningResponse:
    return await run_task("summarize", request.input)

@app.post("/learn/recommendations", response_model=LearningResponse)
async def learning_path(request: LearningRequest) -> LearningResponse:
    return await run_task("recommendations", request.input)
