# ProofFlow AI — System Architecture & Component Design

> **Architecture Pattern**: Modular Monolith with Asynchronous Background Processing and Event Logging.  
> **Target Audience**: AI Systems Engineers, Software Architects, and Technical Reviewers.

---

## 🏛️ High-Level System Architecture

```mermaid
flowchart TB
    subgraph Client["Client Layer"]
        UI["React + Vite Web App<br/>(Review, Chat, Charts)"]
        ExternalAgent["External AI Agent<br/>(Claude Desktop / Cursor)"]
        ExternalApp["External Business Systems<br/>(ERP / Accounting / Webhooks)"]
    end

    subgraph Gateway["API Gateway Layer (FastAPI)"]
        REST["REST API Endpoints<br/>(/documents, /cases, /chat)"]
        MCPServer["Model Context Protocol (MCP)<br/>Server Adapter"]
        Auth["Auth & Scope Enforcement"]
    end

    subgraph Orchestration["Agent & Workflow Runtime"]
        Worker["Async Job Worker<br/>(PostgreSQL SKIP LOCKED)"]
        LangGraphAgent["LangGraph Agent Runtime<br/>(Checkpointer & Bounded Tools)"]
        VerificationEngine["Deterministic 3-Way<br/>Verification Engine"]
    end

    subgraph Intelligence["Document Intelligence Layer"]
        PDFParser["PyMuPDF Native Text Parser"]
        OCRParser["PaddleOCR / Vision Fallback"]
        VLMExtractor["Vision-Language Model<br/>(PaddleOCR-VL / vLLM Adapter)"]
        Normalizer["Field Normalizer & Schema Validator"]
    end

    subgraph Data["Persistence & Storage Layer"]
        Postgres[(PostgreSQL Database<br/>Documents, Cases, Findings, Events)]
        DocStorage[("File Storage<br/>(Local Filesystem / S3 Object Store)")]
    end

    subgraph Improvement["Closed-Loop Self-Improvement"]
        TraceLogger["Execution Trace Logger"]
        FailureAnalyzer["Failure Clustering & Analysis"]
        CandidateOptimizer["Candidate Prompt & Rule Optimizer"]
        EvalGate["Frozen Benchmark & Release Gate"]
    end

    %% Connections
    UI --> REST
    ExternalAgent --> MCPServer
    ExternalApp --> REST

    REST --> Auth
    MCPServer --> Auth
    Auth --> Postgres
    Auth --> Worker
    Auth --> LangGraphAgent

    Worker --> PDFParser
    Worker --> OCRParser
    Worker --> VLMExtractor
    VLMExtractor --> Normalizer
    Normalizer --> VerificationEngine
    VerificationEngine --> Postgres

    LangGraphAgent --> Postgres
    LangGraphAgent --> UI

    Postgres --> TraceLogger
    TraceLogger --> FailureAnalyzer
    FailureAnalyzer --> CandidateOptimizer
    CandidateOptimizer --> EvalGate
    EvalGate -.->|Human Approved Changes| VLMExtractor
```

---

## 🧩 Architectural Subsystems

### 1. Document Intelligence Pipeline
The document ingestion and extraction pipeline uses a **hierarchical routing strategy**:
1. **Digital Parsing (Tier 1)**: Ingests documents via PyMuPDF. High quality vector PDFs extract structured text, fonts, and bounding boxes instantaneously at zero inference cost.
2. **OCR Fallback (Tier 2)**: For scanned or degraded pages, PaddleOCR extracts localized words with confidence scores.
3. **Multimodal VLM Extraction (Tier 3)**: When dealing with ambiguous multi-row tables, skewed columns, or hand-annotated forms, the page image is routed through an open-weight VLM (e.g. PaddleOCR-VL or Qwen-2.5-VL via vLLM) with strict Pydantic JSON schemas.
4. **Provenance & Grounding**: Every extracted field retains an immutable citation:
   $$\text{Evidence} = \{\text{document\_id}, \text{page\_number}, \text{bbox: } [x_0, y_0, x_1, y_1], \text{confidence}\}$$

---

### 2. Deterministic 3-Way Verification Engine
To eliminate financial hallucinations, business reconciliation is **strictly deterministic**:
- The LLM **never** calculates arithmetic sums or decides whether quantities match.
- Calculations use Python's `Decimal` module for precision.
- The engine checks:
  $$\text{Ordered Quantity} \iff \text{Received Quantity} \iff \text{Billed Quantity}$$
  $$\text{Agreed Unit Price} \iff \text{Billed Unit Price}$$
  $$\sum (\text{Qty} \times \text{Price}) + \text{Tax} = \text{Total Billed}$$
