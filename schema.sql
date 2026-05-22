-- ========================================================================
-- FinOps Cost Intelligence Backend - Idempotent PostgreSQL Schema
-- Simplified and focused on essentials
-- ========================================================================

-- ========================================================================
-- 1. EXTENSIONS
-- ========================================================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ========================================================================
-- 2. ENUMS (Defined as VARCHAR for compatibility with SQLAlchemy)
-- ========================================================================
-- Note: Using VARCHAR instead of ENUM for better SQLAlchemy compatibility
-- Valid values maintained via application logic

-- ========================================================================
-- 3. CORE TABLES
-- ========================================================================

-- Tenants (Multi-tenancy)
CREATE TABLE IF NOT EXISTS tenants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tenants_name ON tenants(name);

-- Raw cost events (Immutable audit trail)
CREATE TABLE IF NOT EXISTS raw_cost_events (
    id BIGSERIAL PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    source_type VARCHAR(50) NOT NULL,  -- AWS, AZURE, AI_EVENT, ADJUSTMENT
    source_hash VARCHAR(64) NOT NULL,  -- Idempotency key
    raw_data JSONB NOT NULL,
    batch_id UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, source_hash)
);

CREATE INDEX IF NOT EXISTS idx_raw_cost_events_tenant_id ON raw_cost_events(tenant_id);
CREATE INDEX IF NOT EXISTS idx_raw_cost_events_source_hash ON raw_cost_events(source_hash);
CREATE INDEX IF NOT EXISTS idx_raw_cost_events_batch_id ON raw_cost_events(batch_id);

-- Normalized cost events (Canonical schema)
CREATE TABLE IF NOT EXISTS normalized_cost_events (
    id BIGSERIAL PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    raw_event_id BIGINT NOT NULL REFERENCES raw_cost_events(id) ON DELETE CASCADE,

    -- Identification
    resource_id VARCHAR(1024) NOT NULL,
    resource_type VARCHAR(255),
    service VARCHAR(255) NOT NULL,
    operation VARCHAR(255),
    region VARCHAR(100),

    -- Cost and usage
    cost_usd NUMERIC(20, 10) NOT NULL,
    quantity NUMERIC(20, 10),
    unit_type VARCHAR(255),

    -- Provider
    provider VARCHAR(50) NOT NULL,  -- aws, azure, ai

    -- Time
    event_date DATE NOT NULL,
    event_hour TIMESTAMP WITH TIME ZONE NOT NULL,

    -- Tags for allocation
    tags JSONB DEFAULT '{}'::jsonb,

    -- Status
    is_allocated BOOLEAN DEFAULT FALSE,
    status VARCHAR(50) DEFAULT 'pending',  -- pending, allocated, unallocated

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_normalized_cost_events_tenant_id ON normalized_cost_events(tenant_id);
CREATE INDEX IF NOT EXISTS idx_normalized_cost_events_tenant_date_service ON normalized_cost_events(tenant_id, event_date, service);
CREATE INDEX IF NOT EXISTS idx_normalized_cost_events_resource_id ON normalized_cost_events(resource_id);
CREATE INDEX IF NOT EXISTS idx_normalized_cost_events_status ON normalized_cost_events(status, is_allocated);
CREATE INDEX IF NOT EXISTS idx_normalized_cost_events_event_date ON normalized_cost_events(event_date);
CREATE INDEX IF NOT EXISTS idx_normalized_cost_events_raw_event_id ON normalized_cost_events(raw_event_id);
CREATE INDEX IF NOT EXISTS idx_normalized_cost_events_tags ON normalized_cost_events USING gin(tags);

-- Allocation rules (Configuration for rule engine)
CREATE TABLE IF NOT EXISTS allocation_rules (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    name VARCHAR(255) NOT NULL,
    priority INT NOT NULL DEFAULT 999,
    conditions JSONB DEFAULT '{}'::jsonb,
    action VARCHAR(255) NOT NULL,  -- allocate_to_team, allocate_to_project, etc.
    action_params JSONB DEFAULT '{}'::jsonb,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, name)
);

CREATE INDEX IF NOT EXISTS idx_allocation_rules_tenant_id ON allocation_rules(tenant_id);
CREATE INDEX IF NOT EXISTS idx_allocation_rules_priority ON allocation_rules(priority);

