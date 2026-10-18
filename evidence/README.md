# End-to-end evidence

This directory is the sanitized evidence bundle for the local C4 request path.

## Capture

```powershell
docker compose up --build -d weaviate phoenix
docker compose run --rm ingestion-service python -c "from pathlib import Path; from ingestion_weaviate import ingest_directory; print(ingest_directory(Path('/data/docs')))"
docker compose up --build -d agent-service api-gateway
.\scripts\e2e_verify.ps1
docker compose logs --no-color api-gateway agent-service > evidence\service-logs.txt
```

Open `http://localhost:6006`, filter project `cloud-monitored-rag`, and capture a Phoenix trace screenshot showing `api.gateway`, `agent.orchestration`, `rag.run`, `rag.retrieval`, and `rag.generation`. Do not include credentials or document contents in published screenshots.

The Phoenix service is built locally from [`Dockerfile.phoenix`](../Dockerfile.phoenix)
so the stack does not depend on a separately tagged Phoenix registry image.

The expected response includes a `flow` array and `request_id`; `service-logs.txt` records the gateway and agent stage markers. The trace screenshot is intentionally captured from the running local dashboard rather than checked into source control.
