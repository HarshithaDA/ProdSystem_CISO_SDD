"""Internal agent service for the local C4 container boundary."""

from __future__ import annotations

import logging
import uuid

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from RAG_Agent_VertexAI_GoogleADK import ask_rag
from Observability_Traces_Phoenix import rag_span

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)
app = FastAPI(title="Cloud Monitored RAG Agent Service", version="1.0")


class QueryRequest(BaseModel):
    prompt: str


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "agent-service"}


@app.post("/internal/query")
def query(payload: QueryRequest, x_request_id: str | None = Header(default=None)) -> dict[str, object]:
    request_id = x_request_id or str(uuid.uuid4())
    logger.info("stage=agent_logic request_id=%s", request_id)
    with rag_span("agent.orchestration", request_id=request_id):
        try:
            result = ask_rag(payload.prompt)
        except (ConnectionError, FileNotFoundError, RuntimeError, ValueError) as exc:
            logger.exception("stage=agent_logic request_id=%s status=error", request_id)
            raise HTTPException(status_code=502, detail=str(exc)) from exc
    guardrail = result["guardrail"]
    return {
        "request_id": request_id,
        "answer": result["answer"],
        "accepted": guardrail.accepted,
        "matched_markers": list(guardrail.matched_markers),
        "reason": guardrail.reason,
        "results": result["results"],
        "hit_rate": result.get("hit_rate", 0.0),
    }
