# DataTalker - Product Requirements Document (PRD)

> Forward-looking product vision: what DataTalker should BECOME. Built from a 9-agent Sonnet 5 deep-research pass over the entire NL-to-data / text-to-SQL / conversational-analytics market (2025-2026). Companion to the current-state audit in [`CODEBASE_AUDIT.md`](CODEBASE_AUDIT.md) and the market map in [`COMPETITIVE_LANDSCAPE.md`](COMPETITIVE_LANDSCAPE.md).

**Research scope:** 92 products/frameworks/techniques across 8 segments. **Feature space mapped:** 74 features (30 table-stakes, 16 parity, 18 differentiator, 10 future-bet).

**DataTalker gap today:** ❌ 60 missing · 🟡 6 partial · ✅ 8 present.

---

## 1. Vision

DataTalker becomes the semantic-layer-first, BYO-everything conversational data platform that any enterprise, or any ISV building on top of one, can point at their own warehouse, own LLM, and own deployment boundary - and trust the answer, not just admire the demo.

## 2. Problem

Every credible NL-to-data offering today is either (a) locked to one warehouse's compute and governance model (Snowflake Cortex Analyst, Databricks Genie, BigQuery/Looker, QuickSight), forcing a single-vendor bet enterprises with heterogeneous, multi-cloud, or on-prem estates can't make; or (b) a generic BYO-LLM chat-with-data tool (Vanna, Chat2DB, AskYourDatabase) that reimplements security and semantics poorly, if at all, and fails the enterprise security review before accuracy is ever discussed. Meanwhile raw schema-only text-to-SQL - which is exactly what DataTalker's current prototype does - collapses from ~85-91% on academic benchmarks to 6-21% execution accuracy on real enterprise schemas (Spider 2.0), and has zero authentication, RBAC, audit logging, or config surface, so it cannot even be piloted past a single laptop today. There is no independent, self-hostable, model-and-warehouse-agnostic product that pairs a governed, LLM-writable semantic layer with enterprise-grade trust controls and ships it as infrastructure (MCP-native) rather than only a proprietary chat UI.

**Target market.** Mid-market to large enterprises (500-10,000+ employees) with heterogeneous or multi-cloud data estates (a mix of Postgres/MySQL OLTP, one or more cloud warehouses, and legacy on-prem systems) who cannot or will not standardize on a single hyperscaler's semantic/AI stack, plus regulated industries (finance, healthcare, insurance) requiring on-prem/VPC/air-gapped deployment and BYO-LLM data-residency guarantees. A secondary, high-leverage segment is ISVs and platform teams who want to embed governed conversational analytics inside their own customer-facing product (the GoodData/Sisense Compose SDK niche) without adopting a full BI suite.

## 3. Personas

### Priya, Business/Ops Analyst - Primary end user asking questions
**Needs:** Get a trustworthy answer in plain English without waiting on a data engineer; See the SQL and result provenance so she can defend a number in a meeting; Get a chart, not just a raw table; Ask natural follow-ups ('now break that down by region') without re-typing full context

**Jobs to be done:**
- Answer an ad hoc business question in under a minute with a number she can cite in a leadership deck
- Export/share a result to Slack or a dashboard without opening a BI tool

### Marcus, Analytics/Data Engineer - Owns schema, connectors, and semantic model curation
**Needs:** A low-friction way to auto-model a schema into metrics/dimensions instead of hand-writing YAML for weeks; Confidence that generated SQL respects joins and business logic he's already defined once; A verified-query workflow to lock in known-good answers for the questions leadership asks weekly; Dialect coverage for the actual warehouses/DBs the company runs, not just Postgres/SQLite

**Jobs to be done:**
- Stand up a new data source and reach 80% question coverage within a day, not a quarter
- Curate and expand the semantic layer based on what users are actually asking

### Elena, Security/IT Admin - Gatekeeper for any tool touching production data
**Needs:** SSO/SAML/OIDC and role-based access before evaluation even begins; Row-level security and column masking that inherits from the source DB, not a second parallel permission model to audit; Full audit log of every NL question, generated SQL, and row-level data access; A choice of LLM provider (or none - on-prem) so prompts/data never leave an approved compliance boundary

**Jobs to be done:**
- Sign off on a security review in under 30 days by checking off SSO, RBAC, audit logging, and data-residency controls
- Prove to compliance that no user ever sees data they aren't entitled to, even via NL

### Dana, VP Analytics / BI Platform Owner - Economic buyer, owns the semantic model and the vendor relationship
**Needs:** Avoid vendor lock-in to a single warehouse's AI stack given a multi-cloud estate; Predictable, governable cost as query volume scales org-wide (not per-seat-only pricing); Evidence of accuracy and trust (confidence scores, verified-query coverage, eval dashboards) to justify self-service rollout to the board; A migration path that doesn't require ripping out existing BI tools

**Jobs to be done:**
- Expand self-service analytics adoption beyond the data team without a corresponding spike in wrong-number incidents
- Report a defensible ROI/cost-per-query number to finance

### Sam, ISV/Platform Engineer - Embeds conversational analytics into their own customer-facing SaaS product
**Needs:** A white-label, embeddable SDK/API rather than a full standalone BI seat; Multi-tenant isolation so one customer's semantic model/data never leaks to another; BYO-LLM so their own model/vendor contracts apply, not DataTalker's; Usage-based pricing that matches their own per-customer economics

