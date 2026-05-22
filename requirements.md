# Project: FinOps Cost Intelligence Backend

Build a backend service that ingests raw cloud usage and billing events from multiple sources, normalizes them, computes cost attribution, exposes analytics APIs, and detects spend anomalies.

# Problem Statement

**Build a multi-tenant FinOps analytics backend that ingests raw cloud and AI usage data, normalizes it into a canonical cost model, allocates spend to business entities using configurable rules, exposes analytics APIs, and detects anomalous spend patterns. The system must support idempotent reprocessing, late-arriving data, reconciliation from raw to aggregate, and performant drill-down queries over millions of records.**

The system should ingest cloud cost and usage data from files:
- aws_cur_like_usage.csv : AWS CUR-style raw usage and billing records
- azure_cost_export_like.csv : Azure cost export-style records
- internal_ai_usage_events.jsonl : Internal AI usage events

It should normalize the data into a common schema and support:

- Cost by tenant / project / team / environment
- Tag-based allocation
- Daily and hourly rollups
- Budget tracking
- Anomaly detection
- Top cost drivers
- Unit economics for AI workloads

The backend should expose APIs that a dashboard could use.

## Input Data

### 1. AWS-style Usage Records

Fields like:

- `account_id`
- `payer_account_id`
- `usage_start_time`
- `usage_end_time`
- `service`
- `usage_type`
- `operation`
- `region`
- `availability_zone`
- `resource_id`
- `linked_account_id`
- `unblended_cost`
- `blended_cost`
- `usage_amount`
- `currency`
- `tags`
- `line_item_type`
- `pricing_unit`

### 2. Azure-style Cost Records

Fields like:

- `subscription_id`
- `resource_group`
- `resource_id`
- `meter_category`
- `meter_subcategory`
- `consumed_service`
- `cost_in_billing_currency`
- `quantity`
- `date`
- `tags`
- `reservation_id`
- `pricing_model`

### 3. Internal AI Usage Events

Fields like:

- `tenant_id`
- `user_id`
- `project_id`
- `request_id`
- `model`
- `provider`
- `input_tokens`
- `output_tokens`
- `cached_tokens`
- `cost_usd`
- `latency_ms`
- `timestamp`
- `environment`
- `feature_name`
- `metadata`
- Missing tags
- Duplicate events
- Late-arriving records
- Inconsistent resource IDs
- Cost corrections / refunds
- Multiple currencies
- Reservation / savings-plan style discounts
- Partial hours
- Negative adjustment rows

## 1. Ingestion Pipeline

Requirements:

- Ingest raw JSONL or CSV files
- Normalize into a canonical schema
- Deduplicate records
- Support reprocessing / idempotency
- Handle late-arriving data
- Maintain auditability from normalized records back to source rows

## 2. Data Model

Design tables for:

- Raw ingestion
- Normalized cost events
- Dimensions
- Daily/hourly aggregates
- Budgets
- Anomaly records

The schema should support:

- "Show me cost by service by day for tenant X"
- "Show me top 10 resources driving this week's increase"
- "Show me model spend per project"
- "Show me cost not allocated because tags are missing"

## 3. Allocation Engine

Require support for:

- Direct attribution by tags
- Fallback rules if tags are missing
- Shared-cost allocation across teams
- Business-mapping rules, such as:
    - If `env=prod` and `project=ai-hub`, allocate to platform team
    - If no owner tag but `resource_group` matches regex, map to default cost center
    - Percentage-based splits for shared resources

Build:

- A rule engine or config-driven mapping system
- Explanation for every allocation decision

## 4. Analytics API

Require REST APIs like:

- `GET /tenants/:id/cost-summary?from=&to=&group_by=service`
- `GET /tenants/:id/anomalies?from=&to=`
- `GET /tenants/:id/top-drivers?from=&to=`
- `GET /tenants/:id/budgets`
- `GET /tenants/:id/ai-unit-economics?project_id=...`
- `GET /tenants/:id/unallocated-cost`
- `GET /tenants/:id/cost-investigations/:investigation_id`

## 5. Anomaly Detection

Require:

- Daily spend anomaly detection
- Service-level anomaly detection
- Tenant/project-level anomaly detection
- Top contributor explanation

For example:

- Compare today vs trailing 7-day baseline
- Compare against seasonality by weekday
- Detect spikes in model token spend
- Explain anomaly using feature breakdown

## 6. Budgeting and Forecasting

Require:

- Monthly budget per tenant/project
- Burn rate
- Projected end-of-month spend
- Threshold alerts at 50/75/90/100%

## 7. Reconciliation

Require a reconciliation view:

- Raw source total
- Normalized total
- Allocated total
- Unallocated total
- Adjustments
- Deltas

# Stack Constraints

- **Backend:** Python FastAPI or Go
- **Storage:** PostgreSQL preferred
- **Optional warehouse:** DuckDB or ClickHouse
- **Queue:** Optional
- **Deployment:** Docker Compose
- No managed cloud services required

# Deliverables

- Source code
- Schema design
- Ingestion pipeline
- API implementation
- Sample data
- README with architecture
- Explanation of tradeoffs
- Test suite
- Performance notes
- Sample queries and outputs

Include:

- Data quality checks
- Idempotency strategy
- Backfill strategy
- Multi-tenant isolation strategy

# Bonus Points

**A single dashboard request must return a cost summary in under 500 ms on 5–20 million normalized records.**