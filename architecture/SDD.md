# CISO Solution Design Document: Cloud Monitored RAG

**Document ID:** CM-RAG-SDD-001  
**Version:** 1.0  
**Status:** Phase-4 local reference implementation  
**Owner:** Security Engineering (with AI Platform and Data Platform)  
**Review cadence:** At every model, retrieval schema, or trust-boundary change

## 1. Executive summary

Cloud Monitored RAG is a controlled enterprise question-answering path for authorized PDF knowledge bases. A client request enters a FastAPI API Gateway, is sent to an internal Agent Service, passes prompt-injection guardrails before retrieval, performs hybrid retrieval from a local or hosted Weaviate vector store, generates a grounded answer, and exports OpenTelemetry spans to Arize Phoenix.

The phase-4 local deployment is reproducible with [`docker-compose.yml`](../docker-compose.yml). The compose profile includes the API Gateway, Agent Service, Weaviate Vector DB, Phoenix dashboard, and an optional ingestion service. Phoenix is built locally from [`Dockerfile.phoenix`](../Dockerfile.phoenix) to avoid an external image-tag dependency. Cloud behavior remains supported through the existing Vertex AI and Weaviate Cloud settings.

## 2. Scope and assumptions

### In scope

- Five production layers: Experience, Guardrails, Agentic Logic, Vector RAG, and Telemetry.
- One controlled request path with explicit service boundaries.
- Identity and access, prompt governance, model egress, document ACL, citation/freshness, and trace controls.
- Local verification and a staged rollout/rollback plan.
- Threats mapped to the three prior weekly incidents: supply-chain, rogue agent, and injection/outage.

### Assumptions and residual risks

- Local Weaviate uses anonymous access only on the isolated developer network; production must use private networking and authenticated access.
- `LOCAL_GENERATION=true` is a deterministic local evidence mode, not a production model substitute.
- The current PDF pipeline handles text PDFs and intentionally does not provide OCR.
- Production secrets, document ACLs, human approval, and hosted telemetry require deployment-specific integrations.

## 3. C4 architecture

### 3.1 System context

See [`context.mmd`](context.mmd). A user or client application asks a question. The RAG system is the controlled system of interest; identity, document sources, model inference, vector storage, and Phoenix are external dependencies or platform services.

### 3.2 Container

See [`container.mmd`](container.mmd). The API Gateway is the only public application endpoint. The Agent Service is internal and owns guardrails, orchestration, retrieval calls, and answer construction. Ingestion is an operator-only path.

### 3.3 Component

See [`component.mmd`](component.mmd). Components are aligned to code symbols: `api.query`, `agent_service.query`, `sanitize_user_query`, `hybrid_search`, `generate_grounded_answer`, and `rag_span`.

Mermaid diagrams render in GitHub and VS Code with a Mermaid extension; the same source can be imported into Draw.io for a CISO review pack.

## 4. Five production layers

| Layer | Runtime responsibility | Controls in scope | Accountability | Evidence / runtime state |
|---|---|---|---|---|
| Experience | Client surfaces and API Gateway | TLS, request schema, request ID, rate limiting, authenticated caller, no direct vector access | Security Engineering | `GET /health`, gateway logs, `e2e-response.json` |
| Guardrails | Policy and safety boundary | Prompt-injection detection, PII classification/redaction integration point, policy-as-code decision, reject before retrieval | Security Engineering | `SanitizationResult`, HTTP 422 rejection, `rag.run` attributes |
| Agentic Logic | Supervisor/worker orchestration and tool use | Explicit tool allow-list, untrusted retrieved context, approval checkpoint for consequential tools, bounded timeout | AI Platform | `agent.orchestration`, `rag.retrieval`, `rag.generation` |
| Vector RAG | Retrieval and knowledge | Document-level ACL filters, hybrid dense/BM25 retrieval, citation, freshness and source-coverage checks | Data Platform | Weaviate collection, retrieval count/score, source citations |
| Telemetry | Tracing and evaluation | OpenTelemetry spans, trace-volume/latency metrics, prompt minimization, Phoenix access control, evaluation set | SRE / Security Engineering | Phoenix project `cloud-monitored-rag`, service logs, trace screenshot |

## 5. Controlled request trace

1. **Client** sends `POST /query` with a JSON `prompt`.
2. **API Gateway** validates the schema, creates/propagates `request_id`, and calls only the internal Agent Service.
3. **Guardrails** normalizes and rejects known injection markers before retrieval or generation.
4. **Agent Logic** opens an orchestration span and invokes only the retrieval and generation functions.
5. **Vector Store** embeds the accepted query and returns ranked hybrid results from `KnowledgeChunk`.
6. **Generation** produces a grounded answer. In local evidence mode it returns the top retrieved passage; in cloud mode it calls Vertex AI.
7. **Telemetry** exports gateway, orchestration, RAG, retrieval, and generation spans to Phoenix.

The verification script records a stable `flow` array so the path can be asserted without exposing document contents.