**Jobs to be done:**
- Ship 'ask your data' inside their product under their own brand within weeks, not months
- Guarantee tenant isolation to their own enterprise customers during their security reviews

## 4. Competitive positioning

DataTalker enters a market that has already converged on a clear architectural consensus - governed semantic layer, execution-guided self-correction, show-the-SQL trust, and inherited RBAC/RLS - but that consensus is currently locked inside either single-warehouse platforms (Snowflake Cortex Analyst, Databricks Genie, BigQuery/Looker, QuickSight) that demand a hyperscaler bet, or BI-suite copilots (ThoughtSpot, Qlik, Power BI, Tableau, Sigma) priced and packaged around an existing seat-based platform. Independent challengers that once occupied the flexible middle (Waii, Seek AI, Outerbase) were acquired by Salesforce, IBM, and Cloudflare within months of each other in 2025, leaving a real gap for a self-hostable, BYO-LLM, BYO-warehouse, MCP-native product that treats the semantic layer as infrastructure any agent can query rather than a walled chat UI.

DataTalker's prototype today has none of the governance, semantic-layer, or output-parity features that gate enterprise evaluation, but it also carries none of the lock-in baggage of the incumbents. The winning path is not to out-feature Snowflake or Databricks on their own turf, but to be the vendor-neutral, deeply customizable, embeddable option for the multi-cloud, on-prem, and ISV segments those incumbents structurally cannot serve - winning first on trust and governance table-stakes (phases 1-3), then on the semantic-layer accuracy moat (phase 2), and only then differentiating further on MCP-native interoperability and proactive agentic intelligence (phases 4-5), which research shows even the best-funded incumbents have not yet fully claimed.

## 5. How DataTalker wins (differentiators)

- Semantic-layer-first architecture as the core moat: ship an LLM-writable, auto-modeled metrics/dimensions/joins layer (à la WrenAI MDL / dbt MetricFlow) as day-one infrastructure, not a retrofit - this is the single lever research shows takes accuracy from ~6-10% to 98-100% on real enterprise schemas.
- BYO-everything positioning against hyperscaler lock-in: any LLM (cloud or local/on-prem), any warehouse/DB dialect, any deployment topology (SaaS, VPC, air-gapped) - the explicit wedge for the large segment of enterprises with multi-cloud or on-prem estates that cannot standardize on Snowflake/Databricks/Google/AWS's own AI stack.
- MCP-native from day one: expose the semantic layer and query engine as first-class MCP tools/resources so any agent host (Claude, Copilot, Cursor, ChatGPT) can drive DataTalker - treating it as queryable infrastructure rather than only a proprietary chat UI, ahead of most independent competitors and matching where the whole market (Looker, dbt, AtScale, Oracle) is converging.
- Governance-inherited, not reinvented: enforce RBAC/RLS/column-masking by inheriting the source DB's native controls where they exist, layering DataTalker-native ABAC only where the source lacks it - avoiding the credibility gap of generic chat-with-data tools that ask enterprises to trust a second, weaker permission model.
- Open-core, self-hostable, developer-embeddable: a genuinely open, inspectable semantic layer and pipeline (not just an API wrapper) that developers can extend, plus a white-label embed SDK - targeting the ISV/embedded-analytics niche (GoodData/Sisense Compose SDK) that large BI suites deprioritize relative to their own branded UI.
- Verified-query-repository-as-a-feature: let teams lock in known-good NL->SQL pairs for the questions leadership actually asks, mined back into the semantic model over time - a concrete, demonstrable trust mechanism competitive with Snowflake's VQR that most independent/OSS competitors lack.
- Deliberately defer the agentic/proactive/write-back frontier (where even incumbents are immature) as a phase-5 differentiator once trust, accuracy, and governance foundations are proven - avoiding the trap of shipping impressive-looking agentic demos on top of an ungoverned, unauditable core.

### Non-goals

- Not building a full drag-and-drop dashboard/report-builder BI replacement in the near term - DataTalker augments existing BI stacks and spreadsheets rather than competing head-on with Tableau/Power BI/Looker as a general visualization tool.
- Not building or operating a data warehouse/storage engine - DataTalker always queries the customer's existing systems, never ingests and owns a copy of their data as a product of record.
- Not committing to a single hyperscaler's model or compute stack (no Bedrock-only or Vertex-only architecture) - BYO-LLM is a first-class requirement, not an afterthought.
- Not treating unstructured document/RAG Q&A as a core focus in phases 1-3 - structured NL-to-data is the wedge; document grounding (à la Cortex Search combined with Cortex Analyst) is an explicit later consideration, not a v1 requirement.
- Not training a proprietary foundation model in phase 1 - an on-prem fine-tuned SQL-specialist model is a future-bet, not a near-term dependency.
- Not shipping agentic write-back / autonomous action-taking (triggering webhooks, CRM writes, etc.) until the trust, audit, and approval-workflow foundation (phases 1-3) is proven in production - the governance blast radius of write actions is materially larger than read-only NLQ and is explicitly deferred.
- Not pursuing voice interfaces or spreadsheet-native (Excel/Sheets add-in) products in the initial roadmap - noted as adjacent whitespace but out of scope until the core warehouse/DB-connected product is enterprise-ready.

## 6. Feature taxonomy

