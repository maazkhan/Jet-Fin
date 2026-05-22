from sqlalchemy import Column, String, Integer, Float, DateTime, Date, Boolean, ForeignKey, Numeric, Text, JSON, Index, UniqueConstraint, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

Base = declarative_base()


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    raw_cost_events = relationship("RawCostEvent", back_populates="tenant")
    normalized_cost_events = relationship("NormalizedCostEvent", back_populates="tenant")
    cost_allocations = relationship("CostAllocation", back_populates="tenant")
    allocation_rules = relationship("AllocationRule", back_populates="tenant")
    cost_aggregates_daily = relationship("CostAggregateDaily", back_populates="tenant")
    cost_aggregates_by_entity = relationship("CostAggregateByEntity", back_populates="tenant")
    budgets = relationship("Budget", back_populates="tenant")
    anomalies = relationship("Anomaly", back_populates="tenant")
    reconciliation_audits = relationship("ReconciliationAudit", back_populates="tenant")


class RawCostEvent(Base):
    __tablename__ = "raw_cost_events"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    source_type = Column(String(50), nullable=False)
    source_hash = Column(String(64), nullable=False)
    raw_data = Column(JSONB, nullable=False)
    batch_id = Column(UUID(as_uuid=True))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="raw_cost_events")
    normalized_cost_events = relationship("NormalizedCostEvent", back_populates="raw_event")

    __table_args__ = (
        UniqueConstraint("tenant_id", "source_hash", name="uq_raw_events_tenant_source_hash"),
        Index("idx_raw_cost_events_tenant_id", "tenant_id"),
        Index("idx_raw_cost_events_source_hash", "source_hash"),
        Index("idx_raw_cost_events_batch_id", "batch_id"),
    )


class NormalizedCostEvent(Base):
    __tablename__ = "normalized_cost_events"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    raw_event_id = Column(Integer, ForeignKey("raw_cost_events.id", ondelete="CASCADE"), nullable=False)

    resource_id = Column(String(1024), nullable=False)
    resource_type = Column(String(255))
    service = Column(String(255), nullable=False)
    operation = Column(String(255))
    region = Column(String(100))

    cost_usd = Column(Numeric(20, 10), nullable=False)
    quantity = Column(Numeric(20, 10))
    unit_type = Column(String(255))

    provider = Column(String(50), nullable=False)
    event_date = Column(Date, nullable=False)
    event_hour = Column(DateTime(timezone=True), nullable=False)

    tags = Column(JSONB, default={})
    is_allocated = Column(Boolean, default=False)
    status = Column(String(50), default="pending")
    is_late_arriving = Column(Boolean, nullable=True, default=False)
    ingestion_lag_days = Column(Integer, nullable=True, default=0)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="normalized_cost_events")
    raw_event = relationship("RawCostEvent", back_populates="normalized_cost_events")
    allocations = relationship("CostAllocation", back_populates="normalized_event")

    __table_args__ = (
        Index("idx_normalized_cost_events_tenant_id", "tenant_id"),
        Index("idx_normalized_cost_events_tenant_date_service", "tenant_id", "event_date", "service"),
        Index("idx_normalized_cost_events_resource_id", "resource_id"),
        Index("idx_normalized_cost_events_status", "status", "is_allocated"),
        Index("idx_normalized_cost_events_event_date", "event_date"),
        Index("idx_normalized_cost_events_raw_event_id", "raw_event_id"),
        Index("idx_normalized_cost_events_tags", "tags", postgresql_using="gin"),
    )


class AllocationRule(Base):
    __tablename__ = "allocation_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    name = Column(String(255), nullable=False)
    priority = Column(Integer, default=999)
    conditions = Column(JSONB, default={})
    action = Column(String(255), nullable=False)
    action_params = Column(JSONB, default={})
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="allocation_rules")

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_allocation_rules_tenant_name"),
        Index("idx_allocation_rules_tenant_id", "tenant_id"),
        Index("idx_allocation_rules_priority", "priority"),
    )


