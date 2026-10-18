"""FastAPI gateway for the guarded Cloud Monitored RAG flow."""

from __future__ import annotations

import logging
import os
import uuid

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from Observability_Traces_Phoenix import rag_span

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)
app = FastAPI(title="Cloud Monitored RAG API Gateway", version="1.0")
AGENT_URL = os.getenv("AGENT_SERVICE_URL", "http://localhost:8081").rstrip("/")


class QueryRequest(BaseModel):
    prompt: str


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "api-gateway"}


@app.post("/query")
async def query(payload: QueryRequest, request: Request) -> JSONResponse:
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    logger.info("stage=api_gateway request_id=%s", request_id)
    with rag_span("api.gateway", request_id=request_id, route="/query"):
        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                response = await client.post(
                    f"{AGENT_URL}/internal/query",
                    json={"prompt": payload.prompt},
                    headers={"x-request-id": request_id},
                )
        except httpx.HTTPError as exc:
            logger.exception("stage=api_gateway request_id=%s status=error", request_id)
            raise HTTPException(status_code=502, detail="Agent service is unavailable.") from exc
    if response.status_code >= 500:
        raise HTTPException(status_code=502, detail=response.text)
    body = response.json()
    body["request_id"] = request_id
    body["flow"] = [
        "client",
        "api_gateway",
        "guardrails",
        "agent_logic",
        "vector_store",
        "telemetry",
    ]
    return JSONResponse(status_code=200 if body["accepted"] else 422, content=body)