Tier legend: 🟥 **Table-stakes** (must-have or DOA) · 🟧 **Parity** (expected by mid-market) · 🟩 **Differentiator** (where we can win) · 🔮 **Future-bet** (leapfrog). Status = DataTalker today.

### 6.1 NL Understanding & SQL Generation

_The core generation loop. Table-stakes here is necessary but, per research, insufficient alone - raw schema-only generation is what collapses on real enterprise schemas (6-21% on Spider 2.0), so this category must be read together with the Semantic Layer category, not in isolation._

| Feature | Tier | DataTalker | Who has it |
|---|---|---|---|
| **Zero-shot LLM SQL generation from reflected schema** - Reflect live DB schema and prompt an LLM to write SQL directly against it. | 🟥 Table-stakes | ✅ present | Universal across every product surveyed |
| **Stateful multi-turn conversation** - Resolve follow-up questions ('now by region') against prior turns' tables/filters/context, not just suggest follow-up prompts. | 🟥 Table-stakes | 🟡 partial | Databricks Genie (improved context handling), ThoughtSpot, Delphina |
| **Pluggable LLM providers (BYO-LLM)** - Swap between OpenAI, Anthropic, Gemini, Bedrock, Azure OpenAI, or local models (Ollama/vLLM) per tenant, not hardwired to one vendor. | 🟥 Table-stakes | ❌ missing | ThoughtSpot, Sisense, Vanna, WrenAI, DB-GPT - now standard across nearly every serious product |
| **Multi-statement / multi-part question handling** - Correctly decompose and render results for a single NL ask that implies multiple SQL statements. | 🟧 Parity | 🟡 partial | MAC-SQL, DIN-SQL decomposition patterns; Genie multi-step |
| **Schema linking / pruning for large schemas** - Retrieve only the top-K relevant tables/columns instead of stuffing the whole information_schema into the prompt. | 🟧 Parity | ❌ missing | LlamaIndex SQLTableRetrieverQueryEngine, CHESS, X-Linking, RASL |
| **Query decomposition into sub-questions/CTEs** - Break a complex analytical question into simpler composable sub-queries before assembling final SQL. | 🟩 Differentiator | ❌ missing | MAC-SQL Decomposer, DIN-SQL, QDecomp |
| **On-prem fine-tuned SQL-specialist model option** - Offer a small, purpose-built SQL model (SQLCoder/NSQL-class) for fully offline/air-gapped inference as an alternative to any external API call. | 🔮 Future-bet | ❌ missing | Numbers Station (NSQL), Defog SQLCoder, Chat2DB-SQL-7B |

### 6.2 Semantic / Metrics Layer

_Per 2026 benchmarks, routing through a governed semantic layer lifts frontier-model accuracy from ~84-90% to 98-100% on modeled questions, versus 6-10% for raw text-to-SQL on real enterprise schemas. This is the single highest-leverage investment in the entire PRD and DataTalker's primary proposed moat._

| Feature | Tier | DataTalker | Who has it |
|---|---|---|---|
| **Business glossary / synonym mapping** - Map business terminology and synonyms ('JD' = 'Jane Doe', 'revenue' = specific column expression) onto physical schema elements. | 🟥 Table-stakes | ❌ missing | Nearly every semantic-layer vendor |
| **LLM-writable semantic/metrics model** - A human- and LLM-editable model (tables->'models', dimensions, metrics, joins, synonyms) that narrows the LLM's task from 'write SQL' to 'select the right governed metric,' analogous to WrenAI's MDL, dbt MetricFlow, or Snowflake Semantic Views. | 🟩 Differentiator | ❌ missing | dbt MetricFlow, Cube, WrenAI MDL, Snowflake Semantic Views, Databricks Metric Views, LookML |
| **Verified Query Repository** - Curated bank of human-approved NL-question->SQL pairs matched directly for known questions and mined to expand semantic-model coverage over time. | 🟩 Differentiator | ❌ missing | Snowflake Cortex Analyst VQR, ThoughtSpot verified answers/search tokens |
| **Auto-modeling / one-click semantic model generation** - Scan a connected schema (including low-cardinality columns and historical query logs) to auto-propose a first-draft semantic model, cutting the classic weeks-of-YAML-authoring onboarding cost. | 🟩 Differentiator | ❌ missing | AtScale One-Click Modeling, Databricks database-scan seeding, Dataherald context-store seeding |
| **Open/portable metric spec** - Define metrics in a vendor-neutral format so customers aren't locked into DataTalker's own semantic dialect, aligned with the Open Semantic Interchange direction. | 🔮 Future-bet | ❌ missing | dbt Labs, Cube, Snowflake, Salesforce (OSI initiative) |

### 6.3 Accuracy, Self-Correction & Evaluation

_Execution-guided repair is now table-stakes and shows diminishing returns on frontier models that produce syntactically valid but semantically wrong SQL - so accuracy work must expand into entity grounding, few-shot retrieval, and judge-based semantic checks, not just retry-on-error._