class CostAllocation(Base):
    __tablename__ = "cost_allocations"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    normalized_event_id = Column(Integer, ForeignKey("normalized_cost_events.id", ondelete="CASCADE"), nullable=False)
    allocation_rule_id = Column(UUID(as_uuid=True), ForeignKey("allocation_rules.id"))

    business_entity_type = Column(String(50), nullable=False)
    business_entity_id = Column(String(255), nullable=False)
    allocated_amount = Column(Numeric(20, 10), nullable=False)
    allocation_reason = Column(Text, nullable=False)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="cost_allocations")
    normalized_event = relationship("NormalizedCostEvent", back_populates="allocations")

    __table_args__ = (
        Index("idx_cost_allocations_tenant_id", "tenant_id"),
        Index("idx_cost_allocations_normalized_event_id", "normalized_event_id"),
        Index("idx_cost_allocations_business_entity", "business_entity_type", "business_entity_id"),
    )


class CostAggregateDaily(Base):
    __tablename__ = "cost_aggregates_daily"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    date = Column(Date, nullable=False)
    service = Column(String(255), nullable=False)
    region = Column(String(100))

    cost_usd = Column(Numeric(20, 10), default=0)
    allocated_cost_usd = Column(Numeric(20, 10), default=0)
    unallocated_cost_usd = Column(Numeric(20, 10), default=0)
    record_count = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="cost_aggregates_daily")

    __table_args__ = (
        UniqueConstraint("tenant_id", "date", "service", "region", name="uq_aggregates_daily_key"),
        Index("idx_cost_aggregates_daily_tenant_date_service", "tenant_id", "date", "service"),
        Index("idx_cost_aggregates_daily_tenant_date", "tenant_id", "date"),
    )


class CostAggregateByEntity(Base):
    __tablename__ = "cost_aggregates_by_entity"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    date = Column(Date, nullable=False)
    business_entity_type = Column(String(50), nullable=False)
    business_entity_id = Column(String(255), nullable=False)

    cost_usd = Column(Numeric(20, 10), default=0)
    record_count = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="cost_aggregates_by_entity")

    __table_args__ = (
        UniqueConstraint("tenant_id", "date", "business_entity_type", "business_entity_id", name="uq_aggregates_entity_key"),
        Index("idx_cost_aggregates_by_entity_tenant_date", "tenant_id", "date"),
    )


class Budget(Base):
    __tablename__ = "budgets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    business_entity_type = Column(String(50), nullable=False)
    business_entity_id = Column(String(255), nullable=False)

    budget_period_start = Column(Date, nullable=False)
    budget_period_end = Column(Date, nullable=False)
    budget_amount = Column(Numeric(20, 2), nullable=False)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="budgets")

    __table_args__ = (
        CheckConstraint("budget_period_start < budget_period_end", name="chk_budget_dates"),
        UniqueConstraint("tenant_id", "business_entity_type", "business_entity_id", "budget_period_start",
                        name="uq_budgets_key"),
        Index("idx_budgets_tenant_id", "tenant_id"),
    )


class Anomaly(Base):
    __tablename__ = "anomalies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    date = Column(Date, nullable=False)

    scope_type = Column(String(50))
    scope_id = Column(String(255))

    baseline_cost = Column(Numeric(20, 10), nullable=False)
    actual_cost = Column(Numeric(20, 10), nullable=False)
    variance_percent = Column(Numeric(10, 2), nullable=False)

    top_drivers = Column(JSONB)
    explanation = Column(Text)
    confidence = Column(Numeric(5, 2))

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="anomalies")

    __table_args__ = (
        Index("idx_anomalies_tenant_id", "tenant_id"),
        Index("idx_anomalies_date", "date"),
    )


class ReconciliationAudit(Base):
    __tablename__ = "reconciliation_audit"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    batch_id = Column(UUID(as_uuid=True), nullable=False)
    source_type = Column(String(50), nullable=False)

    raw_record_count = Column(Integer, default=0)
    raw_total_cost = Column(Numeric(20, 10), default=0)

    normalized_record_count = Column(Integer, default=0)
    normalized_total_cost = Column(Numeric(20, 10), default=0)

    allocated_count = Column(Integer, default=0)
    allocated_total_cost = Column(Numeric(20, 10), default=0)
    unallocated_total_cost = Column(Numeric(20, 10), default=0)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="reconciliation_audits")

    __table_args__ = (
        Index("idx_reconciliation_audit_tenant_id", "tenant_id"),
        Index("idx_reconciliation_audit_batch_id", "batch_id"),
    )
