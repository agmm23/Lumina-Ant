"""
Lumina_Ant - Router de Chat/Copilot IA
Endpoints para el chat interactivo con IA
"""

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.chat_service import get_chat_service, SUGGESTED_PROMPTS
import os, glob, json
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


# ── Schemas ─────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    history: List[Dict[str, str]] = []


class ChatResponse(BaseModel):
    role: str = "assistant"
    content: str
    intents: List[str] = []
    data_sources: List[str] = []
    suggested_followups: List[str] = []
    usage: Dict[str, Any] = {}


class SuggestedPromptsResponse(BaseModel):
    prompts: list


# ── Endpoints ───────────────────────────────────────────────────────

@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest, db: Session = Depends(get_db)):
    """
    Envía un mensaje al Copilot IA y recibe una respuesta completa
    basada en los datos reales del negocio.
    """
    service = get_chat_service()
    result = await service.chat(request.message, request.history, db)

    result["suggested_followups"] = service.get_followups(
        result.get("intents", []),
        result.get("data_sources", []),
    )

    logger.info(f"Chat response: intents={result['intents']}, sources={result['data_sources']}")
    return ChatResponse(**result)


@router.post("/stream")
async def chat_stream(request: ChatRequest, db: Session = Depends(get_db)):
    """
    Streaming del Copilot IA via Server-Sent Events (SSE).
    Cada evento tiene el formato: data: {"type": "delta"|"done"|"error", ...}
    """
    service = get_chat_service()

    return StreamingResponse(
        service.stream_chat(request.message, request.history, db),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/suggested-prompts", response_model=SuggestedPromptsResponse)
def get_suggested_prompts():
    """Retorna las preguntas sugeridas para el chat."""
    return {"prompts": SUGGESTED_PROMPTS}


@router.get("/stats")
def get_chat_stats(days: int = 7):
    """
    Estadísticas agregadas de uso del chat leyendo los logs JSONL.
    Retorna: consultas totales, tokens consumidos, costo estimado, intents más usados.
    """
    log_dir = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "..", "logs")
    )
    files = sorted(glob.glob(os.path.join(log_dir, "chat_*.jsonl")))[-days:]

    total_queries = 0
    total_input = 0
    total_output = 0
    intent_counts: Dict[str, int] = {}
    source_counts: Dict[str, int] = {}
    needs_review = 0
    errors = 0
    by_day: Dict[str, Dict[str, Any]] = {}

    for filepath in files:
        day = os.path.basename(filepath).replace("chat_", "").replace(".jsonl", "")
        day_stats = {"queries": 0, "input_tokens": 0, "output_tokens": 0}
        try:
            with open(filepath, encoding="utf-8") as f:
                for line in f:
                    entry = json.loads(line)
                    total_queries += 1
                    day_stats["queries"] += 1
                    tokens = entry.get("tokens", {})
                    inp = tokens.get("input_tokens", 0)
                    out = tokens.get("output_tokens", 0)
                    total_input += inp
                    total_output += out
                    day_stats["input_tokens"] += inp
                    day_stats["output_tokens"] += out
                    for intent in entry.get("intents", []):
                        intent_counts[intent] = intent_counts.get(intent, 0) + 1
                    for src in entry.get("data_sources", []):
                        source_counts[src] = source_counts.get(src, 0) + 1
                    if entry.get("NEEDS_REVIEW"):
                        needs_review += 1
                    if entry.get("error"):
                        errors += 1
        except Exception:
            pass
        by_day[day] = day_stats

    # Costo estimado con Claude Haiku (precios públicos a 2025)
    # Input: $0.80/1M tokens, Output: $4.00/1M tokens
    cost_usd = (total_input * 0.80 + total_output * 4.00) / 1_000_000

    top_intents = sorted(intent_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    top_sources = sorted(source_counts.items(), key=lambda x: x[1], reverse=True)

    return {
        "period_days": days,
        "total_queries": total_queries,
        "tokens": {
            "input": total_input,
            "output": total_output,
            "total": total_input + total_output,
        },
        "estimated_cost_usd": round(cost_usd, 6),
        "avg_tokens_per_query": round((total_input + total_output) / total_queries, 0) if total_queries else 0,
        "needs_review": needs_review,
        "errors": errors,
        "top_intents": [{"intent": k, "count": v} for k, v in top_intents],
        "top_sources": [{"source": k, "count": v} for k, v in top_sources],
        "by_day": by_day,
    }