| Feature | Tier | DataTalker | Who has it |
|---|---|---|---|
| **Execution-guided retry on error/empty result** - Run generated SQL, catch DB errors or unexpectedly empty results, feed the error back to the LLM for a bounded repair loop. | 🟥 Table-stakes | ✅ present | Uber QueryGPT, Swiggy Hermes, LinkedIn SQL Bot, WrenAI, Waii, PandasAI |
| **Typed error classification in repair loop** - Distinguish syntax errors, permission errors, and semantic mismatches to route to the correct correction strategy rather than a single generic retry. | 🟧 Parity | 🟡 partial | CHESS unit-tester agent, ReFoRCE |
| **Column-value / entity grounding** - Fuzzy-match literal values mentioned in the question (names, statuses, typos) against actual distinct DB values via LSH/edit-distance/embedding similarity before generating filters. | 🟧 Parity | ❌ missing | CHESS, Amazon RASL |
| **Dynamic few-shot example retrieval** - Pull the most semantically similar verified question->SQL pairs at query time as in-context examples rather than static prompt examples. | 🟧 Parity | ❌ missing | Dubo-SQL, most semantic-layer vendors |
| **LLM-as-judge semantic-equivalence scoring** - A second LLM/model call scores whether generated SQL actually matches question intent before returning results, catching valid-but-wrong-intent queries. | 🟩 Differentiator | ❌ missing | Snowflake Cortex Analyst semantic-alignment layer |
| **Continuous eval harness (internal benchmark + regression)** - Customer-specific golden-query test sets plus BIRD/Spider-2.0-style internal benchmarks run pre-release and continuously in production. | 🟩 Differentiator | ❌ missing | Databricks Genie Benchmarks, Snowflake's internal 150-question benchmark |
| **Per-answer confidence scoring** - Surface a confidence signal (verified-match vs fresh generation, judge score) alongside every answer. | 🟩 Differentiator | ❌ missing | Snowflake Cortex Analyst confidence object |

### 6.4 Trust, Verification & Explainability

_Industry consensus (research segment: enterprise-requirements-gtm) treats 90% accuracy as commercially 'useless' without a hard trust guarantee - 'show your work' and principled refusal are the actual bar, not a nice-to-have._

| Feature | Tier | DataTalker | Who has it |
|---|---|---|---|
| **Show-the-SQL** - Always expose the exact SQL executed alongside the NL answer for inspection. | 🟥 Table-stakes | ✅ present | Universal among credible vendors |
| **Principled abstention ('insufficient grounding/permission')** - Return no answer rather than a fabricated or permission-violating one when confidence or authorization is insufficient. | 🟥 Table-stakes | ❌ missing | Databricks Genie, Snowflake Cortex Analyst |
| **Full audit trail** - Log every NL question, generated SQL, executing user/role, and rows touched for compliance review. | 🟥 Table-stakes | ❌ missing | Universal enterprise requirement per research |
| **Reasoning/lineage explainability** - Explain which semantic terms, tables, and joins were resolved to answer the question, not just the final SQL string. | 🟧 Parity | ❌ missing | ThoughtSpot search-token audit trail, Amazon Q assumptions/filters trace |
| **Verified-query / confidence badge in UI** - Visually flag whether an answer came from a pre-approved verified query versus freshly generated SQL. | 🟩 Differentiator | ❌ missing | Snowflake Cortex Analyst, ThoughtSpot Spotter |
| **Human-in-the-loop approval for low-confidence queries** - Route low-confidence or first-time query patterns to a review/approval step before returning or acting. | 🔮 Future-bet | ❌ missing | Emerging pattern across guardrail literature |

### 6.5 Visualization & Output Modalities

_Raw tables are the single most visible gap versus every competitor surveyed - every BI copilot and warehouse-native tool auto-generates charts; DataTalker currently cannot._

| Feature | Tier | DataTalker | Who has it |
|---|---|---|---|
| **Auto-generated charts from results** - Turn query results directly into an appropriate chart type, not just a table. | 🟥 Table-stakes | ❌ missing | Universal across BI copilots, startups, and warehouse-native tools |
| **NL narrative summary of results** - Plain-language explanation of what the data shows alongside the raw answer. | 🟥 Table-stakes | ✅ present | Universal |
| **Streaming responses** - Stream SQL generation and answer tokens incrementally rather than waiting for full completion. | 🟥 Table-stakes | ❌ missing | Vanna 2.0, most modern chat-with-data tools |
| **Export (CSV/Excel/PDF)** - Export query results and charts in common formats. | 🟥 Table-stakes | ❌ missing | Universal |
| **Follow-up question suggestions** - Suggest relevant next questions after each answer. | 🟧 Parity | ✅ present | Most BI copilots and startups |
| **Save/pin chart to a dashboard** - Persist a generated chart into a lightweight dashboard for reuse. | 🟧 Parity | ❌ missing | Genie, Basedash, Sigma |
| **Proactive narrative digest delivery** - Push scheduled/triggered narrative summaries to Slack/Teams/email rather than requiring users to visit the app. | 🟩 Differentiator | ❌ missing | Tableau Pulse, Domo, Datarails Insights |

### 6.6 Connectors & Data Sources

_Breadth here determines whether DataTalker can actually be pointed at a real enterprise's fragmented stack; current dialect coverage (SQLite+Postgres) is a hard blocker for most target customers._

