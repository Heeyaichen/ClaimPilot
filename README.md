# ClaimPilot — AI-Powered Insurance Claims Autopilot

> **Production-grade multimodal claims processing system** built on Azure AI Foundry, using Document Intelligence, Content Understanding, Azure Speech (STT + Voice Live), Azure Translator, and Foundry Agent Service to automate auto physical damage claim adjudication end-to-end.

[![Azure AI Foundry](https://img.shields.io/badge/Azure%20AI-Foundry-0078D4?style=flat-square&logo=microsoft-azure)](https://ai.azure.com)
[![Foundry Agent Service](https://img.shields.io/badge/Foundry-Agent%20Service%20GA-1D9E75?style=flat-square)](https://learn.microsoft.com/azure/ai-foundry/agents)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python)](https://python.org)
[![Next.js](https://img.shields.io/badge/Next.js-15-black?style=flat-square&logo=next.js)](https://nextjs.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)

---

## What This Is

ClaimPilot is a reference implementation of a full-stack, multi-agent insurance claims processing system. It ingests **multimodal evidence** — scanned forms, accident photos, claimant voice statements in any language — and produces a **traceable adjudication decision** with every output linked to its source evidence.

This is not a dashboard wrapper around Azure OpenAI. It is a production-grade agentic pipeline that demonstrates:

- Multi-agent orchestration with Foundry Agent Service (GA as of March 2026)
- Real document processing with Azure AI Document Intelligence custom models trained on ACORD forms
- Visual evidence analysis with Azure AI Content Understanding (multimodal: image + PDF + audio)
- Real-time voice adjuster interface via Azure Speech Voice Live API + MCP tool integration
- Human-in-loop escalation with confidence-gated routing
- Full observability via AgentOps tracing on every agent step
- Async pipeline pattern (202-accepted + polling) via Azure Durable Functions Flex Consumption

**Vertical scope:** Auto physical damage claims only. One line of business, done properly.

### Implementation Status

| Phase | Description | Status |
|---|---|---|
| Phase 1 | Foundation & Ingestion (Doc Intelligence, Content Understanding, Speech STT, Translator) | Done |
| Phase 2 | Durable Functions Pipeline (FastAPI, Cosmos DB, SignalR, Next.js dashboard) | Done |
| Phase 3 | Foundry Agents (4 real agent classes, Azure Search, tracing, extraction eval) | Done |
| Phase 4 | Voice Live Interface (adjuster copilot, MCP adapter, claim lookup tools) | Done |
| Phase 5 | Frontend Polish, Evaluation, README | Done |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         INGESTION LAYER                             │
│                                                                     │
│  Claim Form (PDF/scan)  →  Azure Doc Intelligence (custom model)   │
│  Accident Photos        →  Azure AI Content Understanding           │
│  Voice Statement        →  Azure Speech STT  →  Azure Translator    │
│                                    ↓                                │
└────────────────────────────────────┬────────────────────────────────┘
                                     │
┌────────────────────────────────────▼────────────────────────────────┐
│                    ORCHESTRATION LAYER                              │
│                  Azure AI Foundry Agent Service                     │
│                                                                     │
│  ┌──────────────────┐   ┌──────────────────┐   ┌────────────────┐  │
│  │  Classifier      │   │  Extractor       │   │  Fraud         │  │
│  │  Agent           │──▶│  Agent           │──▶│  Detection     │  │
│  │                  │   │                  │   │  Agent         │  │
│  └──────────────────┘   └──────────────────┘   └───────┬────────┘  │
│                                                         │           │
│  ┌──────────────────────────────────────────────────────▼────────┐  │
│  │              Decision & Reasoning Agent (GPT-5.4)             │  │
│  │   Approve / Escalate / Reject  +  Traceable evidence chain    │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                                     │
┌────────────────────────────────────▼────────────────────────────────┐
│                      INTERFACE LAYER                                │
│                                                                     │
│  Voice Live API + Azure Speech MCP Server  →  Adjuster copilot     │
│  Photo Avatar                              →  Customer status bot  │
│  Next.js + SignalR                         →  Real-time dashboard  │
└─────────────────────────────────────────────────────────────────────┘
                                     │
┌────────────────────────────────────▼────────────────────────────────┐
│                    OBSERVABILITY LAYER                              │
│  AgentOps tracing  │  Azure Monitor  │  Cosmos DB claim state      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

### Azure AI Services

| Service | Role in Pipeline | SDK / API |
|---|---|---|
| **Azure AI Document Intelligence** | Extract structured fields from ACORD claim forms (custom neural model) | `azure-ai-documentintelligence` |
| **Azure AI Content Understanding** | Analyze accident images + cross-file reasoning over mixed evidence | `azure-ai-contentsafety` + Content Understanding REST |
| **Azure Speech — STT** | Transcribe claimant voice statements with speaker diarization | `azure-cognitiveservices-speech` |
| **Azure Speech — Voice Live API** | Real-time speech-to-speech adjuster copilot interface | Voice Live WebSocket SDK (Python + C#) |
| **Azure Speech MCP Server** | Exposes speech capabilities as tools to Foundry agents | MCP endpoint at `mcp.ai.azure.com` |
| **Azure Translator** | Normalize non-English voice transcripts before processing | `azure-ai-translation-text` |
| **Azure AI Foundry Agent Service** | Multi-agent orchestration: classify → extract → detect → decide | `azure-ai-projects` v2 (GA) |
| **Foundry IQ (Azure AI Search)** | Policy database lookup + cross-claim pattern retrieval | `azure-search-documents` |
| **Azure AI Foundry (GPT-5.4)** | Decision reasoning with traceable source grounding | `azure-ai-projects` inference client |

### Backend

| Tool | Version | Purpose |
|---|---|---|
| **Python** | 3.11+ | Agent pipeline, API layer, all Azure SDK calls |
| **Azure Durable Functions** | Flex Consumption (Python v2) | Async pipeline orchestration — 202-accepted pattern |
| **Azure Functions** | HTTP triggers | Claim submission endpoint, status polling endpoint |
| **FastAPI** | 0.115+ | Local dev API server + test harness |
| **Azure Cosmos DB** | NoSQL (serverless) | Claim state store: step status, extracted fields, agent outputs |
| **Azure Blob Storage** | Hot tier | Raw document + image ingestion bucket |
| **Azure Service Bus** | Standard | Queue between ingestion and orchestration layers |
| **Azure SignalR Service** | Serverless | Real-time step progress events to frontend |
| **Azure Key Vault** | — | Secrets: API keys, connection strings (never in code) |
| **Azure Application Insights** | — | Distributed tracing, latency telemetry |

### Frontend

| Tool | Version | Purpose |
|---|---|---|
| **Next.js** | 15 (App Router) | Dashboard: claim submission, real-time pipeline status, decision viewer |
| **TypeScript** | 5.x | Type-safe API client, component layer |
| **Tailwind CSS** | 4.x | Styling |
| **Shadcn/ui** | latest | Component primitives |
| **@microsoft/signalr** | 8.x | Real-time step event subscription |
| **React Query (TanStack)** | v5 | Server state, polling fallback |

### Infrastructure & DevOps

| Tool | Purpose |
|---|---|
| **Azure Bicep** | Infrastructure-as-code for all Azure resources |
| **GitHub Actions** | CI/CD: lint, test, Bicep validation, deploy to Azure |
| **Docker** | Local dev containers matching Flex Consumption runtime |
| **pytest** | Agent unit tests + integration test suite |
| **Azure AI Evaluation SDK** | Ground-truth accuracy evaluation on extraction and fraud detection |

---

## Repository Structure

```
claimpilot/
├── README.md
├── CHANGELOG.md
├── LICENSE
├── .env.example
├── pyproject.toml
│
├── infra/                          # Azure Bicep IaC
│   ├── main.bicep
│   ├── modules/                    # 12 modules + RBAC
│   └── parameters/dev.bicepparam
│
├── backend/
│   ├── core/
│   │   ├── config.py               # pydantic-settings (all Azure endpoints + model IDs)
│   │   └── tracing.py              # AgentOps / App Insights tracing
│   │
│   ├── models/
│   │   ├── ingestion.py            # DocumentField, ImageAnalysisResult, VoiceTranscript
│   │   ├── claim.py                # ClaimRecord, PipelineStep, agent output models
│   │   └── voice_live.py           # Voice Live session, event, avatar models
│   │
│   ├── agents/                     # Foundry Agent definitions
│   │   ├── base.py                 # FoundryAgentClient: JSON parsing + retry + Pydantic validation
│   │   ├── classifier_agent.py     # Claim type + routing confidence
│   │   ├── extractor_agent.py      # Structured field extraction + validation
│   │   ├── fraud_agent.py          # Multi-signal fraud risk scoring
│   │   └── decision_agent.py       # Traceable adjudication with reasoning chain
│   │
│   ├── services/
│   │   ├── document_intelligence.py
│   │   ├── content_understanding.py
│   │   ├── speech.py               # STT batch transcription
│   │   ├── translator.py           # Azure Translator with English passthrough
│   │   ├── search.py               # Azure AI Search (policies + claims-history indexes)
│   │   ├── claim_state_store.py    # Cosmos DB persistence
│   │   ├── claim_lookup_tool.py    # Voice Live tool: claim data from Cosmos
│   │   ├── voice_live.py           # Voice Live session service
│   │   ├── signalr.py              # Real-time pipeline events
│   │   └── blob_storage.py         # File upload to claims-intake container
│   │
│   ├── mcp/
│   │   └── claim_server.py         # MCP-compatible claim lookup adapter
│   │
│   ├── pipeline/
│   │   ├── orchestrator.py         # 8-step pipeline with real agent activities
│   │   └── activities/             # classification, extraction, fraud_detection, reasoning
│   │
│   ├── api/
│   │   ├── app.py                  # FastAPI application factory
│   │   ├── routes.py               # POST /claims + GET /claims/{id}/status
│   │   └── adjuster_routes.py      # Session URL, WebSocket relay, queue, claim context
│   │
│   └── domains/auto_damage/        # JSON-driven domain config
│
├── frontend/                       # Next.js 15 App Router
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx            # Claim submission
│   │   │   ├── claims/[claimId]/   # Claim detail + pipeline status + decision viewer
│   │   │   └── adjuster/
│   │   │       ├── [claimId]/      # Voice Live adjuster session
│   │   │       └── queue/          # Escalated claims queue
│   │   ├── components/
│   │   │   ├── ClaimUploadForm.tsx
│   │   │   ├── ClaimStatusPage.tsx
│   │   │   ├── PipelineTracker.tsx
│   │   │   ├── DecisionViewer.tsx
│   │   │   └── voice-adjuster.tsx
│   │   └── lib/
│   │       ├── api.ts
│   │       └── signalr.ts
│
├── evaluation/
│   ├── generate_acord_synthetic.py # 200 PDFs + ground-truth JSON + training samples
│   ├── generate_search_fixtures.py # 50 policies + 100 claims history records
│   ├── evaluate_extraction.py      # Field-level F1 against ACORD ground truth
│   ├── evaluate_fraud.py           # Fraud detection precision/recall
│   ├── evaluate_decision.py        # Decision groundedness metrics
│   ├── run_full_evaluation.py      # Combined report → results/latest.json
│   ├── datasets/
│   │   ├── acord_synthetic/        # forms/, labels/, training/
│   │   └── search_fixtures/        # policies.json, claims_history.json
│   └── results/latest.json
│
├── scripts/                        # CLI smoke tests for each Azure service
│
└── tests/
    ├── unit/                       # 171+ mocked tests (no Azure needed)
    └── integration/                # Live tests (RUN_AZURE_INTEGRATION=1)
```

---

## The 7-Stage Pipeline — Deep Dive

### Stage 1 — Multimodal Ingestion

**Trigger:** File upload to Azure Blob Storage (`claims-intake` container).

**What happens:**

1. Blob trigger fires Azure Durable Functions orchestrator via starter function.
2. **Claim form (PDF/scan):** Routed to Azure AI Document Intelligence custom neural model trained on ACORD 1 (personal auto) and ACORD 2 (private passenger auto) forms. Outputs structured Markdown preserving tables and layout.
3. **Accident photos:** Routed to Azure AI Content Understanding with a pre-defined image analysis schema — extracts vehicle damage indicators, visible make/model/color, environmental conditions, license plate if visible.
4. **Voice statement (any language):** Routed to Azure Speech STT with speaker diarization enabled and semantic VAD for noisy audio environments. If detected language is not English, output is sent to Azure Translator before downstream processing.

**Key technical decision:** Content Understanding handles cross-file reasoning — it can take both the claim form Markdown and the image analysis output together and produce a unified evidence summary. This is the "pro mode" multi-input capability from the `2025-05-01-preview` API.

```python
# services/content_understanding.py (simplified)
async def analyze_claim_evidence(
    form_markdown: str,
    image_urls: list[str],
    schema: dict
) -> ClaimEvidenceSummary:
    # Content Understanding pro mode: multi-input reasoning
    response = await cu_client.analyze(
        inputs=[
            {"type": "text", "content": form_markdown},
            *[{"type": "image_url", "url": url} for url in image_urls]
        ],
        output_schema=schema,
        model="gpt-5.4"
    )
    return ClaimEvidenceSummary(**response.result)
```

---

### Stage 2 — Classification + Routing

**Agent:** `ClassifierAgent` (Foundry Agent Service)

**What it does:** Determines claim type (auto physical damage, total loss, theft, liability) and routes to the appropriate domain sub-agent configuration. Returns a confidence score — if below threshold (configurable, default 0.75), immediately escalates to human queue.

**Tools attached:**
- Foundry IQ (AI Search) — looks up policy number to validate coverage type
- Azure Speech MCP Server — can request an additional claimant call transcription if evidence is insufficient

**Domain config is JSON-driven** — adding a new claim type requires zero code changes, only a new folder under `domains/`.

```python
# agents/classifier_agent.py (simplified)
async def run_classifier(claim_id: str, evidence: ClaimEvidenceSummary) -> ClassificationResult:
    agent = project_client.agents.get_agent(CLASSIFIER_AGENT_ID)
    thread = project_client.agents.create_thread()

    project_client.agents.create_message(
        thread_id=thread.id,
        role="user",
        content=f"Classify this claim evidence: {evidence.model_dump_json()}"
    )
    run = project_client.agents.create_and_process_run(
        thread_id=thread.id, agent_id=agent.id
    )
    # AgentOps traces every run step automatically
    return ClassificationResult.model_validate_json(run.last_message.content)
```

---

### Stage 3 — Extraction + Validation

**Agent:** `ExtractorAgent` (Foundry Agent Service)

**What it does:** Extracts all structured claim fields per the domain schema. Cross-validates extracted values against the policy database via Foundry IQ. Produces a field-level confidence score for each extracted value — fields below threshold are flagged for human review without blocking the pipeline.

**Extraction schema** is defined in `domains/auto_damage/extraction_schema.json` and consumed by both Content Understanding (which builds an analyzer from it) and the Extractor Agent (which validates the outputs).

| Field Group | Source | Validation |
|---|---|---|
| Policy number, holder name | Doc Intelligence | Foundry IQ — must exist in policy index |
| Loss date, time, location | Doc Intelligence + voice | Within policy active period |
| Vehicle make, model, year, VIN | Doc Intelligence + image CU | VIN format check + cross-reference |
| Damage description | Content Understanding (image) | Matches declared loss type |
| Estimated repair amount | Doc Intelligence | Within coverage limits |
| Claimant statement | Speech STT + Translator | Sentiment + consistency flags |

---

### Stage 4 — Fraud Detection Agent

**Agent:** `FraudDetectionAgent` (Foundry Agent Service)

**What it does:** Runs a multi-signal fraud analysis. This is the hardest engineering problem in the pipeline and the most interesting thing on your resume.

**Signals analyzed:**

- **Claim pattern anomaly:** Foundry IQ searches for the same policy holder's prior claims history. Statistical outlier scoring via GPT-5.4 with function calling.
- **Image forensics via Content Understanding:** Checks for photo metadata inconsistencies, damage patterns inconsistent with the stated accident type (e.g., front-end damage from a claimed rear collision).
- **Voice sentiment analysis:** Detects hedging language, inconsistency between statement and form data, undue hesitation patterns from Speech STT transcript.
- **Cross-reference integrity:** Verifies that parties named in the form match voice statement names match repair shop records.

**Output:** `FraudRiskScore` (0.0–1.0) with a structured rationale. Scores above 0.7 automatically escalate to the Special Investigations Unit queue (human-in-loop gate). Scores 0.4–0.7 flag for adjuster review. Below 0.4 proceeds to automated decision.

---

### Stage 5 — Decision + Reasoning Agent

**Agent:** `DecisionAgent` (Foundry Agent Service, model: GPT-5.4)

**What it does:** Produces the final adjudication decision — Approve / Reject / Escalate — with a traceable reasoning chain where **every conclusion is linked to a specific source evidence item**.

This is the explainability layer that makes the project defensible to enterprise buyers (and to interviewers asking "how do you handle hallucinations?"). The decision output is a structured JSON object where each reasoning step references the specific Doc Intelligence field, Content Understanding output, or Speech transcript excerpt that supports it.

```json
{
  "decision": "APPROVE",
  "confidence": 0.91,
  "approved_amount": 8400.00,
  "reasoning_chain": [
    {
      "step": "Coverage verified",
      "conclusion": "Policy active on loss date",
      "evidence_source": "doc_intelligence.field.policy_expiry",
      "evidence_value": "2026-11-30"
    },
    {
      "step": "Damage assessment",
      "conclusion": "Front-end damage consistent with stated collision",
      "evidence_source": "content_understanding.image_analysis.damage_pattern",
      "evidence_value": "front_impact_consistent"
    },
    {
      "step": "Fraud risk",
      "conclusion": "Low fraud risk (score: 0.18)",
      "evidence_source": "fraud_agent.risk_score",
      "evidence_value": 0.18
    }
  ]
}
```

---

### Stage 6 — Voice Live Adjuster Interface

**Service:** Azure Speech Voice Live API (GA, November 2025) + Azure Speech MCP Server

**Two interaction modes:**

**Adjuster copilot** — Internal tool for claims adjusters. Voice-driven. The adjuster speaks naturally ("pull up the Smith claim, what's the damage assessment say?") and the Voice Live agent — connected to the claim's Cosmos DB record via the Azure Speech MCP Server — responds in real time with information from the pipeline outputs. Semantic VAD handles noisy call center backgrounds.

**Customer status bot** — Outbound customer-facing interface. A Photo Avatar (powered by VASA-1, created from a single brand image) presents claim status updates to claimants. Deployed via Azure Communication Services telephony integration.

```python
# services/speech.py — Voice Live WebSocket connection
async def start_adjuster_session(claim_id: str, websocket: WebSocket):
    async with VoiceLiveClient(endpoint=VOICE_LIVE_ENDPOINT) as vl:
        await vl.configure_session(
            model="gpt-5.4",
            voice="en-US-AvaMultilingualNeural",
            mcp_servers=[AZURE_SPEECH_MCP_URL],
            tools=[claim_lookup_tool(claim_id)],
            vad_mode="azure_semantic"
        )
        async for audio_chunk in websocket:
            await vl.send_audio(audio_chunk)
            async for response in vl.receive():
                await websocket.send_bytes(response.audio)
```

---

### Stage 7 — Observability + Evaluation

**AgentOps tracing** is enabled on all Foundry Agent runs via the `azure-ai-projects` SDK. Every agent step (tool call, model invocation, output) is traced to Azure Application Insights.

**Azure AI Evaluation SDK** runs automated evals on:
- Extraction accuracy (field-level F1 against ground truth ACORD form annotations)
- Fraud detection precision/recall on a labeled synthetic dataset
- Decision quality (groundedness, relevance, coherence) using Azure OpenAI score model grader

**Durable Functions** implements the [async request-reply pattern](https://learn.microsoft.com/azure/architecture/patterns/async-request-reply):
- `POST /claims` → immediately returns `202 Accepted` with `task_id` and polling URL
- `GET /claims/{task_id}/status` → returns current pipeline step + partial results
- SignalR broadcasts `stepStarted` / `stepCompleted` / `stepFailed` events to the frontend in real time

---

## Local Development Setup

### Prerequisites

- Python 3.11+
- Node.js 20+
- Azure CLI (`az login` with an active subscription)
- Docker Desktop

### 1. Clone and install

```bash
git clone https://github.com/yourusername/claimpilot.git
cd claimpilot
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cd frontend && npm install
```

### 2. Provision Azure resources

```bash
cd infra
az deployment sub create \
  --location eastus \
  --template-file main.bicep \
  --parameters parameters/dev.bicepparam
```

This provisions: AI Foundry workspace, Document Intelligence, Speech resource, Content Understanding, Cosmos DB (serverless), Blob Storage, Service Bus, SignalR, Azure Functions (Flex Consumption), AI Search, Key Vault.

### 3. Configure environment

```bash
cp .env.example .env
# Fill in values from the Bicep deployment outputs:
# az deployment sub show --name ... --query properties.outputs
```

Key environment variables:

```bash
AZURE_FOUNDRY_PROJECT_ENDPOINT=https://...foundry.azure.com/...
AZURE_DOC_INTELLIGENCE_ENDPOINT=https://...cognitiveservices.azure.com/
AZURE_SPEECH_ENDPOINT=https://...cognitiveservices.azure.com/
AZURE_CONTENT_UNDERSTANDING_ENDPOINT=https://...
AZURE_TRANSLATOR_KEY=...
AZURE_SEARCH_ENDPOINT=https://....search.windows.net
AZURE_COSMOS_CONNECTION=...
AZURE_SIGNALR_CONNECTION=...
# Model deployment names
FOUNDRY_MODEL_DEPLOYMENT=gpt-5-4
CLASSIFIER_AGENT_ID=...
EXTRACTOR_AGENT_ID=...
FRAUD_AGENT_ID=...
DECISION_AGENT_ID=...
```

### 4. Train Document Intelligence custom model

```bash
# Uses synthetic ACORD forms in evaluation/datasets/acord_synthetic/
python backend/services/document_intelligence.py --train --dataset evaluation/datasets/acord_synthetic
```

### 5. Run locally

```bash
# Terminal 1: Backend (FastAPI dev server)
uvicorn backend.api.app:app --reload --port 8000

# Terminal 2: Frontend
cd frontend && npm run dev

# Terminal 3: Durable Functions (local emulation, production only)
cd backend/pipeline && func start
```

Open `http://localhost:3000` — upload a synthetic claim form + photo to see the full pipeline run.

---

## Evaluation Results (Synthetic Dataset, n=200 ACORD forms)

Results from `python -m evaluation.run_full_evaluation --mocked`:

| Metric | Mocked Score | Target |
|---|---|---|
| Doc Intelligence field extraction F1 | 1.00 | >= 0.90 |
| Content Understanding image classification accuracy | 0.89 | >= 0.85 |
| Fraud detection precision | 0.81 | >= 0.80 |
| Fraud detection recall | 0.87 | >= 0.80 |
| Fraud detection F1 | 0.84 | >= 0.80 |
| Decision groundedness | 0.90 | >= 0.80 |
| Mean pipeline latency (p50) | 3.2s* | < 60s |
| Mean pipeline latency (p95) | 8.7s* | < 120s |
| Human escalation rate | 25% | < 30% |

*Mocked benchmarks. Live latency requires `RUN_AZURE_INTEGRATION=1` with configured Azure resources.

See `evaluation/results/latest.json` for the full machine-readable report.

---

## Demo Data

A small pack of synthetic, non-PII claim bundles for manual frontend testing and live Azure validation:

```bash
python scripts/generate_demo_assets.py           # generates demo_assets/
pytest tests/unit/test_demo_assets.py -v          # validates the bundles
```

Three deterministic scenarios are generated:

| Bundle | Claimant | Expected Outcome | Description |
|---|---|---|---|
| `claim_001_approve` | Maria Thompson | APPROVED | Minor front damage, deer collision |
| `claim_002_escalate` | James Chen | ESCALATED | Rear-end collision, high repair estimate |
| `claim_003_fraud_review` | Diana Brooks | FRAUD_REVIEW | Inconsistent damage description |

Each bundle contains `claim_form.pdf`, 2 placeholder damage photos, and a `voice_statement.txt` transcript. See `demo_assets/README.md` for upload instructions.

---

## Key Design Decisions

**Why Durable Functions over a simple queue?** The pipeline has 7 sequential steps with individual failure modes. Durable Functions provides checkpointed execution — if step 4 fails, the orchestrator retries from step 4, not from step 1. On Flex Consumption, you pay only for execution time, not idle time.

**Why domain config in JSON?** Adding a new line of business (property, health) requires zero code changes. The extraction schema drives both Content Understanding analyzer creation and the Extractor Agent's Pydantic model (dynamically built at runtime from the JSON). This design pattern is borrowed from production IDP systems at Microsoft.

**Why not stream all outputs directly?** Fraud detection requires all three signal types (document, image, voice) before scoring. Parallelizing stages 1–3 and joining at stage 4 is the right pattern. Durable Functions `fan_out / fan_in` handles this natively.

**Why Voice Live over a standard chat UI?** Insurance adjusters work in call centers. Their hands are occupied. A voice-first interface that has access to the structured claim data via MCP is a genuine productivity improvement, not a demo gimmick. Semantic VAD specifically handles the noisy background problem that kills most voice AI deployments in call centers.

---

## What This Demonstrates (For Your Portfolio)

| Skill Area | Evidence in This Project |
|---|---|
| Azure AI Engineering | 8 distinct Azure AI services, each with a defensible architectural reason |
| Multi-agent systems | Foundry Agent Service: 4 specialized agents with A2A tool calls |
| Multimodal NLP | Text (forms) + image (photos) + audio (voice) processed via separate pipelines, unified at reasoning layer |
| Production patterns | Async 202-pattern, confidence-gated HITL, traceable reasoning chain, AgentOps observability |
| Evaluation discipline | Azure AI Evaluation SDK, ground-truth labeled dataset, quantified metrics |
| Infrastructure as code | Full Bicep IaC, GitHub Actions CI/CD |
| Full-stack | Python backend (Durable Functions + FastAPI) + Next.js 15 frontend with real-time SignalR |

---

## Roadmap (After v1)

- [ ] Property damage claims vertical (extends domain config, no pipeline changes)
- [ ] Azure Communication Services integration for outbound claimant calls via Photo Avatar
- [ ] Foundry Agent Service managed memory — cross-session adjuster context
- [ ] Agent-to-Agent (A2A) protocol integration for third-party repair shop API calls
- [ ] Multi-tenant deployment with Azure Managed Identity + role-based access per carrier

---

## Contributing

This is a reference implementation. Issues and PRs are welcome, particularly for:
- Additional ACORD form types in the synthetic dataset
- Evaluation harness improvements
- Bicep module hardening for production security posture

---

## License

MIT — see [LICENSE](LICENSE). Not affiliated with Microsoft. Azure service names and trademarks belong to Microsoft Corporation.

---

## References

- [Azure AI Foundry Agent Service GA (March 2026)](https://devblogs.microsoft.com/foundry/)
- [Choosing the right Azure AI tool for document processing](https://learn.microsoft.com/azure/ai-services/content-understanding/choosing-right-ai-tool)
- [Voice Live API reference](https://learn.microsoft.com/azure/ai-services/speech-service/voice-live-faq)
- [Azure Speech MCP Server](https://learn.microsoft.com/azure/developer/azure-mcp-server/services/azure-mcp-speech-foundry-tools)
- [Async request-reply pattern (Durable Functions)](https://learn.microsoft.com/azure/architecture/patterns/async-request-reply)
- [From Manual Document Processing to AI-Orchestrated Intelligence](https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/from-manual-document-processing-to-ai-orchestrated-intelligence/4498835)
