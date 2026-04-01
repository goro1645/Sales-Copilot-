# Sales Copilot Design Spec

Date: 2026-04-01
Status: Draft approved in conversation, written for review
Project root: `D:\minimind\.worktrees\minimind-job-agent`

## 1. Goal

Build a local single-user but enterprise-shaped sales workbench that can:

- upload customer profile files and meeting note files
- parse and structure meeting outcomes
- retrieve related context from product, sales, and account knowledge
- maintain long-term account memory across multiple meetings
- score lead quality and opportunity stage
- generate follow-up recommendations and task lists
- simulate CRM write-backs for account status, meeting records, and tasks
- display the full workflow in a workbench UI

The system must make `LangGraph`, `workflow orchestration`, `tool use`, `RAG`, `memory`, `prompt design`, and `DeepSeek API integration` explicit enough to discuss in enterprise interviews.

## 2. Why This Version

This version is intentionally scoped as a `local enterprise workbench` instead of a chatbot or a full SaaS system.

Reasons:

- It is easy to demo on one machine.
- It still looks like an internal enterprise system because it supports multiple accounts, multiple meetings, CRM updates, and task tracking.
- It keeps engineering focus on agent workflow and data flow rather than login, permissions, and deployment infrastructure.

## 3. Non-Goals For V1

V1 will not include:

- multi-user authentication or RBAC
- real external CRM integration
- speech-to-text meeting transcription
- production vector databases or distributed infrastructure
- email sending, notifications, or calendar sync
- complex browser automation

## 4. User Journey

Primary user: one salesperson or account manager running the system locally.

Main journey:

1. Upload a customer profile document and a meeting note document.
2. Choose an existing account or create a new one.
3. Start the workflow from the workbench.
4. Review extracted meeting facts, account context, retrieved knowledge, lead score, opportunity stage, and risk flags.
5. Review generated follow-up plan and task suggestions.
6. Confirm simulated CRM write-back.
7. Inspect updated account memory, latest meeting record, and open tasks.

## 5. Architecture

The system is split into six layers.

### 5.1 Ingestion Layer

Responsibility:

- read uploaded files
- normalize file content into plain text
- associate inputs with an account and a meeting

Expected supported file types in V1:

- `.txt`
- `.md`
- `.json`

### 5.2 Tool Layer

Responsibility:

- perform deterministic reads and writes
- keep state-changing actions outside the LLM
- provide clear interfaces for LangGraph nodes

Initial tools:

- `load_account_profile`
- `load_meeting_note`
- `search_account_history`
- `search_product_knowledge`
- `search_sales_playbook`
- `get_open_tasks`
- `save_meeting_record`
- `update_crm_account`
- `create_followup_tasks`
- `append_account_memory`

### 5.3 RAG Layer

Knowledge sources:

- account history corpus
- product knowledge corpus
- sales playbook corpus

Retrieval behavior:

- use account-id filtering for account history
- use similarity retrieval for product and playbook chunks
- return top-k chunks with source labels

### 5.4 Memory Layer

Two memory types:

- short-term memory: the active `LangGraph` state for the current run
- long-term memory: persisted account memory across runs

Long-term memory must store:

- account status
- opportunity stage
- confirmed needs
- budget signals
- timeline signals
- decision makers
- risk flags
- unresolved objections
- latest recommended next step

### 5.5 LLM Layer

DeepSeek API will be the default model provider for V1.

The LLM layer must be abstracted behind a provider interface so the workflow and prompts do not depend directly on DeepSeek-specific transport code.

Suggested module split:

- `llm/base.py`
- `llm/deepseek_client.py`

### 5.6 Workbench UI Layer

The UI should be a local Streamlit workbench rather than a chat-first interface.

Main sections:

- upload panel
- account summary and lead dashboard
- CRM update preview
- task board
- retrieval and memory panel
- workflow execution log

## 6. LangGraph Workflow

### 6.1 Core Nodes

1. `ingest_files`
2. `parse_meeting_note`
3. `retrieve_context`
4. `load_account_memory`
5. `evaluate_lead`
6. `plan_follow_up`
7. `write_back_crm`
8. `generate_dashboard_output`

### 6.2 Node Responsibilities

`ingest_files`

- parse uploaded documents
- extract plain text
- identify account metadata if present

`parse_meeting_note`

- use DeepSeek to convert raw notes into structured JSON
- extract needs, objections, budget, timeline, competitors, next steps

`retrieve_context`

- call RAG tools for product knowledge, sales playbook, and account history
- attach retrieval outputs to the workflow state

`load_account_memory`

- load persisted account memory and open tasks

`evaluate_lead`

- generate lead score
- assign opportunity stage
- generate risk flags
- determine priority

`plan_follow_up`

- create follow-up guidance
- generate recommended materials
- create task payloads

`write_back_crm`

- simulate CRM updates via tools
- save meeting record
- update account status and stage
- create tasks
- append long-term memory

`generate_dashboard_output`

- create UI-friendly summary cards and sections

### 6.3 Conditional Routing

The workflow should include explicit conditional edges after scoring:

- if structured information is insufficient: route to `need_more_info`
- if score is low: route to `low_priority_nurture`
- if score is medium: route to `standard_follow_up`
- if score is high: route to `high_priority_follow_up`

These routes should affect:

- urgency level
- recommended actions
- task priority
- CRM status updates

### 6.4 Workflow State

Minimum state keys:

- `account_id`
- `meeting_id`
- `customer_profile_raw`
- `meeting_note_raw`
- `customer_profile_structured`
- `meeting_summary`
- `retrieved_docs`
- `account_memory`
- `open_tasks`
- `lead_score`
- `lead_priority`
- `opportunity_stage`
- `risk_flags`
- `follow_up_plan`
- `crm_update_payload`
- `task_payload`
- `dashboard_output`
- `workflow_log`

## 7. Prompt Design

Prompts must be separated by business function instead of using one large prompt.

Required prompt builders:

- `meeting_parse_prompt`
- `lead_scoring_prompt`
- `followup_plan_prompt`
- `crm_update_prompt`
- `dashboard_summary_prompt`

Prompt requirements:

- request structured JSON where possible
- explicitly ban invented facts
- separate current meeting facts from retrieved context
- keep output fields stable for downstream nodes

## 8. DeepSeek API Integration

DeepSeek will be used for:

- meeting note extraction
- lead scoring and opportunity reasoning
- follow-up recommendation generation
- dashboard summary generation

DeepSeek will not directly perform database writes or CRM updates.

All state-changing actions must be executed through tools after the model returns structured payloads.

Configuration requirements:

- `DEEPSEEK_API_KEY`
- optional `DEEPSEEK_BASE_URL`, otherwise use the provider client's default base URL
- model name configurable from UI or settings

## 9. Data Model

V1 should persist at least six logical entities.

### 9.1 `accounts`

Fields:

- `id`
- `name`
- `industry`
- `size_segment`
- `status`
- `opportunity_stage`
- `last_contact_at`
- `created_at`
- `updated_at`

### 9.2 `meeting_records`

Fields:

- `id`
- `account_id`
- `meeting_title`
- `meeting_note_raw`
- `meeting_summary_json`
- `lead_score`
- `priority`
- `created_at`

### 9.3 `tasks`

Fields:

- `id`
- `account_id`
- `meeting_id`
- `title`
- `description`
- `priority`
- `due_at`
- `status`
- `created_at`

### 9.4 `account_memory`

Fields:

- `account_id`
- `confirmed_needs_json`
- `budget_signals_json`
- `timeline_signals_json`
- `decision_makers_json`
- `risk_flags_json`
- `recommended_next_step`
- `updated_at`

### 9.5 `crm_updates`

Fields:

- `id`
- `account_id`
- `meeting_id`
- `update_type`
- `before_json`
- `after_json`
- `created_at`

### 9.6 `knowledge_chunks`

Fields:

- `id`
- `source_type`
- `source_name`
- `chunk_text`
- `tags_json`
- `retrieval_metadata_json`

## 10. UI Design

The workbench should avoid a generic chat layout.

Recommended layout:

- left column: upload files and select account
- center column: lead score, account summary, opportunity stage, risk cards, recommended actions
- right column: CRM write-back preview and task list
- lower section: retrieved documents, account history, long-term memory, workflow trace

Key UI outputs after one run:

- structured meeting summary
- lead score and stage
- priority label
- next-step recommendation
- generated task list
- CRM update preview
- retrieval citations
- account memory snapshot

## 11. Testing Strategy

Testing must make workflow behavior explicit.

Required coverage:

- deterministic tool tests
- RAG retrieval tests
- memory load and append tests
- prompt builder tests
- graph routing tests
- runner tests with fake LLM provider
- UI utility tests

Critical scenarios:

- incomplete meeting note triggers `need_more_info`
- low score routes to nurture
- high score routes to high-priority follow-up
- CRM simulation writes account update, meeting record, and tasks together
- repeated account runs reuse prior memory

## 12. Observability And Debuggability

Because this is an interview-facing enterprise demo, workflow transparency matters.

V1 should expose:

- node execution order
- intermediate state snapshots or summaries
- retrieval source list
- CRM write-back log
- task creation log

## 13. Risks And Mitigations

Risk: model invents account facts  
Mitigation: structured prompts, tool-grounded context, explicit no-invention instruction

Risk: workflow scope becomes too large  
Mitigation: keep V1 local, single-user, and file-upload based

Risk: RAG adds complexity without clear value  
Mitigation: keep only three corpora and show retrieved sources in UI

Risk: memory and RAG responsibilities blur  
Mitigation: define memory as account-specific long-term facts and RAG as external contextual knowledge

## 14. Resume Positioning

Recommended project title:

`Sales Copilot: LangGraph Sales Lead And Meeting Intelligence Workbench`

Suggested narrative:

- enterprise sales workflow automation
- LangGraph orchestration with conditional routing
- DeepSeek API integration for structured reasoning
- RAG over account history, product knowledge, and sales playbooks
- long-term account memory across meetings
- tool-driven CRM update simulation and task generation

## 15. Open Implementation Decisions

These are intentionally fixed for V1 to avoid ambiguity later:

- deployment mode: local single-user
- UI mode: workbench, not chat-first
- LLM provider: DeepSeek by default
- persistence: SQLite
- CRM integration: simulated local write-back
- initial file types: `.txt`, `.md`, and `.json`

## 16. Success Criteria

V1 is successful if:

- a user can upload customer profile and meeting note files
- the workflow runs end-to-end through LangGraph
- the system uses RAG, account memory, and explicit tools
- DeepSeek powers extraction and reasoning tasks
- CRM updates and follow-up tasks are simulated and persisted
- the UI looks and behaves like an enterprise sales workbench
- the architecture is clear enough to explain in interviews