-- Cost allocations (Audit trail of allocation decisions)
CREATE TABLE IF NOT EXISTS cost_allocations (
    id BIGSERIAL PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    normalized_event_id BIGINT NOT NULL REFERENCES normalized_cost_events(id) ON DELETE CASCADE,
    allocation_rule_id UUID REFERENCES allocation_rules(id),

    -- Allocation target
    business_entity_type VARCHAR(50) NOT NULL,  -- team, project, cost_center
    business_entity_id VARCHAR(255) NOT NULL,

    -- Amount
    allocated_amount NUMERIC(20, 10) NOT NULL,

    -- Reason
    allocation_reason TEXT NOT NULL,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_cost_allocations_tenant_id ON cost_allocations(tenant_id);
CREATE INDEX IF NOT EXISTS idx_cost_allocations_normalized_event_id ON cost_allocations(normalized_event_id);
CREATE INDEX IF NOT EXISTS idx_cost_allocations_business_entity ON cost_allocations(business_entity_type, business_entity_id);

-- Daily aggregates (Pre-computed for <500ms queries)
CREATE TABLE IF NOT EXISTS cost_aggregates_daily (
    id BIGSERIAL PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    date DATE NOT NULL,
    service VARCHAR(255) NOT NULL,
    region VARCHAR(100),

    cost_usd NUMERIC(20, 10) DEFAULT 0,
    allocated_cost_usd NUMERIC(20, 10) DEFAULT 0,
    unallocated_cost_usd NUMERIC(20, 10) DEFAULT 0,
    record_count INT DEFAULT 0,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(tenant_id, date, service, region)
);

CREATE INDEX IF NOT EXISTS idx_cost_aggregates_daily_tenant_date_service ON cost_aggregates_daily(tenant_id, date, service);
CREATE INDEX IF NOT EXISTS idx_cost_aggregates_daily_tenant_date ON cost_aggregates_daily(tenant_id, date);

-- Cost by business entity
CREATE TABLE IF NOT EXISTS cost_aggregates_by_entity (
    id BIGSERIAL PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    date DATE NOT NULL,
    business_entity_type VARCHAR(50) NOT NULL,
    business_entity_id VARCHAR(255) NOT NULL,

    cost_usd NUMERIC(20, 10) DEFAULT 0,
    record_count INT DEFAULT 0,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(tenant_id, date, business_entity_type, business_entity_id)
);

CREATE INDEX IF NOT EXISTS idx_cost_aggregates_by_entity_tenant_date ON cost_aggregates_by_entity(tenant_id, date);

-- Budgets
CREATE TABLE IF NOT EXISTS budgets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    business_entity_type VARCHAR(50) NOT NULL,
    business_entity_id VARCHAR(255) NOT NULL,

    budget_period_start DATE NOT NULL,
    budget_period_end DATE NOT NULL,
    budget_amount NUMERIC(20, 2) NOT NULL,

    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT budget_dates CHECK (budget_period_start < budget_period_end),
    UNIQUE(tenant_id, business_entity_type, business_entity_id, budget_period_start)
);

CREATE INDEX IF NOT EXISTS idx_budgets_tenant_id ON budgets(tenant_id);

-- Anomalies
CREATE TABLE IF NOT EXISTS anomalies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    date DATE NOT NULL,

    scope_type VARCHAR(50),  -- tenant, project, service, team
    scope_id VARCHAR(255),

    baseline_cost NUMERIC(20, 10) NOT NULL,
    actual_cost NUMERIC(20, 10) NOT NULL,
    variance_percent NUMERIC(10, 2) NOT NULL,

    top_drivers JSONB,  -- Array of {service: X, cost: Y}
    explanation TEXT,
    confidence NUMERIC(5, 2),

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_anomalies_tenant_id ON anomalies(tenant_id);
CREATE INDEX IF NOT EXISTS idx_anomalies_date ON anomalies(date);