- Findings are emitted as structured discrepancies with explicit severity levels (`HIGH`, `MEDIUM`, `LOW`, `INFO`).

---

### 3. Agentic Runtime (LangGraph)
The conversational layer ("Talk with your data") is governed by a **bounded LangGraph agent**:
- Operates under a strict read-only execution context.
- Equipped with a limited tool registry:
  - `get_case(case_id)`: Fetches full bundle state and verification status.
  - `list_findings(case_id, severity)`: Inspects specific discrepancies.
  - `search_documents(keyword, vendor)`: Queries indexed document text.
  - `get_metrics(metric_name, dimension, time_range)`: Retrieves validated database aggregates.
- **Safety Invariants**:
  - Maximum 4 tool iterations per question.
  - No direct SQL code generation or raw query execution.
  - Mandatory evidence citations for every numerical assertion.

---

### 4. Model Context Protocol (MCP) Integration
ProofFlow exposes its verification capabilities to external AI systems (such as Claude Desktop, Cursor, and enterprise agents) via a standardized MCP server implementation in `apps/mcp/`:

```json
{
  "tools": [
    {
      "name": "proofflow_get_case",
      "description": "Retrieve verification findings, line items, and audit states for a document case.",
      "parameters": {
        "type": "object",
        "properties": {
          "case_id": { "type": "string" }
        },
        "required": ["case_id"]
      }
    },
    {
      "name": "proofflow_get_metrics",
      "description": "Query approved aggregate metrics (e.g., mismatch rates, vendor discrepancy count).",
      "parameters": {
        "type": "object",
        "properties": {
          "metric": { "type": "string", "enum": ["mismatch_rate", "volume", "cycle_time"] },
          "vendor": { "type": "string" }
        },
        "required": ["metric"]
      }
    }
  ]
}
```

---

### 5. Closed-Loop Self-Improvement Engine

```mermaid
stateDiagram-v2
    [*] --> ProductionLogging: User/Worker runs pipeline
    ProductionLogging --> ReviewCapture: Human reviewer corrects field
    ReviewCapture --> FailureClustering: Group recurring error types
    FailureClustering --> CandidateGeneration: Generate prompt/rule fix
    CandidateGeneration --> FrozenBenchmark: Run offline test suite
    FrozenBenchmark --> RegressionCheck: Check accuracy & regressions
    RegressionCheck --> HumanApprovalGate: Passed benchmarks?
    HumanApprovalGate --> PromotedRelease: Reviewed and approved
    HumanApprovalGate --> RejectedCandidate: Regressed on other cases
    PromotedRelease --> [*]
    RejectedCandidate --> [*]
```

#### Key Tenets of Self-Improvement:
1. **Never autonomous in production**: Changes are proposed offline as versioned pull requests or configuration candidates.
2. **Immutable benchmark sets**: Optimization algorithms never run against the held-out test dataset.
3. **Comprehensive delta scoring**: Candidate prompts must prove zero regression on critical financial fields across historical benchmark cases.

---

## 🗄️ Database Architecture (PostgreSQL)

```mermaid
erDiagram
    DOCUMENTS ||--o{ EXTRACTION_RUNS : "has"
    DOCUMENTS }o--|| VERIFICATION_CASES : "belongs to"
    VERIFICATION_CASES ||--o{ VERIFICATION_FINDINGS : "produces"
    VERIFICATION_CASES ||--o{ REVIEW_EVENTS : "audited by"
    VERIFICATION_CASES ||--o{ JOBS : "processed in"
    EXTRACTION_RUNS ||--o{ EXECUTION_EVENTS : "logs"

    DOCUMENTS {
        uuid id PK
        string filename
        string doc_type
        string storage_uri
        string sha256_hash
        timestamp created_at
    }

    VERIFICATION_CASES {
        uuid id PK
        string case_number
        string status
        string vendor_name
        timestamp created_at
    }

    VERIFICATION_FINDINGS {
        uuid id PK
        uuid case_id FK
        string rule_code
        string severity
        jsonb observed_values
        jsonb expected_values
        jsonb evidence_locations
    }

    REVIEW_EVENTS {
        uuid id PK
        uuid case_id FK
        string reviewer_id
        string action
        jsonb corrected_fields
        timestamp created_at
    }
```