| Feature | Tier | DataTalker | Who has it |
|---|---|---|---|
| **SQLite & Postgres support** - Existing dialect coverage. | 🟥 Table-stakes | ✅ present | Baseline for all |
| **MySQL / SQL Server / Oracle dialects** - Expand SQLAlchemy dialect coverage to the most common enterprise OLTP engines. | 🟥 Table-stakes | ❌ missing | Chat2DB, LangChain SQLDatabaseToolkit, Vanna |
| **First-class file/spreadsheet ingestion (CSV/Excel)** - Treat uploaded spreadsheets as a first-class, queryable source, not just DB files. | 🟥 Table-stakes | 🟡 partial | Julius AI, Rows AI, PandasAI |
| **Cloud warehouse connectors** - Snowflake, BigQuery, Redshift, Databricks connectivity. | 🟧 Parity | ❌ missing | Every warehouse-native vendor plus Wren AI, Dataherald, Waii |
| **Flexible DB-input methods (upload/path/URL/connection-string)** - Four ways to point DataTalker at a database, unusually flexible versus tools that assume you're already on their warehouse. | 🟩 Differentiator | ✅ present | AskYourDatabase (partial), most warehouse-native tools lack this entirely |
| **Existing semantic-layer ingestion (dbt/Cube/LookML import)** - Import an existing governed metrics layer instead of forcing customers to re-author one from scratch. | 🟩 Differentiator | ❌ missing | AtScale integrates with Genie/Cortex; largely unaddressed by independents |
| **Cross-source federation** - Answer a single NL question by joining across more than one connected source. | 🔮 Future-bet | ❌ missing | Databricks Lakehouse Federation, Looker cross-warehouse |

### 6.7 Security & Governance

_Per research, this is the non-negotiable gate to even be evaluated by enterprise IT/security - currently DataTalker has none of it, making this the single largest business risk in the PRD, ahead of accuracy._

| Feature | Tier | DataTalker | Who has it |
|---|---|---|---|
| **SSO/SAML/OIDC authentication** - Enterprise login integration; no bespoke credential store. | 🟥 Table-stakes | ❌ missing | Universal enterprise requirement |
| **Role-based access control (RBAC)** - Control which users/roles can query which connections/semantic models. | 🟥 Table-stakes | ❌ missing | Universal |
| **Row-level security & column masking** - Enforce at query time, ideally inherited from the source DB's native roles plus an additional DataTalker-native ABAC layer for sources without native RLS. | 🟥 Table-stakes | ❌ missing | Snowflake RBAC/RAP, Unity Catalog ABAC, QuickSight RLS, WrenAI RLAC/CLAC |
| **Read-only sandboxed execution** - Enforce execution via a genuinely read-only DB role/sandbox, not a keyword blocklist alone (current validator is bypassable). | 🟥 Table-stakes | 🟡 partial | LangChain recommended pattern, Delphina Firecracker microVMs |
| **Audit logging** - Immutable log of every question, SQL, and data access event. | 🟥 Table-stakes | ❌ missing | Universal enterprise requirement |
| **Compliance certifications (SOC2, ISO27001, HIPAA, ISO 42001)** - Formal attestations required for enterprise procurement. | 🟥 Table-stakes | ❌ missing | Qlik Answers ISO 42001, most enterprise BI vendors SOC2 |
| **PII auto-classification & masking** - Automatically detect and mask sensitive fields (emails, SSNs) before they reach the LLM or the user. | 🟧 Parity | ❌ missing | Snowflake SYSTEM$CLASSIFY, Immuta/Privacera-style platforms |
| **Attribute-based access control (ABAC)** - Tag-driven policies applying automatically across catalogs/schemas at scale. | 🟩 Differentiator | ❌ missing | Databricks Unity Catalog ABAC |

### 6.8 Multi-Tenancy & Deployment

_Currently there is no working containerized deploy and no config surface at all - this blocks every persona from admin to ISV and must be fixed before any other differentiator matters operationally._

| Feature | Tier | DataTalker | Who has it |
|---|---|---|---|
| **Multi-tenant workspace isolation** - Logical separation of connections, semantic models, and conversation history per tenant/org. | 🟥 Table-stakes | ❌ missing | Universal for any multi-customer deployment |
| **Config surface (per-tenant settings, prompts, model choice)** - Admin-configurable settings instead of hardcoded values across the codebase. | 🟥 Table-stakes | ❌ missing | Universal |
| **Async request handling & connection pooling** - Non-blocking I/O and pooled DB connections to serve concurrent users. | 🟥 Table-stakes | ❌ missing | Universal for production BI |
| **Working containerized deployment (Docker/Helm)** - A reproducible, documented deploy path; current scripts are incomplete/removed. | 🟥 Table-stakes | ❌ missing | Universal |
| **BYO-LLM provider selection per tenant** - Let each tenant choose/restrict which LLM provider processes their prompts. | 🟥 Table-stakes | ❌ missing | ThoughtSpot, Sisense, GoodData ('no vendor lock-in') |
| **On-prem / VPC / air-gapped deployment option** - Deploy fully inside a customer's own compliance boundary with no external calls when combined with local LLM support. | 🟩 Differentiator | ❌ missing | Seek AI (Snowflake Native App), Numbers Station NSQL, Google Conversational Analytics regional endpoints |

### 6.9 Observability & Cost Governance

_LLM cost governance has shifted from an engineering afterthought to a procurement-visible line item; DataTalker has schema caching but no query/semantic caching, no usage analytics, and no budget controls._