-- Reconciliation audit
CREATE TABLE IF NOT EXISTS reconciliation_audit (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    batch_id UUID NOT NULL,
    source_type VARCHAR(50) NOT NULL,

    raw_record_count INT DEFAULT 0,
    raw_total_cost NUMERIC(20, 10) DEFAULT 0,

    normalized_record_count INT DEFAULT 0,
    normalized_total_cost NUMERIC(20, 10) DEFAULT 0,

    allocated_count INT DEFAULT 0,
    allocated_total_cost NUMERIC(20, 10) DEFAULT 0,
    unallocated_total_cost NUMERIC(20, 10) DEFAULT 0,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_reconciliation_audit_tenant_id ON reconciliation_audit(tenant_id);
CREATE INDEX IF NOT EXISTS idx_reconciliation_audit_batch_id ON reconciliation_audit(batch_id);

-- Ingestion batches
CREATE TABLE IF NOT EXISTS ingestion_batches (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    source_type VARCHAR(50) NOT NULL,

    file_name VARCHAR(1024),
    status VARCHAR(50) DEFAULT 'pending',  -- pending, processing, completed, failed

    total_records INT DEFAULT 0,
    processed_records INT DEFAULT 0,
    failed_records INT DEFAULT 0,

    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ingestion_batches_tenant_id ON ingestion_batches(tenant_id);
CREATE INDEX IF NOT EXISTS idx_ingestion_batches_status ON ingestion_batches(status);

-- ========================================================================
-- 4. VIEWS
-- ========================================================================

-- Unallocated costs
CREATE OR REPLACE VIEW v_unallocated_costs AS
SELECT
    nce.id,
    nce.tenant_id,
    nce.event_date,
    nce.service,
    nce.cost_usd,
    nce.resource_id,
    nce.tags
FROM normalized_cost_events nce
WHERE nce.is_allocated = FALSE;

-- Cost by service and day
CREATE OR REPLACE VIEW v_cost_by_service_daily AS
SELECT
    cad.tenant_id,
    cad.date,
    cad.service,
    SUM(cad.cost_usd) as total_cost_usd,
    SUM(cad.allocated_cost_usd) as allocated_cost_usd,
    SUM(cad.unallocated_cost_usd) as unallocated_cost_usd,
    SUM(cad.record_count) as record_count
FROM cost_aggregates_daily cad
GROUP BY cad.tenant_id, cad.date, cad.service;

-- ========================================================================
-- 5. FUNCTIONS
-- ========================================================================

-- Refresh daily aggregates for a tenant and date
CREATE OR REPLACE FUNCTION refresh_daily_aggregates(
    p_tenant_id UUID,
    p_date DATE
) RETURNS INT AS $$
DECLARE
    v_affected_rows INT;
BEGIN
    DELETE FROM cost_aggregates_daily
    WHERE tenant_id = p_tenant_id AND date = p_date;

    INSERT INTO cost_aggregates_daily (
        tenant_id, date, service, region,
        cost_usd, allocated_cost_usd, unallocated_cost_usd, record_count
    )
    SELECT
        p_tenant_id,
        p_date,
        nce.service,
        nce.region,
        SUM(nce.cost_usd),
        SUM(CASE WHEN nce.is_allocated THEN nce.cost_usd ELSE 0 END),
        SUM(CASE WHEN NOT nce.is_allocated THEN nce.cost_usd ELSE 0 END),
        COUNT(*)
    FROM normalized_cost_events nce
    WHERE nce.tenant_id = p_tenant_id AND nce.event_date = p_date
    GROUP BY nce.service, nce.region;

    GET DIAGNOSTICS v_affected_rows = ROW_COUNT;
    RETURN v_affected_rows;
END;
$$ LANGUAGE plpgsql;

-- ========================================================================
-- 5A. TRIGGERS FOR AUTOMATIC AGGREGATE UPDATES
-- ========================================================================

-- Trigger to update aggregates when normalized events are inserted
CREATE OR REPLACE FUNCTION update_daily_aggregates_on_insert()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO cost_aggregates_daily (
        tenant_id, date, service, region,
        cost_usd, allocated_cost_usd, unallocated_cost_usd, record_count
    )
    VALUES (
        NEW.tenant_id,
        NEW.event_date,
        NEW.service,
        NEW.region,
        NEW.cost_usd,
        CASE WHEN NEW.is_allocated THEN NEW.cost_usd ELSE 0 END,
        CASE WHEN NOT NEW.is_allocated THEN NEW.cost_usd ELSE 0 END,
        1
    )
    ON CONFLICT (tenant_id, date, service, region) DO UPDATE SET
        cost_usd = cost_aggregates_daily.cost_usd + NEW.cost_usd,
        allocated_cost_usd = cost_aggregates_daily.allocated_cost_usd +
            (CASE WHEN NEW.is_allocated THEN NEW.cost_usd ELSE 0 END),
        unallocated_cost_usd = cost_aggregates_daily.unallocated_cost_usd +
            (CASE WHEN NOT NEW.is_allocated THEN NEW.cost_usd ELSE 0 END),
        record_count = cost_aggregates_daily.record_count + 1,
        updated_at = CURRENT_TIMESTAMP;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_daily_aggregates
AFTER INSERT ON normalized_cost_events
FOR EACH ROW
EXECUTE FUNCTION update_daily_aggregates_on_insert();

-- ========================================================================
-- 5b. MIGRATION: Late-arriving data tracking
-- ========================================================================
ALTER TABLE normalized_cost_events
    ADD COLUMN IF NOT EXISTS is_late_arriving BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS ingestion_lag_days INTEGER DEFAULT 0;

-- ========================================================================
-- END OF SCHEMA
-- ========================================================================