## 6. Security posture

### Identity and access

- Public boundary: API Gateway only.
- Internal boundary: Agent Service is reachable on the compose network, not published to the host.
- Ingestion is operator-only and disabled from the default compose profile.
- Production: use workload identity or managed service accounts, private service networking, authenticated Weaviate, and least-privilege Phoenix access.

### Prompt governance

- `sanitize_user_query` rejects empty, oversized, and known prompt-injection requests.
- Retrieved text is explicitly untrusted context; document instructions cannot override the system policy.
- Production extension point: classify and redact PII before trace export; store hashes or categories rather than raw prompts where possible.
- Policy changes require a versioned evaluation set and security review.

### Model egress

- Cloud generation is disabled in local compose through `LOCAL_GENERATION=true`.
- Production Vertex AI egress must be restricted to approved projects, regions, model IDs, and service accounts.
- No API keys are stored in source or compose files; use a secret manager and short-lived credentials.

### Data protection

- Documents are mounted read-only for ingestion.
- Local vector data is persisted in a named volume.
- Production must carry document ACL metadata into the retrieval filter and encrypt data at rest and in transit.
- Phoenix must use retention limits and role-based access because traces may contain sensitive query metadata.

## 7. Threat model and incident mapping

| Threat / prior incident | Attack path | Preventive controls | Detection / response | Residual risk |
|---|---|---|---|---|
| Supply-chain incident (week 1 CI/CD artifact) | Malicious dependency or image enters build | Pin/lock dependencies, scan images, signed artifacts, minimal images, protected build identity | Dependency and container scan gates; quarantine and rebuild from known-good digest | Transitive package compromise |
| Rogue-agent incident (week 2 multi-agent system) | Agent invokes an unapproved tool or acts without oversight | Internal-only Agent Service, explicit tool allow-list, bounded timeouts, human approval for consequential actions, deny-by-default policy | Tool-call audit events and anomaly alerts; revoke service identity and roll back | Novel tool misuse not covered by policy |
| Injection/outage incident (week 3 RAG service) | Prompt injection reaches retrieval/model or a dependency outage causes cascading failure | Guardrail before retrieval, untrusted-context instruction, request limits, health checks, timeouts, canary, fallback local response | 422 guardrail signal, Phoenix traces, latency/error alerts, circuit breaker | Evasive injection patterns and Phoenix outage |

## 8. Reliability and observability

Required signals:

- API and agent availability.
- End-to-end and per-span latency.
- Trace volume and export failures.
- Guardrail rejection count and marker distribution.
- Retrieval result count, score/hit rate, citation/source coverage.
- Model input/output token counts in cloud mode.

Alert thresholds for production are set by SRE during canary: availability below 99.5% over 10 minutes, p95 latency above the agreed SLO for 5 minutes, or guardrail bypass/evaluation failure at any rate.

## 9. Rollout and rollback

1. **Build gate:** run unit/integration tests, dependency and image scans, secret scanning, and the fixed guardrail/retrieval evaluation set.
2. **Shadow:** mirror sanitized requests without returning model responses; compare trace health, retrieval quality, and cost.
3. **Canary (5%):** route one tenant or 5% of traffic to the new image. Hold for at least one business day and compare p95 latency, rejection rate, citations, and error budget.
4. **Staged expansion (25% / 50% / 100%):** expand only after the previous stage meets SLOs and security sign-off.
5. **Rollback trigger:** any guardrail bypass, unauthorized tool call, material citation regression, sustained 5xx/error-budget burn, or trace loss. Stop promotion and route traffic to the prior image.
6. **Rollback procedure:** restore the previous signed image/configuration, disable the new model or retrieval index, preserve request IDs and traces for incident review, and re-run the smoke suite.
7. **Data rollback:** retain the prior vector collection/index until the new ingestion is accepted; switch the collection alias rather than deleting the previous data.

## 10. Weekly narrative and traceability

- **Week 1 – NASA Space Data App:** established the client/data experience and CI/CD delivery narrative.
- **Week 2 – Guardrailed Multi-Agent System:** established policy enforcement, multi-agent orchestration, tool boundaries, and approval concepts.
- **Week 3 – Cloud Monitored RAG:** implemented guarded hybrid retrieval, grounded generation, and Phoenix/OpenTelemetry instrumentation.
- **Week 4 – this SDD:** joins those artifacts into a single controlled path, adds service isolation and local-compose evidence, maps threats to prior incidents, and defines production rollout/rollback.

## 11. Acceptance checklist

- [x] Master compose file for gateway, agent, vector DB, Phoenix, and optional ingestion.
- [x] Single request path with request ID and stage evidence.
- [x] Five production layers documented.
- [x] C4 context, container, and component diagrams.
- [x] Threat model mapped to the three prior incidents.
- [x] Staged rollout and rollback plan.
- [ ] Production identity, ACL enforcement, hosted secrets, and canary infrastructure (deployment-specific follow-up).
