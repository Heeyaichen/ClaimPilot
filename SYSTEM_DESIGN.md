# ClaimPilot — System Design & Architecture Plan

## Table of Contents

1. [Problem Statement & Scope](#1-problem-statement--scope)
2. [System Requirements](#2-system-requirements)
3. [High-Level Architecture](#3-high-level-architecture)
4. [Layer-by-Layer Design](#4-layer-by-layer-design)
5. [Azure Service Mapping](#5-azure-service-mapping)
6. [Data Models](#6-data-models)
7. [Agent Design](#7-agent-design)
8. [Pipeline Flow — Sequence Diagrams](#8-pipeline-flow--sequence-diagrams)
9. [API Design](#9-api-design)
10. [Infrastructure as Code](#10-infrastructure-as-code)
11. [Observability & Evaluation Strategy](#11-observability--evaluation-strategy)
12. [Security & Compliance](#12-security--compliance)
13. [Failure Modes & Resilience](#13-failure-modes--resilience)
14. [Cost Estimate](#14-cost-estimate)
15. [Build Roadmap — Week by Week](#15-build-roadmap--week-by-week)

---

## 1. Problem Statement & Scope

### The Problem

Insurance carriers process thousands of claims monthly. Auto physical damage claims alone require:
- Manual extraction of data from ACORD forms (error-prone, slow)
- Review of multiple photos (subjective, inconsistent)
- Listening to claimant voice statements (time-consuming)
- Cross-referencing policy databases (manual lookup)
- Fraud screening (requires pattern recognition across historical data)
- Generating a written adjudication rationale (bottleneck)

Current industry median: 7–14 days per claim. Human adjuster handles 8–12 claims per day.

### The Solution

ClaimPilot ingests multimodal claim evidence and produces a complete, traceable adjudication decision in under 2 minutes — with a confidence-gated human-in-loop escalation path for edge cases.

### Scope Boundaries (v1)

| In scope | Out of scope |
|---|---|
| Auto physical damage claims | Health, property, liability claims (v2) |
| ACORD 1 + ACORD 2 form types | All other ACORD form variants |
| English + top-10 language translation | Real-time multilingual voice (v2) |
| Synthetic + publicly sourced ACORD data | Real carrier production data |
| Reference implementation (single tenant) | Multi-tenant SaaS architecture (roadmap) |

---

## 2. System Requirements

### Functional Requirements

- **FR-01:** Accept multimodal claim submission: PDF form, 1–10 images, optional audio file
- **FR-02:** Extract all structured fields from ACORD 1 and ACORD 2 forms with F1 ≥ 0.90
- **FR-03:** Analyze accident images for damage type, vehicle characteristics, scene conditions
- **FR-04:** Transcribe voice statements; translate from detected language to English
- **FR-05:** Classify claim type and route to appropriate agent configuration
- **FR-06:** Cross-validate all extracted fields against a policy search index
- **FR-07:** Produce a fraud risk score (0.0–1.0) with a structured multi-signal rationale
- **FR-08:** Generate a final adjudication decision (Approve / Reject / Escalate) with traceable reasoning
- **FR-09:** Expose a voice-driven adjuster interface against any claim record
- **FR-10:** Provide real-time pipeline step status to the frontend

### Non-Functional Requirements

| Requirement | Target |
|---|---|
| End-to-end pipeline latency (p50) | < 60 seconds |
| End-to-end pipeline latency (p95) | < 120 seconds |
| Pipeline availability | 99.5% (Flex Consumption + retry) |
| Claim state durability | 100% (Cosmos DB, 3-zone redundant) |
| Fraud detection precision | ≥ 0.85 on labeled synthetic dataset |
| Extraction F1 (ACORD 1 fields) | ≥ 0.90 on held-out test set |
| Human escalation rate | < 15% of claims (at default thresholds) |
| Voice Live adjuster session latency | < 600ms first-token response |

---

## 3. High-Level Architecture

```
                          ┌─────────────────────┐
                          │   External Input     │
                          │  (Web / API / Email) │
                          └──────────┬──────────┘
                                     │
                          ┌──────────▼──────────┐
                          │   Next.js Frontend   │
                          │  (Upload + Dashboard)│
                          └──────────┬──────────┘
                                     │ HTTPS
                          ┌──────────▼──────────┐
                          │  Azure Functions     │
                          │  (HTTP Trigger)      │
                          │  POST /claims        │
                          └──────┬──────┬───────┘
               202 + task_id     │      │ Files
                                 │      ▼
                    ┌────────────┘  Azure Blob Storage
                    │               (claims-intake)
                    ▼                    │
           ┌─────────────────┐          │ Blob Trigger
           │  Azure Service  │          │
           │      Bus        │◀─────────┘
           └────────┬────────┘
                    │ Dequeue
                    ▼
    ┌───────────────────────────────────────────────────┐
    │          Azure Durable Functions                  │
    │          (Orchestrator — Flex Consumption)        │
    │                                                   │
    │  Step 1: Ingestion Activities (fan-out)           │
    │    ├── Doc Intelligence activity                  │
    │    ├── Content Understanding activity             │
    │    └── Speech STT + Translator activity           │
    │                    │ (fan-in)                     │
    │  Step 2: Classification activity                  │
    │  Step 3: Extraction + Validation activity         │
    │  Step 4: Fraud Detection activity                 │
    │  Step 5: Decision + Reasoning activity            │
    │  Step 6: Notification activity (SignalR)          │
    └────────────────────┬──────────────────────────────┘
                         │ Agent calls
                         ▼
    ┌───────────────────────────────────────────────────┐
    │         Azure AI Foundry Agent Service            │
    │                                                   │
    │  ClassifierAgent ──▶ ExtractorAgent               │
    │                          ├── Foundry IQ search    │
    │                          └── Validation           │
    │  FraudAgent (parallel signals)                    │
    │  DecisionAgent (GPT-5.4 + traceable chain)        │
    └────────────────────┬──────────────────────────────┘
                         │ Reads / Writes
                         ▼
    ┌───────────────────────────────────────────────────┐
    │               Storage Layer                       │
    │                                                   │
    │  Cosmos DB (NoSQL, serverless)                    │
    │  ├── claims container (claim state + outputs)     │
    │  ├── policies container (policy index replica)    │
    │  └── audit_log container (immutable trail)        │
    │                                                   │
    │  Azure AI Search (Foundry IQ)                     │
    │  ├── policies-index                               │
    │  └── claims-history-index (fraud pattern lookup)  │
    └───────────────────────────────────────────────────┘
                         │
                         │ Real-time events
                         ▼
    ┌─────────────────────────────────────────────────┐
    │         Azure SignalR Service                   │
    │   Broadcasts stepStarted / stepCompleted events │
    │   to subscribed Next.js clients via @microsoft/ │
    │   signalr WebSocket connection                  │
    └─────────────────────────────────────────────────┘
                         │
                         ▼
    ┌─────────────────────────────────────────────────┐
    │         Voice Layer (separate path)             │
    │                                                  │
    │  Azure Speech Voice Live API (WebSocket)         │
    │  ├── Azure Speech MCP Server (claim data tools)  │
    │  ├── Semantic VAD (call center noise robust)     │
    │  └── Photo Avatar (customer-facing bot)         │
    └─────────────────────────────────────────────────┘
```

---

## 4. Layer-by-Layer Design

### 4.1 Ingestion Layer

**Pattern:** Fan-out / fan-in via Durable Functions

The three ingestion activities (document, image, voice) run in parallel:

```python
# pipeline/orchestrator.py
@df.orchestrator_function
def claim_orchestrator(context: df.DurableOrchestrationContext):
    input_data: ClaimInput = context.get_input()

    # Fan-out: all three run in parallel
    doc_task = context.call_activity("process_document", input_data.form_blob_url)
    image_task = context.call_activity("process_images", input_data.image_blob_urls)
    voice_task = context.call_activity("process_voice", input_data.audio_blob_url)

    # Fan-in: wait for all three
    doc_result, image_result, voice_result = yield context.task_all([
        doc_task, image_task, voice_task
    ])

    # Broadcast step 1 complete
    yield context.call_activity("broadcast_event", {
        "claim_id": input_data.claim_id,
        "step": 1,
        "status": "completed"
    })

    # Sequential pipeline continues...
    classification = yield context.call_activity("classify_claim", {
        "doc": doc_result, "images": image_result, "voice": voice_result
    })
    # ...
```

**Retry policy per activity:**
```python
retry_options = df.RetryOptions(
    first_retry_interval_in_milliseconds=5000,
    max_number_of_attempts=3,
    backoff_coefficient=2.0
)
```

### 4.2 Document Intelligence Integration

**Model strategy:** Composite custom model (two sub-models joined under one endpoint):
- Sub-model A: ACORD 1 (Personal Auto Application) — template-based
- Sub-model B: ACORD 2 (Private Passenger Auto) — neural (handles scan quality variation)

**Training data:** 200 labeled synthetic ACORD forms generated via Python `fpdf2` library with randomized field values matching ACORD field specifications. Stored in `evaluation/datasets/acord_synthetic/`.

**Output format:** Structured Markdown (Doc Intelligence v4.0 `outputContentFormat=markdown`) — preserves table structure for downstream LLM consumption without token bloat.

```python
# services/document_intelligence.py
async def extract_claim_form(blob_url: str) -> DocumentExtractionResult:
    async with DocumentIntelligenceClient(endpoint=DI_ENDPOINT, credential=credential) as client:
        poller = await client.begin_analyze_document_from_url(
            model_id=ACORD_COMPOSITE_MODEL_ID,
            url_source=blob_url,
            output_content_format="markdown"
        )
        result = await poller.result()

    return DocumentExtractionResult(
        markdown_content=result.content,
        fields={
            field_name: DocumentField(
                value=field.value,
                confidence=field.confidence,
                bounding_regions=field.bounding_regions
            )
            for field_name, field in result.documents[0].fields.items()
        }
    )
```

### 4.3 Content Understanding Integration

**Two uses:**
1. **Image analysis** — standalone call per image, schema-driven output
2. **Cross-file reasoning** — multi-input call combining form Markdown + all image outputs → unified evidence summary

**Schema file** (`domains/auto_damage/extraction_schema.json`) defines what Content Understanding should extract from images:

```json
{
  "damage_indicators": {
    "type": "array",
    "items": {
      "type": "object",
      "properties": {
        "panel": {"type": "string", "enum": ["front", "rear", "driver_side", "passenger_side", "roof", "undercarriage"]},
        "severity": {"type": "string", "enum": ["minor", "moderate", "severe", "total_loss_candidate"]},
        "description": {"type": "string"}
      }
    }
  },
  "vehicle_identification": {
    "type": "object",
    "properties": {
      "make": {"type": "string"},
      "model": {"type": "string"},
      "color": {"type": "string"},
      "license_plate_visible": {"type": "boolean"},
      "license_plate_value": {"type": "string", "nullable": true}
    }
  },
  "scene_conditions": {
    "type": "object",
    "properties": {
      "time_of_day_estimated": {"type": "string"},
      "weather_conditions": {"type": "string"},
      "location_type": {"type": "string", "enum": ["road", "parking_lot", "private_property", "highway", "unknown"]}
    }
  },
  "forensic_flags": {
    "type": "array",
    "description": "Anomalies inconsistent with stated accident type",
    "items": {"type": "string"}
  }
}
```

### 4.4 Speech Pipeline

**Two distinct paths:**

**Path A — Async transcription (claim ingestion):**
- Input: `.wav` or `.mp3` audio blob
- Process: Azure Speech STT batch transcription with `--diarization` (identifies claimant vs. interviewer)
- Post-process: Language detection → Azure Translator if not English
- Output: Structured transcript with speaker labels + language metadata

**Path B — Real-time Voice Live (adjuster interface):**
- Input: Streaming audio from browser microphone (WebSocket)
- Process: Voice Live API with Semantic VAD + MCP tools for claim data access
- Output: Streaming audio response + text transcript for audit log

```python
# services/speech.py — Batch transcription (Path A)
async def transcribe_voice_statement(audio_blob_url: str) -> VoiceTranscript:
    speech_config = speechsdk.SpeechConfig(endpoint=SPEECH_ENDPOINT)
    speech_config.speech_recognition_language = "en-US"  # Will auto-detect
    speech_config.set_property(
        speechsdk.PropertyId.SpeechServiceConnection_LanguageIdMode,
        "Continuous"
    )

    audio_config = speechsdk.audio.AudioConfig(url=audio_blob_url)
    recognizer = speechsdk.SpeechRecognizer(
        speech_config=speech_config,
        auto_detect_source_language_config=AutoDetectSourceLanguageConfig(
            languages=["en-US", "es-ES", "fr-FR", "de-DE", "zh-CN",
                       "ja-JP", "ko-KR", "pt-BR", "ar-SA", "hi-IN"]
        ),
        audio_config=audio_config
    )

    result = await recognizer.recognize_once_async()
    detected_language = result.properties.get(
        speechsdk.PropertyId.SpeechServiceConnection_AutoDetectSourceLanguageResult
    )

    transcript_text = result.text
    if detected_language != "en-US":
        transcript_text = await translate_to_english(transcript_text, detected_language)

    return VoiceTranscript(
        original_text=result.text,
        translated_text=transcript_text,
        detected_language=detected_language,
        duration_seconds=result.duration / 10_000_000
    )
```

---

## 5. Azure Service Mapping

### Service Configuration Reference

```
┌─────────────────────────────────────────────────────────────────────┐
│ Service                    │ SKU/Tier         │ Region              │
├────────────────────────────┼──────────────────┼─────────────────────┤
│ Azure AI Foundry           │ Standard S0      │ East US 2           │
│ Azure Doc Intelligence     │ Standard S0      │ East US 2           │
│ Azure AI Content Underst.  │ 2025-05-01-prev  │ East US 2           │
│ Azure Speech               │ Standard S0      │ East US 2           │
│ Azure Translator           │ Standard S1      │ East US 2           │
│ Azure AI Search            │ Standard S1      │ East US 2           │
│ Azure Cosmos DB            │ Serverless       │ East US 2 + West US │
│ Azure Durable Functions    │ Flex Consumption │ East US 2           │
│ Azure Blob Storage         │ Standard LRS     │ East US 2           │
│ Azure Service Bus          │ Standard         │ East US 2           │
│ Azure SignalR Service      │ Standard         │ East US 2           │
│ Azure Key Vault            │ Standard         │ East US 2           │
│ Azure Application Insights │ Pay-as-you-go    │ East US 2           │
│ Azure Container Registry   │ Basic            │ East US 2           │
└────────────────────────────┴──────────────────┴─────────────────────┘
```

### SDK Version Pinning

```toml
# pyproject.toml
[tool.poetry.dependencies]
python = "^3.11"
azure-ai-projects = "^2.0.0"          # Foundry Agent Service GA
azure-ai-documentintelligence = "^1.0.0"
azure-cognitiveservices-speech = "^1.41.0"
azure-ai-translation-text = "^1.0.1"
azure-search-documents = "^11.6.0"
azure-cosmos = "^4.9.0"
azure-storage-blob = "^12.23.0"
azure-servicebus = "^7.14.0"
azure-identity = "^1.19.0"
azure-monitor-opentelemetry = "^1.6.0"
azure-functions-durable = "^1.2.9"
pydantic = "^2.9.0"
fastapi = "^0.115.0"
httpx = "^0.27.0"
```

---

## 6. Data Models

### Claim State Machine

```
SUBMITTED
    │
    ▼
INGESTING ──────────────────────────────────────┐
    │                                           │
    ▼                                           │
CLASSIFYING                              FAILED │
    │                                           │
    ▼                                           │
EXTRACTING                                      │
    │                                           │
    ▼                                           │
FRAUD_SCREENING                                 │
    │                                           │
    ▼                                           │
DECIDING                                        │
    │                                           │
    ├── confidence ≥ threshold ──▶ APPROVED     │
    ├── fraud_score ≥ 0.7 ──────▶ ESCALATED    │
    ├── confidence < threshold ──▶ ESCALATED    │
    └── policy mismatch ────────▶ REJECTED      │
                                                │
FAILED ◀────────────────────────────────────────┘
```

### Core Pydantic Models

```python
# models/claim.py

from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional


class ClaimStatus(str, Enum):
    SUBMITTED = "SUBMITTED"
    INGESTING = "INGESTING"
    CLASSIFYING = "CLASSIFYING"
    EXTRACTING = "EXTRACTING"
    FRAUD_SCREENING = "FRAUD_SCREENING"
    DECIDING = "DECIDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ESCALATED = "ESCALATED"
    FAILED = "FAILED"


class ClaimType(str, Enum):
    AUTO_PHYSICAL_DAMAGE = "AUTO_PHYSICAL_DAMAGE"
    TOTAL_LOSS = "TOTAL_LOSS"
    THEFT = "THEFT"
    LIABILITY = "LIABILITY"


class DecisionOutcome(str, Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    ESCALATE = "ESCALATE"


class ReasoningStep(BaseModel):
    step: str
    conclusion: str
    evidence_source: str   # e.g., "doc_intelligence.field.policy_expiry"
    evidence_value: str | float | bool


class AdjudicationDecision(BaseModel):
    decision: DecisionOutcome
    confidence: float = Field(ge=0.0, le=1.0)
    approved_amount: Optional[float] = None
    rejection_reason: Optional[str] = None
    escalation_reason: Optional[str] = None
    reasoning_chain: list[ReasoningStep]
    generated_at: datetime


class FraudRiskScore(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    signals: dict[str, float]  # signal_name → individual score
    flags: list[str]           # human-readable anomaly descriptions
    recommendation: str        # "proceed" | "adjuster_review" | "escalate_siu"


class ClaimRecord(BaseModel):
    claim_id: str
    status: ClaimStatus
    claim_type: Optional[ClaimType] = None
    submitted_at: datetime
    updated_at: datetime

    # Pipeline outputs (populated progressively)
    doc_extraction: Optional[dict] = None
    image_analysis: Optional[dict] = None
    voice_transcript: Optional[dict] = None
    extracted_fields: Optional[dict] = None
    validation_flags: list[str] = []
    fraud_risk: Optional[FraudRiskScore] = None
    decision: Optional[AdjudicationDecision] = None

    # Metadata
    pipeline_duration_seconds: Optional[float] = None
    human_escalated: bool = False
    escalation_assigned_to: Optional[str] = None
```

---

## 7. Agent Design

### Agent Architecture Principles

Each Foundry agent has a single responsibility. They do not share state directly — all state flows through Cosmos DB and is passed explicitly as context in each agent invocation.

### ClassifierAgent

```python
# agents/classifier_agent.py

CLASSIFIER_SYSTEM_PROMPT = """
You are a claims classification specialist. Given multimodal claim evidence,
you classify the claim type and assess routing confidence.

Output ONLY valid JSON matching this schema:
{
    "claim_type": "AUTO_PHYSICAL_DAMAGE | TOTAL_LOSS | THEFT | LIABILITY",
    "confidence": 0.0-1.0,
    "routing_rationale": "brief explanation",
    "requires_human_review": true/false,
    "review_reason": "null or explanation if requires_human_review is true"
}

Classification rules:
- AUTO_PHYSICAL_DAMAGE: Repairable vehicle damage from collision or incident
- TOTAL_LOSS: Damage estimated > 75% of vehicle ACV, or vehicle not recoverable
- THEFT: Vehicle stolen (partial or complete), without collision
- LIABILITY: Third-party bodily injury or property damage claim

If evidence is insufficient for high-confidence classification (< 0.75),
set requires_human_review to true.
"""

CLASSIFIER_TOOLS = [
    # Policy lookup via Foundry IQ
    {
        "type": "azure_ai_search",
        "index_name": "policies-index",
        "description": "Look up policy details by policy number to validate coverage type"
    }
]
```

### FraudDetectionAgent

```python
FRAUD_SYSTEM_PROMPT = """
You are a fraud detection specialist for auto insurance claims.
Analyze the provided claim evidence across multiple signals and produce
a fraud risk assessment.

Evidence signals available to you:
1. Document fields (from ACORD form extraction)
2. Image forensic analysis (from Content Understanding)
3. Voice statement transcript with sentiment markers
4. Policy history (via search tool)
5. Claims history (via search tool)

Fraud indicators to check:
- Damage pattern inconsistency: Does image damage match the stated accident type?
- Timeline inconsistency: Claimed date vs. vehicle condition in photos
- Coverage timing: Was the policy taken out recently before the loss?
- Prior claims: Same claimant or vehicle with prior claims in < 24 months
- Statement inconsistency: Voice transcript contradicts written form
- Total loss pattern: Older vehicle, high mileage, full comprehensive claim

Scoring guidance:
- 0.0–0.3: Low risk — proceed to automated decision
- 0.3–0.7: Medium risk — flag for adjuster review (do not block)
- 0.7–1.0: High risk — escalate to Special Investigations Unit

Output ONLY valid JSON matching the FraudRiskScore schema.
"""

FRAUD_TOOLS = [
    {"type": "azure_ai_search", "index_name": "policies-index"},
    {"type": "azure_ai_search", "index_name": "claims-history-index"},
    {"type": "mcp", "server_url": AZURE_SPEECH_MCP_URL}  # Can request additional transcription
]
```

### DecisionAgent

```python
DECISION_SYSTEM_PROMPT = """
You are the final adjudication decision agent. You receive all processed
evidence and must produce a binding adjudication decision.

CRITICAL REQUIREMENT: Every conclusion in your reasoning_chain MUST be
linked to a specific evidence_source. Do not make inferences not supported
by the provided evidence. If evidence is insufficient, set decision to ESCALATE.

Decision rules:
- APPROVE: fraud_score < 0.4 AND confidence ≥ 0.80 AND all required fields validated
- REJECT: Clear policy exclusion OR fraud_score ≥ 0.7 AND evidence is definitive
- ESCALATE: Any other case, OR if reasoning chain cannot be fully grounded

approved_amount: If APPROVE, calculate based on:
  - Document-extracted repair estimate
  - Coverage limit (from policy lookup)
  - Applicable deductible (from policy)
  - Depreciation if applicable

Output ONLY valid JSON matching the AdjudicationDecision schema.
Every reasoning_chain item must have a real evidence_source path.
"""
```

---

## 8. Pipeline Flow — Sequence Diagrams

### Claim Submission (Happy Path)

```
Client          API Function    Blob Storage    Service Bus    Orchestrator
  │                  │               │               │               │
  │── POST /claims ─▶│               │               │               │
  │                  │── Upload ────▶│               │               │
  │                  │               │── Blob ──────▶│               │
  │                  │               │   trigger     │               │
  │◀── 202 ─────────│               │               │── Start ─────▶│
  │   {task_id}      │               │               │   orchestrator│
  │                  │               │               │               │
  │── GET /status ──▶│               │               │               │
  │◀── {step:1} ────│               │               │               │
  │   INGESTING      │               │               │               │
  │                  │               │               │               │
  │   [SignalR]       │               │               │               │
  │◀══ stepCompleted ══════════════════════════════════════════════ │
  │   step: 1         │               │               │               │
  │◀══ stepCompleted ══════════════════════════════════════════════ │
  │   step: 2 (CLASSIFYING)          │               │               │
  │◀══ stepCompleted ══════════════════════════════════════════════ │
  │   step: 3 (EXTRACTING)           │               │               │
  │◀══ stepCompleted ══════════════════════════════════════════════ │
  │   step: 4 (FRAUD_SCREENING)      │               │               │
  │◀══ stepCompleted ══════════════════════════════════════════════ │
  │   step: 5 (DECIDING)             │               │               │
  │◀══ APPROVED ══════════════════════════════════════════════════ │
  │   {decision, reasoning_chain}    │               │               │
```

### Voice Adjuster Session

```
Adjuster Browser    Next.js API     Voice Live API    Foundry IQ (MCP)
      │                  │               │                    │
      │── GET /adjuster/claim/{id} ─────▶│                    │
      │◀── WebSocket URL ───────────────│                    │
      │                  │               │                    │
      │══ WS Connect ══════════════════▶│                    │
      │                  │               │── Session config ─▶│ (MCP tools registered)
      │                  │               │                    │
      │── [audio stream] ═══════════════▶│                    │
      │   "What's the damage assessment  │── claim_lookup ───▶│
      │    say on this one?"             │   tool call        │
      │                  │               │◀── claim data ─────│
      │                  │               │── Generate response│
      │◀═ [audio stream] ═══════════════│                    │
      │   "The Content Understanding     │                    │
      │    analysis shows front-end      │                    │
      │    impact damage, severity       │                    │
      │    moderate, consistent with     │                    │
      │    the stated rear-end collision │                    │
      │    — actually, flag that as      │                    │
      │    inconsistent..."              │                    │
```

---

## 9. API Design

### REST Endpoints

```
POST   /api/v1/claims
       Body: multipart/form-data
         - form_document: file (PDF, max 50MB)
         - images[]: file[] (JPEG/PNG, max 10 files, 20MB each)
         - voice_statement: file (WAV/MP3, max 300s, optional)
         - claimant_name: string
         - policy_number: string
       Response: 202 Accepted
         { "claim_id": "uuid", "status_url": "/api/v1/claims/{id}/status" }

GET    /api/v1/claims/{claim_id}/status
       Response: 200 OK
         {
           "claim_id": "uuid",
           "status": "EXTRACTING",
           "current_step": 3,
           "total_steps": 7,
           "step_name": "Extraction + Validation",
           "started_at": "2026-04-19T...",
           "partial_results": {
             "claim_type": "AUTO_PHYSICAL_DAMAGE",
             "classification_confidence": 0.93
           }
         }

GET    /api/v1/claims/{claim_id}
       Response: 200 OK — full ClaimRecord JSON

GET    /api/v1/claims/{claim_id}/decision
       Response: 200 OK — AdjudicationDecision JSON (or 404 if not yet decided)

POST   /api/v1/claims/{claim_id}/escalate
       Body: { "reason": "string", "assigned_to": "adjuster_id" }
       Response: 200 OK — Updates claim to ESCALATED

GET    /api/v1/adjuster/session-url
       Query: ?claim_id=uuid
       Response: 200 OK — { "ws_url": "wss://...", "token": "..." }

GET    /api/v1/claims
       Query: ?status=ESCALATED&page=1&page_size=20
       Response: 200 OK — paginated ClaimRecord list
```

### SignalR Hub Events

```typescript
// frontend/lib/signalr.ts

type PipelineEvent =
  | { type: "stepStarted";   claimId: string; step: number; stepName: string }
  | { type: "stepCompleted"; claimId: string; step: number; stepName: string; durationMs: number }
  | { type: "stepFailed";    claimId: string; step: number; error: string; willRetry: boolean }
  | { type: "claimDecided";  claimId: string; outcome: "APPROVED" | "REJECTED" | "ESCALATED" }
  | { type: "claimFailed";   claimId: string; error: string }
```

---

## 10. Infrastructure as Code

### Bicep — Main Module Structure

```bicep
// infra/main.bicep

targetScope = 'subscription'

param location string = 'eastus2'
param environment string = 'dev'
param projectName string = 'claimpilot'

resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: '${projectName}-${environment}-rg'
  location: location
}

module foundry './modules/foundry.bicep' = {
  scope: rg
  name: 'foundry'
  params: {
    location: location
    projectName: projectName
    environment: environment
  }
}

module speech './modules/speech.bicep' = {
  scope: rg
  name: 'speech'
  params: { location: location, projectName: projectName, environment: environment }
}

module docIntelligence './modules/doc-intelligence.bicep' = {
  scope: rg
  name: 'doc-intelligence'
  params: { location: location, projectName: projectName, environment: environment }
}

module cosmos './modules/cosmos.bicep' = {
  scope: rg
  name: 'cosmos'
  params: {
    location: location
    projectName: projectName
    environment: environment
    enableZoneRedundancy: environment == 'prod'
  }
}

module functions './modules/functions.bicep' = {
  scope: rg
  name: 'functions'
  params: {
    location: location
    projectName: projectName
    environment: environment
    cosmosConnectionString: cosmos.outputs.connectionString
    foundryEndpoint: foundry.outputs.projectEndpoint
    speechEndpoint: speech.outputs.endpoint
  }
}

// ... search, signalr, keyvault modules
```

### GitHub Actions CI/CD

```yaml
# .github/workflows/deploy.yml

name: Deploy ClaimPilot

on:
  push:
    branches: [main]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Lint Python
        run: |
          pip install ruff mypy
          ruff check backend/
          mypy backend/ --ignore-missing-imports
      - name: Run unit tests
        run: pytest tests/unit/ -v --tb=short
        env:
          AZURE_FOUNDRY_PROJECT_ENDPOINT: ${{ secrets.AZURE_FOUNDRY_PROJECT_ENDPOINT }}
      - name: Validate Bicep
        run: az bicep build --file infra/main.bicep

  deploy-infra:
    needs: validate
    runs-on: ubuntu-latest
    steps:
      - uses: azure/login@v2
        with: { creds: '${{ secrets.AZURE_CREDENTIALS }}' }
      - name: Deploy Bicep
        run: |
          az deployment sub create \
            --location eastus2 \
            --template-file infra/main.bicep \
            --parameters environment=prod

  deploy-backend:
    needs: deploy-infra
    runs-on: ubuntu-latest
    steps:
      - name: Deploy Durable Functions
        run: |
          cd backend
          func azure functionapp publish ${{ secrets.FUNCTION_APP_NAME }}

  deploy-frontend:
    needs: deploy-infra
    runs-on: ubuntu-latest
    steps:
      - name: Deploy Next.js to Azure Static Web Apps
        uses: Azure/static-web-apps-deploy@v1
        with:
          azure_static_web_apps_api_token: ${{ secrets.SWA_TOKEN }}
          repo_token: ${{ secrets.GITHUB_TOKEN }}
          action: upload
          app_location: frontend
          output_location: .next
```

---

## 11. Observability & Evaluation Strategy

### AgentOps Tracing

Every Foundry Agent run automatically traces to Application Insights via the `azure-ai-projects` SDK. Key metrics to instrument:

```python
# agents/base.py
from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry import trace

configure_azure_monitor(connection_string=APPINSIGHTS_CONNECTION_STRING)
tracer = trace.get_tracer(__name__)

async def run_agent_with_tracing(agent_name: str, input_data: dict) -> dict:
    with tracer.start_as_current_span(f"agent.{agent_name}") as span:
        span.set_attribute("claim.id", input_data.get("claim_id"))
        span.set_attribute("agent.name", agent_name)
        # ... agent execution
        span.set_attribute("agent.confidence", result.get("confidence"))
        return result
```

### Evaluation Harness

```python
# evaluation/evaluate_extraction.py

from azure.ai.evaluation import evaluate, F1ScoreEvaluator

results = evaluate(
    data="evaluation/datasets/acord_synthetic/ground_truth.jsonl",
    evaluators={"f1_score": F1ScoreEvaluator()},
    target=lambda sample: extract_claim_form_sync(sample["form_blob_url"]),
    evaluator_config={
        "f1_score": {
            "column_mapping": {
                "prediction": "${target.extracted_fields}",
                "ground_truth": "${data.ground_truth_fields}"
            }
        }
    }
)
print(f"Extraction F1: {results['f1_score']['f1_score']:.3f}")
```

### Key Dashboards to Build in App Insights

| Dashboard | Metrics | Alert threshold |
|---|---|---|
| Pipeline health | Step success rate, retry rate | Step failure > 5% |
| Latency | p50, p95, p99 pipeline duration | p95 > 120s |
| Fraud detection | Score distribution, escalation rate | Escalation rate > 20% |
| Extraction accuracy | Field confidence histogram | Mean confidence < 0.80 |
| Voice Live | Session latency, VAD accuracy | p95 latency > 800ms |
| Cost | Per-claim cost breakdown by service | Cost per claim > $0.50 |

---

## 12. Security & Compliance

### Authentication & Authorization

- All Azure service connections use **Managed Identity** (no connection strings in code)
- Foundry Agent tools use **Entra Agent Identity** for tool call authentication
- Frontend users authenticate via **Azure AD B2C** (adjuster role vs. supervisor role)
- API endpoints protected by **Bearer token** validation middleware

```python
# api/middleware.py
from azure.identity import DefaultAzureCredential

# Managed Identity — no secrets in code
credential = DefaultAzureCredential()

# All service clients instantiated with credential
doc_intelligence_client = DocumentIntelligenceClient(
    endpoint=DI_ENDPOINT,
    credential=credential  # Uses Managed Identity in Azure, DefaultAzureCredential locally
)
```

### Data Handling

- Claim documents stored in Blob Storage with **customer-managed keys** (CMK) enabled in prod
- Cosmos DB with **CMK encryption at rest**
- Blob Storage lifecycle policy: raw claim files deleted after 90 days (processed data retained in Cosmos)
- Azure Key Vault for all secrets — **no secrets in environment variables in production**
- All API traffic over **TLS 1.2+**

### Audit Trail

Every claim state transition and every agent decision is written to the `audit_log` Cosmos container with:
- Timestamp
- Actor (agent name + run ID, or human adjuster ID)
- Action
- Previous state
- New state
- Traceable evidence references

This container is configured as **append-only** via Cosmos DB role-based access.

---

## 13. Failure Modes & Resilience

| Failure Mode | Detection | Recovery |
|---|---|---|
| Doc Intelligence API timeout | Activity timeout (30s) | Retry up to 3x with exponential backoff |
| Content Understanding returns low confidence | Confidence threshold check | Route to human review, do not fail pipeline |
| Speech STT fails (corrupt audio) | Exception catch | Continue pipeline with null voice_transcript, flag for adjuster |
| Foundry Agent Service returns malformed JSON | Pydantic validation error | Retry once; if still invalid, escalate claim |
| Cosmos DB write failure | Exception catch in notification activity | Dead-letter to Service Bus; manual replay |
| Voice Live session drops | WebSocket close event | Client-side reconnect with session resume (claim_id preserved) |
| Fraud detection timeout (> 60s) | Activity timeout | Escalate claim automatically; log for investigation |

### Human-in-Loop Escalation Triggers

Any of the following automatically sets `status = ESCALATED`:
- Classifier confidence < 0.75
- Extractor field confidence < 0.70 on any required field
- Fraud risk score ≥ 0.70
- Decision agent confidence < 0.80
- Any unhandled exception after 3 retries
- Pipeline duration > 180 seconds

---

## 14. Cost Estimate

### Per-Claim Cost (approximate, dev/test volume)

| Service | Unit | Cost |
|---|---|---|
| Doc Intelligence (custom model) | Per page (2 pages avg) | ~$0.014 |
| Content Understanding (3 images) | Per image | ~$0.015 |
| Azure Speech STT (90s avg) | Per minute | ~$0.006 |
| Azure Translator (500 tokens avg) | Per 1M chars | ~$0.001 |
| Foundry Agent Service (4 agents, ~2k tokens each) | Per 1M tokens | ~$0.040 |
| Cosmos DB (serverless, 5 writes) | Per RU | ~$0.002 |
| Durable Functions (Flex Consumption) | Per execution | ~$0.003 |
| Azure AI Search | Per query (5 queries) | ~$0.005 |
| **Total per claim** | | **~$0.086** |

At 1,000 claims/month development volume: ~$86/month in service costs.

---

## 15. Build Roadmap — Week by Week

### Week 1 — Foundation & Ingestion

**Goal:** End-to-end file ingestion working. No agents yet.

- [ ] Provision all Azure resources via Bicep (`az deployment sub create`)
- [ ] Configure Managed Identity role assignments for all services
- [ ] Implement `DocumentIntelligenceService` — call API with a sample ACORD form, verify JSON output
- [ ] Generate 50 synthetic ACORD forms using `fpdf2` — label 20 for training
- [ ] Train Doc Intelligence custom model on ACORD 1 (template-based model, min 5 labeled samples)
- [ ] Implement `ContentUnderstandingService` — schema-driven image analysis on 3 sample accident photos
- [ ] Implement `SpeechService` — batch STT on a sample audio file, verify transcript output
- [ ] Implement `TranslatorService` — test with Spanish audio transcript
- [ ] Write unit tests for all four services

**Deliverable:** `pytest tests/unit/ -v` passes. Can call each service independently and get structured output.

---

### Week 2 — Durable Functions Pipeline

**Goal:** Sequential pipeline working without agents (stub agent calls).

- [ ] Implement Durable Functions orchestrator with stub activities
- [ ] Implement fan-out ingestion (doc + image + voice in parallel)
- [ ] Implement Cosmos DB claim state store — write on every step transition
- [ ] Implement Service Bus queue trigger → orchestrator starter
- [ ] Implement `202 Accepted` HTTP trigger + polling endpoint
- [ ] Implement SignalR event broadcast per step
- [ ] Connect Next.js SignalR client — verify real-time step updates in browser
- [ ] Implement Blob Storage upload endpoint (multipart form data)
- [ ] End-to-end test: Upload PDF + image → see 7 steps appear in browser in real time

**Deliverable:** Can submit a claim form, watch 7 steps complete in the dashboard, see structured output in Cosmos DB.

---

### Week 3 — Foundry Agents

**Goal:** All 4 Foundry agents implemented and wired into pipeline.

- [ ] Create Foundry workspace and agent definitions in the portal
- [ ] Implement `ClassifierAgent` — system prompt, Foundry IQ tool, JSON output validation
- [ ] Implement `ExtractorAgent` — field extraction schema, cross-validation against policies-index
- [ ] Create `policies-index` in Azure AI Search — load 50 synthetic policy records
- [ ] Implement `FraudDetectionAgent` — multi-signal prompt, claims-history-index tool
- [ ] Create `claims-history-index` — load 100 synthetic prior claims
- [ ] Implement `DecisionAgent` — traceable reasoning chain, AdjudicationDecision output
- [ ] Wire all 4 agents into Durable Functions activities (replace stubs)
- [ ] AgentOps tracing: verify all agent steps appear in Application Insights
- [ ] Run evaluation: `python evaluation/evaluate_extraction.py` — target F1 ≥ 0.90

**Deliverable:** Full pipeline runs with real agents. Decision JSON with traceable reasoning chain in Cosmos DB.

---

### Week 4 — Voice Live Interface

**Goal:** Adjuster voice copilot working in browser.

- [ ] Implement Voice Live WebSocket connection in `SpeechService`
- [ ] Configure Azure Speech MCP Server with claim lookup tool
- [ ] Implement voice adjuster Next.js page — browser microphone → WebSocket → audio playback
- [ ] Test Semantic VAD with noisy background audio (fan noise, etc.)
- [ ] Implement Photo Avatar configuration (standard avatar for customer bot)
- [ ] Implement adjuster session URL endpoint with auth token
- [ ] End-to-end test: Start adjuster session on a processed claim, ask questions verbally, verify MCP tool calls to Cosmos DB

**Deliverable:** Working voice adjuster demo. Ask "what's the fraud score on this claim?" and get a spoken answer with data from Cosmos DB.

---

### Week 5 — Frontend, Evaluation, README

**Goal:** Polished frontend, evaluation metrics documented, GitHub-ready.

- [ ] Build claim submission form (upload zone, progress tracker, real-time pipeline visualization)
- [ ] Build claim detail page — traceable decision viewer (reasoning chain UI)
- [ ] Build adjuster queue — list of ESCALATED claims with priority sorting
- [ ] Run full evaluation suite on 200 synthetic ACORD forms — record all metrics
- [ ] Write evaluation results table in README
- [ ] Write architecture diagram (ASCII in README + PNG version)
- [ ] Record 3-minute demo video (full claim submission → decision → adjuster voice session)
- [ ] Write GitHub README (this document)
- [ ] Tag v1.0.0 release

**Deliverable:** Repository is portfolio-ready. Full demo video uploaded to README.

---

### Post-v1 (if time allows)

- **Week 6:** Property damage vertical (new domain config, no pipeline changes)
- **Week 7:** Azure Communication Services telephony → Photo Avatar outbound customer calls
- **Week 8:** Foundry Agent managed memory — cross-session adjuster context retention
- **Week 9:** Multi-tenant isolation (separate Cosmos containers + Entra app registrations per carrier)
- **Week 10:** A2A protocol — Foundry agents calling external repair shop estimate APIs

---

*Last updated: April 2026 | Built with Azure AI Foundry Agent Service GA (March 2026)*