from pydantic import BaseModel, Field
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, Dict, List, Any
from enum import Enum


class CostSourceType(str, Enum):
    AWS = "aws"
    AZURE = "azure"
    AI_EVENT = "ai_event"


class CostStatus(str, Enum):
    PENDING = "pending"
    ALLOCATED = "allocated"
    UNALLOCATED = "unallocated"


class AllocationEntityType(str, Enum):
    TEAM = "team"
    PROJECT = "project"
    COST_CENTER = "cost_center"


# Request/Response schemas
class NormalizedCostEvent(BaseModel):
    tenant_id: str
    resource_id: str
    service: str
    provider: str
    cost_usd: Decimal
    quantity: Optional[Decimal] = None
    unit_type: Optional[str] = None
    event_date: date
    event_hour: datetime
    region: Optional[str] = None
    operation: Optional[str] = None
    resource_type: Optional[str] = None
    tags: Dict[str, str] = Field(default_factory=dict)
    is_allocated: bool = False
    status: CostStatus = CostStatus.PENDING
    is_late_arriving: Optional[bool] = False
    ingestion_lag_days: Optional[int] = 0

    class Config:
        json_encoders = {Decimal: lambda v: float(v)}


class FileUploadRequest(BaseModel):
    tenant_id: str
    source_type: CostSourceType


class CostSummaryItem(BaseModel):
    date: date
    service: Optional[str] = None
    region: Optional[str] = None
    cost_usd: Decimal
    allocated_cost_usd: Decimal
    unallocated_cost_usd: Decimal
    record_count: int

    class Config:
        json_encoders = {Decimal: lambda v: float(v)}


class CostSummaryResponse(BaseModel):
    tenant_id: str
    from_date: date
    to_date: date
    total_cost_usd: Decimal
    allocated_cost_usd: Decimal
    unallocated_cost_usd: Decimal
    items: List[CostSummaryItem]

    class Config:
        json_encoders = {Decimal: lambda v: float(v)}


class CostDetailsResponse(BaseModel):
    tenant_id: str
    from_date: date
    to_date: date
    items: List[NormalizedCostEvent]
    total_count: int
    limit: int
    offset: int


class TopDriverItem(BaseModel):
    rank: int
    service: str
    cost_usd: Decimal
    percent_of_total: Decimal

    class Config:
        json_encoders = {Decimal: lambda v: float(v)}


class TopDriverResponse(BaseModel):
    tenant_id: str
    from_date: date
    to_date: date
    total_cost_usd: Decimal
    top_drivers: List[TopDriverItem]

    class Config:
        json_encoders = {Decimal: lambda v: float(v)}


class UnallocatedCostItem(BaseModel):
    date: date
    service: str
    cost_usd: Decimal
    record_count: int
    top_missing_tags: List[str] = []

    class Config:
        json_encoders = {Decimal: lambda v: float(v)}


class UnallocatedCostResponse(BaseModel):
    tenant_id: str
    from_date: date
    to_date: date
    total_unallocated_cost_usd: Decimal
    items: List[UnallocatedCostItem]

    class Config:
        json_encoders = {Decimal: lambda v: float(v)}


class AnomalyItem(BaseModel):
    date: date
    scope_type: Optional[str] = None
    scope_id: Optional[str] = None
    baseline_cost: Decimal
    actual_cost: Decimal
    variance_percent: Decimal
    confidence: Decimal

    class Config:
        json_encoders = {Decimal: lambda v: float(v)}


class AnomalyResponse(BaseModel):
    tenant_id: str
    from_date: date
    to_date: date
    items: List[AnomalyItem]


class BudgetItem(BaseModel):
    entity_type: str
    entity_id: str
    budget_amount: Decimal
    spent_amount: Decimal
    remaining_amount: Decimal
    burn_rate_percent: Decimal
    period_start: date
    period_end: date

    # Forecasting fields
    days_elapsed: int
    days_remaining: int
    daily_avg_spend: Decimal
    projected_end_of_period_spend: Decimal
    projected_overage: Decimal  # negative if under budget
    alert_status: str  # "on-track" | "caution" | "alert" | "critical"
    alert_threshold_percent: Decimal

    class Config:
        json_encoders = {Decimal: lambda v: float(v)}


class BudgetResponse(BaseModel):
    tenant_id: str
    items: List[BudgetItem]


class ReconciliationItem(BaseModel):
    batch_id: str
    source_type: str
    raw_record_count: int
    raw_total_cost: Decimal
    normalized_record_count: int
    normalized_total_cost: Decimal
    allocated_count: int
    allocated_total_cost: Decimal
    unallocated_total_cost: Decimal

    # Deltas
    raw_to_normalized_delta: Decimal  # should be 0 (lossless)
    allocated_to_unallocated_split: str  # "X% allocated, Y% unallocated"
    created_at: datetime

    class Config:
        json_encoders = {Decimal: lambda v: float(v)}


class ReconciliationResponse(BaseModel):
    tenant_id: str
    summary: Dict[str, Any]  # Overall totals
    audits: List[ReconciliationItem]


class AIUnitEconomicsItem(BaseModel):
    project_id: str
    total_cost_usd: Decimal
    total_tokens: Decimal
    cost_per_1k_tokens: Decimal
    total_requests: int

    class Config:
        json_encoders = {Decimal: lambda v: float(v)}


class AIUnitEconomicsResponse(BaseModel):
    tenant_id: str
    from_date: date
    to_date: date
    items: List[AIUnitEconomicsItem]


class AllocationAction(BaseModel):
    entity_type: AllocationEntityType
    entity_id: str
    amount: Decimal
    reason: str

    class Config:
        json_encoders = {Decimal: lambda v: float(v)}


class AllocationResponse(BaseModel):
    normalized_event_id: int
    allocations: List[AllocationAction]
    is_fully_allocated: bool


class HealthResponse(BaseModel):
    status: str
    environment: str
    database: str