| Feature | Tier | DataTalker | Who has it |
|---|---|---|---|
| **Structured pipeline logging/tracing** - Trace each stage (schema fetch, generation, validation, execution, formatting) for debugging and audit. | 🟥 Table-stakes | ❌ missing | Universal for production systems |
| **Usage analytics dashboard** - Queries, cost, and latency broken down per team/tenant/model. | 🟧 Parity | ❌ missing | AI-gateway category, Kyligence, ThoughtSpot credit dashboards |
| **Token-based rate limiting & budget caps** - Hierarchical spend caps at org/team/key level with hard stops. | 🟧 Parity | ❌ missing | Snowflake model-level RBAC, AI gateways (Kong AI Gateway class) |
| **Semantic caching** - Match functionally-equivalent questions (not just exact hashes) to cut redundant LLM calls; schema caching exists today but not query-level caching. | 🟩 Differentiator | ❌ missing | Cube semantic layer caching, AI gateway category |
| **Model-tier routing** - Route simple lookups to cheaper/faster models and reserve premium models for complex reasoning. | 🟩 Differentiator | ❌ missing | Emerging pattern across cost-governance literature |
| **Per-model RBAC** - Gate which roles can invoke which LLMs, doubling as a cost and data-exposure control. | 🔮 Future-bet | ❌ missing | Snowflake Cortex model-level RBAC |

### 6.10 Collaboration, Distribution & Embedding

_Ambient delivery (Slack/Teams) and MCP are becoming the actual battleground beyond the dashboard; embeddability is also DataTalker's clearest wedge into the ISV segment underserved by big BI suites._

| Feature | Tier | DataTalker | Who has it |
|---|---|---|---|
| **Web chat UI** - Existing React/Vite frontend for direct interaction. | 🟥 Table-stakes | ✅ present | Universal |
| **Shareable saved queries/links** - Persist and share a specific question+answer with teammates. | 🟥 Table-stakes | ❌ missing | Universal |
| **Slack/Teams delivery** - Deliver answers and proactive alerts inside chat tools people already use. | 🟧 Parity | ❌ missing | Tableau Pulse, Julius Slack Agent, Domo, Qlik |
| **Scheduled/recurring queries and reports** - Run a saved question on a cadence and deliver the result automatically. | 🟧 Parity | ❌ missing | Delphina Workflows, Datarails Insights |
| **Embeddable/white-label SDK for ISVs** - API/SDK to embed conversational analytics inside a third party's own product under their brand, with per-tenant isolation. | 🟩 Differentiator | ❌ missing | GoodData AI Assistant, Sisense Compose SDK, ThoughtSpot Everywhere, Domo Everywhere |
| **MCP server exposing semantic layer & query engine** - Expose the governed semantic model and query execution as MCP tools/resources so any agent host (Claude, Copilot, Cursor) can query it - infrastructure, not just a chat UI. | 🟩 Differentiator | ❌ missing | Looker Managed MCP, dbt MCP server, AtScale MCP, Oracle Analytics MCP Server, WrenAI agent-first design |

### 6.11 Admin & Customization

_Highly-customizable is the explicit brief; today there is no admin surface at all, which also blocks the multi-tenant and ISV stories above._

| Feature | Tier | DataTalker | Who has it |
|---|---|---|---|
| **Admin console (connectors/users/roles)** - Central place to manage data sources, users, and role assignments. | 🟥 Table-stakes | ❌ missing | Universal |
| **Custom prompt/instruction injection per tenant** - Let admins steer SQL generation style, tone, and disambiguation rules per deployment (akin to Snowflake semantic-view custom instructions). | 🟧 Parity | ❌ missing | Snowflake custom instructions, MicroStrategy Auto tone/detail customization |
| **Pluggable validator/guardrail rules** - Configurable, layered guardrails (deterministic rules escalating to LLM-judge checks) beyond a static keyword blocklist. | 🟧 Parity | 🟡 partial | Layered guardrail pattern documented across semantic-layer/accuracy research |
| **Custom branding/white-label theming** - Rebrand the UI/embed for ISV customers. | 🟩 Differentiator | ❌ missing | GoodData, MicroStrategy Auto, Domo Everywhere |
| **Feature flagging / gradual rollout controls** - Roll out new agent behaviors or model versions to a subset of tenants first. | 🔮 Future-bet | ❌ missing | Not commonly documented as a standalone feature in this market yet |

### 6.12 Agentic / Proactive Intelligence

_Research explicitly flags proactive monitoring and multi-step 'deep research over structured data' as the least-commoditized, most whitespace capability in the whole market - a deliberate later-phase bet, not a near-term must-have, and write-back actions are an explicit non-goal until trust foundations are proven._

| Feature | Tier | DataTalker | Who has it |
|---|---|---|---|
| **Proactive anomaly detection & root-cause narration** - Continuously monitor data and surface unprompted anomalies with driver-level explanation, pushed to Slack/email. | 🔮 Future-bet | ❌ missing | ThoughtSpot SpotIQ, Tableau Pulse, Kyligence root-cause analysis, Guandata BI Copilot |
| **Multi-step autonomous data investigation** - Plan -> query -> re-plan -> synthesize a full investigative report from a single open-ended prompt, not a single-turn NL-to-chart. | 🔮 Future-bet | ❌ missing | Explicitly flagged as underexplored even by incumbents (DataSTORM/DABStep-Research) |
| **Scheduled monitoring agents** - Background agents that watch metrics against thresholds and alert on breach. | 🔮 Future-bet | ❌ missing | Delphina Proactive Agents, Basedash Autopilot, Zenlytic Zoë |
| **Agentic write-back / action-taking** - Trigger downstream actions (webhooks, CRM updates) from a conversational agent rather than only reading data. | 🔮 Future-bet | ❌ missing | Sigma Agents, Mosaic PE Autopilot |

