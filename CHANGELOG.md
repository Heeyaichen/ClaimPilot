
# Changelog

All notable changes to ClaimPilot are documented here.

## [v1.0.0] — Draft (not yet tagged)

### Phase 1 — Foundation & Ingestion
- Azure Bicep IaC for 12 resources + RBAC module
- Document Intelligence service wrapper (custom ACORD model)
- Content Understanding service wrapper (REST + schema-driven)
- Speech service wrapper (STT with auto-detect)
- Translator service wrapper (English passthrough)
- ACORD synthetic dataset generator (50-200 PDFs + ground truth)
- Pydantic models for all ingestion outputs
- 37 unit tests

### Phase 2 — Durable Functions Pipeline
- FastAPI application factory with multipart upload
- Cosmos DB claim state store (8-step pipeline state machine)
- SignalR broadcaster for real-time step events
- Blob storage service for file uploads
- Next.js 15 dashboard with upload form and status tracker
- Pipeline orchestrator with all 8 steps
- 66 tests (doubled from Phase 1)

### Phase 3 — Foundry Agents
- 4 real agent classes replacing pipeline stubs:
  - ClassifierAgent: claim type + routing confidence
  - ExtractorAgent: structured field extraction + validation
  - FraudDetectionAgent: multi-signal fraud risk scoring
  - DecisionAgent: traceable adjudication with reasoning chain
- FoundryAgentClient: JSON parsing with retry, Pydantic validation
- Azure AI Search service (policies-index + claims-history-index)
- AgentOps / App Insights tracing module
- Search fixture generator (50 policies + 100 claims)
- Extraction evaluation harness (F1 >= 0.90)
- 127 unit tests

### Phase 4 — Voice Live Interface
- Voice Live session service with semantic VAD
- ClaimLookupTool: 4 methods backed by Cosmos DB
- MCP claim server adapter (JSON-RPC 2.0, inline + remote modes)
- Adjuster API routes (session URL, WebSocket relay, claim context)
- Frontend adjuster page with microphone capture and transcript panel
- 171 unit tests

### Phase 5 — Frontend Polish, Evaluation, README
- Polished claim submission form with file validation
- Complete claim detail page with all extracted fields
- DecisionViewer component with reasoning chain and evidence links
- Adjuster queue page (sorted by fraud risk, failed pipeline, low confidence)
- Adjuster queue backend endpoint with priority sorting
- Full evaluation suite (extraction, fraud, decision, latency metrics)
- Evaluation results report (evaluation/results/latest.json)
- Updated README reflecting actual implementation state
- Architecture diagram source (Mermaid)
- 171+ unit tests, ruff clean, frontend builds

## Release Checklist

- [ ] PR #5 merged to main
- [ ] All tests passing (ruff, pytest, frontend build)
- [ ] README evaluation results match latest.json
- [ ] Tag v1.0.0