## 7. Architecture pillars

- **Governed Semantic Core** - An LLM-writable, versionable metrics/dimensions/joins model sitting between raw schema and every LLM call, auto-seeded from a schema scan and refined by a Verified Query Repository - the primary accuracy and governance substrate for the whole product.
- **Pluggable Model & Data Fabric** - Adapter layers for LLM providers (cloud and local) and DB dialects (via SQLAlchemy plus warehouse-specific connectors), so no customer is forced onto a single vendor's model or database engine.
- **Verify-Then-Execute Pipeline** - A multi-stage generation pipeline - schema/entity linking, SQL generation, static guardrail checks, sandboxed read-only execution, bounded error-driven repair, LLM-judge semantic-equivalence check, confidence scoring - replacing the current single-shot generate-and-validate flow.
- **Inherited Governance & Audit Plane** - RBAC/SSO/ABAC enforced at the DataTalker layer and, where available, passed through to the source DB's native RLS/column masking, with every question, generated SQL statement, and data access event immutably logged.
- **MCP-First Interface Layer** - The semantic layer and query engine are exposed as MCP tools/resources as a first-class interface, with the web chat UI and embeddable SDK built as clients of the same interface rather than a special-cased internal API.
- **Observability & Cost Control Plane** - Structured tracing of every pipeline stage, per-tenant usage/cost dashboards, token budgets, semantic caching, and model-tier routing, so LLM spend is a managed, visible line item rather than an unbounded liability.
- **Multi-Tenant Deployment Fabric** - A single codebase deployable as multi-tenant SaaS, dedicated VPC, or fully air-gapped on-prem, with per-tenant configuration (connectors, prompts, model choice, branding) as a first-class config surface rather than hardcoded values.

## 8. Accuracy strategy

The single hardest problem in NL-to-data is being *right* on real enterprise schemas. Concrete techniques:

- Make the governed semantic layer the default grounding path: route every question through metric/dimension resolution first, falling back to raw schema-based generation only for genuinely unmodeled ad hoc questions - this is the documented lever that closes most of the enterprise accuracy gap.
- Schema linking and pruning via embeddings over table/column descriptions (and, for large schemas, row-value sampling) so the LLM only ever sees the relevant slice of a potentially 1,000+ column enterprise schema.
- Column-value/entity grounding: fuzzy-match literal values in the question against actual distinct DB values (LSH + edit-distance + embedding similarity) to catch the class of errors where SQL is structurally right but filters on the wrong/nonexistent literal.
- Dynamic few-shot retrieval of the most similar Verified Query Repository entries as in-context examples for every new question, continuously expanded from real usage.
- Formalize the existing retry-on-empty/sql_retry.py logic into a typed, bounded execution-guided repair loop (syntax vs. permission vs. semantic-mismatch errors routed differently) rather than a single generic retry.
- Add an LLM-as-judge semantic-equivalence check as a final gate before returning results, specifically to catch syntactically-valid-but-intent-wrong SQL that execution-only checks miss on frontier models.
- Layered guardrails: cheap deterministic checks (forbidden operations, injection patterns, row-limit enforcement) first, escalating to the LLM-judge only for ambiguous cases, to control latency and cost.
- Principled abstention: when confidence is below threshold or the semantic layer can't map the question to a governed metric, return 'insufficient grounding' rather than a fabricated number.
- Continuous evaluation: maintain a customer-specific golden-query regression suite plus an internal BIRD/Spider-2.0-style benchmark, run pre-release and monitored live in production via LLM-as-judge scoring of faithfulness/relevancy/task-completion.
- Longer-term: offer a fine-tuned, on-prem SQL-specialist model (SQLCoder/NSQL-class) per customer schema as an accuracy and data-residency lever once enough verified query pairs accumulate (documented >10-examples-per-table fine-tuning threshold).

## 9. Success metrics

| Metric | Target |
|---|---|
| Execution accuracy on semantic-layer-backed questions (internal benchmark) | >=90% within 12 months, approaching the 98-100% ceiling published for governed semantic-layer routing |
| Execution accuracy on raw/unmodeled schema questions | >=40% within 12 months (vs. current 6-21% enterprise-schema baseline for schema-only text-to-SQL) |
| Time-to-80%-question-coverage for a new customer schema | <1 business day via auto-modeling, down from weeks of manual semantic-model authoring |
| Share of answers served from Verified Query Repository | >=30% of production query volume within 6 months of a deployment going live, growing over time |
| Abstention correctness | >=98% correct refusal on ungrounded/unauthorized queries with <5% false-refusal rate on answerable questions |
| Enterprise security review time-to-sign-off | <30 days once SSO/RBAC/audit/SOC2 controls ship (vs. currently unable to pass review at all) |
| Self-service adoption | >=60% weekly-active-to-licensed-seat ratio within 6 months of enterprise rollout |
| P95 end-to-end query latency | <8 seconds for generation + execution + formatting |
| Mean LLM cost per simple query | <$0.01/query via semantic caching and model-tier routing, with full per-tenant cost visibility |
| ISV embed time-to-launch | <4 weeks from SDK access to a live embedded deployment for a design-partner ISV |

## 10. Roadmap

### Phase 0 (current) - Working prototype
- Schema reflection + caching
- Gemini-only SQL generation
- Keyword-blocklist validator
- Retry-on-empty
- 4 DB-input methods
- Follow-up question suggestions
- Multi-statement execution (buggy)

**Outcome:** Demonstrable single-user prototype; not deployable to any real customer due to zero security, no config surface, and hardwired LLM/dialect.

### Phase 1: Enterprise-Safe Foundation - Make it legally and operationally deployable
- SSO/SAML/OIDC authentication
- RBAC and per-tenant config surface
- Audit logging
- Read-only sandboxed execution (replace keyword blocklist)
- Async request handling + connection pooling
- Working containerized deploy (Docker/Helm)
- Structured pipeline logging/observability
- Fix multi-statement rendering bug

**Outcome:** Passes a baseline enterprise security review and can be piloted with real concurrent users; no accuracy or semantic-layer work yet.

### Phase 2: Semantic Layer & Accuracy Core - Close the enterprise-accuracy-cliff gap
- LLM-writable semantic/metrics model + auto-modeling
- Verified Query Repository
- Schema linking/pruning + column-value grounding
- Dynamic few-shot retrieval
- Pluggable LLM providers (BYO-LLM)
- Dialect expansion: MySQL, SQL Server, Snowflake, BigQuery, Databricks
- Formalized typed repair loop

**Outcome:** Accuracy on modeled questions reaches the 90%+ range; product works across the customer's actual multi-warehouse/multi-dialect estate.

### Phase 3: Trust & Output Parity - Meet the enterprise trust and visualization bar
- Auto-generated charts
- Streaming responses
- Verified-query confidence badge in UI
- Principled abstention behavior
- LLM-as-judge semantic-equivalence gate
- Continuous eval harness (golden queries + internal benchmark)
- Row-level security / column masking (own + inherited)
- PII auto-classification
- Compliance certification program (SOC2, ISO27001)

**Outcome:** Output modality parity with BI copilots; passes deeper security/compliance diligence; trustworthy enough for broad self-service rollout.

### Phase 4: Scale & Interoperability - Become infrastructure, not just an app
- Multi-tenant workspace isolation
- MCP server exposing semantic layer + query engine
- On-prem/VPC/air-gapped deployment option
- Token budgets, semantic caching, model-tier routing
- Usage analytics/cost dashboards
- Slack/Teams delivery
- Embeddable/white-label SDK for ISVs
- Admin console

**Outcome:** Deployable at scale across tenants and channels; opens the ISV/embedded-analytics revenue line and agent-ecosystem interoperability.

### Phase 5: Agentic & Proactive - Differentiate on the market's least-commoditized frontier
- Proactive anomaly detection & root-cause narration
- Scheduled monitoring agents with Slack/email push
- Multi-step autonomous data investigation ('deep research' over structured data)
- Approval-gated agentic write-back (behind explicit customer opt-in)
- On-prem fine-tuned SQL-specialist model option

**Outcome:** Moves beyond reactive Q&A into proactive, trusted agentic analytics - the whitespace research shows even incumbents haven't fully claimed.

## 11. Risks

- Security/governance gap is existential, not incremental: with zero SSO/RBAC/audit today, DataTalker cannot pass even a basic enterprise security review, meaning zero enterprise revenue is possible until Phase 1 ships - this must be sequenced before any accuracy or agentic investment, however tempting the demo value.
- Accuracy overpromising risk: research shows raw schema-only text-to-SQL collapses to 6-21% on real enterprise schemas; marketing or selling against benchmark-only accuracy numbers (vs. semantic-layer-backed numbers) will produce visible, trust-destroying failures in enterprise pilots.
- Single-vendor LLM dependency (hardwired Gemini) is both a cost and a data-residency/compliance risk - any customer requiring contractual no-training/no-retention guarantees or a specific approved model provider cannot be served until BYO-LLM ships.
- Market consolidation risk: credible independent text-to-SQL vendors (Waii, Seek AI, Outerbase) were acquired by larger platforms within months in 2025; hyperscalers may keep commoditizing semantic-layer-plus-chat faster than a smaller entrant can differentiate, so the BYO/on-prem/embeddable wedge must be defended deliberately, not assumed durable.
- Semantic-layer curation cost is real and could stall time-to-value: dbt/LookML-style modeling takes real human effort; without a genuinely effective auto-modeling/one-click generation feature, customers may churn before reaching enough coverage to see value.
- MCP and agent-ecosystem standards are moving fast (Linux Foundation AAIF stewardship, Microsoft Power BI MCP servers within ~1 year of MCP's release) - building a proprietary-chat-only interface risks obsolescence as 'just another chat UI' if MCP-native support slips too far behind schedule.
- Frontier-model failure mode shift: execution-guided self-correction shows diminishing returns as modern LLMs increasingly produce syntactically valid but semantically wrong SQL with no error to trigger repair - over-relying on the existing retry-on-empty mechanism without adding judge-based semantic checks will plateau accuracy well short of targets.
- Scalability debt: current lack of async handling/connection pooling and a working container deploy means even a successful single-pilot conversation cannot yet extend to concurrent multi-user production traffic without a real infrastructure rework.
- Scope-creep risk: the full feature space spans ~70+ features across 12 categories; without disciplined phase sequencing (security/governance and semantic layer before agentic/proactive), the team risks spreading thin across differentiators before table-stakes are secured, repeating the trap of shipping impressive demos on an ungoverned core.
