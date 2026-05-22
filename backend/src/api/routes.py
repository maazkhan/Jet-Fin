from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, text
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Optional, List
import logging

from src.database.connection import get_db
from src.database.models import (
    NormalizedCostEvent, CostAggregateDaily, CostAggregateByEntity,
    RawCostEvent, CostAllocation, Anomaly, Budget, AllocationRule, Tenant, ReconciliationAudit
)
from src.models import (
    CostSummaryResponse, CostSummaryItem, CostDetailsResponse,
    TopDriverResponse, TopDriverItem, UnallocatedCostResponse, UnallocatedCostItem,
    AnomalyResponse, AnomalyItem, BudgetResponse, BudgetItem,
    AIUnitEconomicsResponse, AIUnitEconomicsItem, AllocationResponse, AllocationAction,
    HealthResponse, ReconciliationResponse, ReconciliationItem, NormalizedCostEvent as NormalizedCostEventModel, CostStatus
)
from src.scheduler.jobs import detect_anomalies_daily, detect_anomalies_weekly, detect_anomalies_monthly

router = APIRouter(prefix="/api/v1", tags=["finops"])
logger = logging.getLogger(__name__)


def get_tenant_or_404(session: Session, tenant_id: str):
    tenant = session.query(Tenant).filter(Tenant.name == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Tenant {tenant_id} not found")
    return tenant


# ============================================================================
# HEALTH CHECK
# ============================================================================

@router.get("/health", response_model=HealthResponse)
async def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return HealthResponse(status="healthy", environment="production", database="postgresql")
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthResponse(status="unhealthy", environment="production", database="error")


# ============================================================================
# TENANT MANAGEMENT
# ============================================================================

@router.get("/tenants")
async def list_tenants(db: Session = Depends(get_db)):
    """List all available tenants."""
    tenants = db.query(Tenant).order_by(Tenant.name).all()
    return {
        "tenants": [{"id": str(t.id), "name": t.name} for t in tenants],
        "count": len(tenants)
    }


# ============================================================================
# COST ANALYTICS
# ============================================================================

@router.get("/tenants/{tenant_id}/cost-summary", response_model=CostSummaryResponse)
async def get_cost_summary(
    tenant_id: str,
    from_date: date = Query(...),
    to_date: date = Query(...),
    group_by: Optional[str] = Query("service"),
    db: Session = Depends(get_db)
):
    tenant = get_tenant_or_404(db, tenant_id)

    query = db.query(
        CostAggregateDaily.date,
        CostAggregateDaily.service if group_by == "service" else CostAggregateDaily.region,
        func.sum(CostAggregateDaily.cost_usd),
        func.sum(CostAggregateDaily.allocated_cost_usd),
        func.sum(CostAggregateDaily.unallocated_cost_usd),
        func.sum(CostAggregateDaily.record_count)
    ).filter(
        and_(
            CostAggregateDaily.tenant_id == tenant.id,
            CostAggregateDaily.date >= from_date,
            CostAggregateDaily.date <= to_date
        )
    ).group_by(
        CostAggregateDaily.date,
        CostAggregateDaily.service if group_by == "service" else CostAggregateDaily.region
    ).order_by(CostAggregateDaily.date)

    results = query.all()

    items = [
        CostSummaryItem(
            date=r[0],
            service=r[1] if group_by == "service" else None,
            region=r[1] if group_by == "region" else None,
            cost_usd=Decimal(str(r[2])) if r[2] else Decimal("0"),
            allocated_cost_usd=Decimal(str(r[3])) if r[3] else Decimal("0"),
            unallocated_cost_usd=Decimal(str(r[4])) if r[4] else Decimal("0"),
            record_count=int(r[5]) if r[5] else 0
        )
        for r in results
    ]

    total_cost = sum(item.cost_usd for item in items)
    total_allocated = sum(item.allocated_cost_usd for item in items)
    total_unallocated = sum(item.unallocated_cost_usd for item in items)

    return CostSummaryResponse(
        tenant_id=tenant_id,
        from_date=from_date,
        to_date=to_date,
        total_cost_usd=total_cost,
        allocated_cost_usd=total_allocated,
        unallocated_cost_usd=total_unallocated,
        items=items
    )


@router.get("/tenants/{tenant_id}/cost-details", response_model=CostDetailsResponse)
async def get_cost_details(
    tenant_id: str,
    from_date: date = Query(...),
    to_date: date = Query(...),
    service: Optional[str] = Query(None),
    limit: int = Query(100, le=1000),
    offset: int = Query(0),
    db: Session = Depends(get_db)
):
    tenant = get_tenant_or_404(db, tenant_id)

    query = db.query(NormalizedCostEvent).filter(
        and_(
            NormalizedCostEvent.tenant_id == tenant.id,
            NormalizedCostEvent.event_date >= from_date,
            NormalizedCostEvent.event_date <= to_date
        )
    )

    if service:
        query = query.filter(NormalizedCostEvent.service == service)

    total_count = query.count()
    results = query.offset(offset).limit(limit).all()

    items = [
        NormalizedCostEventModel(
            tenant_id=str(r.tenant_id),
            resource_id=r.resource_id,
            service=r.service,
            provider=r.provider,
            cost_usd=Decimal(str(r.cost_usd)),
            quantity=Decimal(str(r.quantity)) if r.quantity else None,
            unit_type=r.unit_type,
            event_date=r.event_date,
            event_hour=r.event_hour,
            region=r.region,
            operation=r.operation,
            resource_type=r.resource_type,
            tags=r.tags or {},
            is_allocated=r.is_allocated,
            status=CostStatus(r.status),
            is_late_arriving=r.is_late_arriving,
            ingestion_lag_days=r.ingestion_lag_days
        )
        for r in results
    ]

    return CostDetailsResponse(
        tenant_id=tenant_id,
        from_date=from_date,
        to_date=to_date,
        items=items,
        total_count=total_count,
        limit=limit,
        offset=offset
    )


@router.get("/tenants/{tenant_id}/top-drivers", response_model=TopDriverResponse)
async def get_top_drivers(
    tenant_id: str,
    from_date: date = Query(...),
    to_date: date = Query(...),
    limit: int = Query(10, le=100),
    db: Session = Depends(get_db)
):
    tenant = get_tenant_or_404(db, tenant_id)

    query = db.query(
        CostAggregateDaily.service,
        func.sum(CostAggregateDaily.cost_usd)
    ).filter(
        and_(
            CostAggregateDaily.tenant_id == tenant.id,
            CostAggregateDaily.date >= from_date,
            CostAggregateDaily.date <= to_date
        )
    ).group_by(
        CostAggregateDaily.service
    ).order_by(
        func.sum(CostAggregateDaily.cost_usd).desc()
    ).limit(limit)

    results = query.all()
    total_cost = sum(Decimal(str(r[1])) for r in results)

    items = [
        TopDriverItem(
            rank=i + 1,
            service=r[0],
            cost_usd=Decimal(str(r[1])),
            percent_of_total=Decimal(str(r[1])) / total_cost * 100 if total_cost > 0 else Decimal("0")
        )
        for i, r in enumerate(results)
    ]

    return TopDriverResponse(
        tenant_id=tenant_id,
        from_date=from_date,
        to_date=to_date,
        total_cost_usd=total_cost,
        top_drivers=items
    )


@router.get("/tenants/{tenant_id}/unallocated-cost", response_model=UnallocatedCostResponse)
async def get_unallocated_cost(
    tenant_id: str,
    from_date: date = Query(...),
    to_date: date = Query(...),
    group_by: str = Query("service"),
    db: Session = Depends(get_db)
):
    tenant = get_tenant_or_404(db, tenant_id)

    query = db.query(
        NormalizedCostEvent.event_date,
        NormalizedCostEvent.service,
        func.sum(NormalizedCostEvent.cost_usd),
        func.count(NormalizedCostEvent.id)
    ).filter(
        and_(
            NormalizedCostEvent.tenant_id == tenant.id,
            NormalizedCostEvent.event_date >= from_date,
            NormalizedCostEvent.event_date <= to_date,
            NormalizedCostEvent.is_allocated == False
        )
    ).group_by(
        NormalizedCostEvent.event_date,
        NormalizedCostEvent.service
    ).order_by(NormalizedCostEvent.event_date)

    results = query.all()

    items = [
        UnallocatedCostItem(
            date=r[0],
            service=r[1],
            cost_usd=Decimal(str(r[2])) if r[2] else Decimal("0"),
            record_count=int(r[3]) if r[3] else 0
        )
        for r in results
    ]

    total_unallocated = sum(item.cost_usd for item in items)

    return UnallocatedCostResponse(
        tenant_id=tenant_id,
        from_date=from_date,
        to_date=to_date,
        total_unallocated_cost_usd=total_unallocated,
        items=items
    )


# ============================================================================
# ALLOCATION BREAKDOWN
# ============================================================================

@router.get("/tenants/{tenant_id}/allocation-breakdown")
async def get_allocation_breakdown(
    tenant_id: str,
    from_date: date = Query(...),
    to_date: date = Query(...),
    db: Session = Depends(get_db)
):
    """
    Cost breakdown by business entity (team / project / cost_center).
    Sourced from cost_aggregates_by_entity, which is populated by the allocation engine.
    """
    tenant = get_tenant_or_404(db, tenant_id)

    rows = (
        db.query(
            CostAggregateByEntity.business_entity_type,
            CostAggregateByEntity.business_entity_id,
            func.sum(CostAggregateByEntity.cost_usd),
            func.sum(CostAggregateByEntity.record_count),
        )
        .filter(
            and_(
                CostAggregateByEntity.tenant_id == tenant.id,
                CostAggregateByEntity.date >= from_date,
                CostAggregateByEntity.date <= to_date,
            )
        )
        .group_by(
            CostAggregateByEntity.business_entity_type,
            CostAggregateByEntity.business_entity_id,
        )
        .order_by(func.sum(CostAggregateByEntity.cost_usd).desc())
        .all()
    )

    # Group by entity type for the response
    by_type = {}
    allocated_total = Decimal("0")
    for etype, eid, cost, count in rows:
        cost = Decimal(str(cost)) if cost else Decimal("0")
        allocated_total += cost
        if etype not in by_type:
            by_type[etype] = []
        by_type[etype].append({
            "entity_id": eid,
            "cost_usd": float(cost),
            "record_count": int(count) if count else 0,
        })

    # Sort each group descending by cost
    for etype in by_type:
        by_type[etype].sort(key=lambda x: x["cost_usd"], reverse=True)

    # Env breakdown — sourced directly from normalized_cost_events tags
    # because env is an analysis dimension, not an allocation target.
    env_rows = (
        db.query(
            NormalizedCostEvent.tags["env"].astext,
            func.sum(NormalizedCostEvent.cost_usd),
            func.count(NormalizedCostEvent.id),
        )
        .filter(
            and_(
                NormalizedCostEvent.tenant_id == tenant.id,
                NormalizedCostEvent.event_date >= from_date,
                NormalizedCostEvent.event_date <= to_date,
            )
        )
        .group_by(NormalizedCostEvent.tags["env"].astext)
        .order_by(func.sum(NormalizedCostEvent.cost_usd).desc())
        .all()
    )

    by_env = []
    for env_val, env_cost, env_count in env_rows:
        by_env.append({
            "entity_id": env_val or "untagged",
            "cost_usd": float(Decimal(str(env_cost)) if env_cost else Decimal("0")),
            "record_count": int(env_count) if env_count else 0,
        })

    if by_env:
        by_type["env"] = by_env

    # Get total cost from all normalized events (not just allocated)
    total_cost_result = (
        db.query(func.sum(NormalizedCostEvent.cost_usd))
        .filter(
            and_(
                NormalizedCostEvent.tenant_id == tenant.id,
                NormalizedCostEvent.event_date >= from_date,
                NormalizedCostEvent.event_date <= to_date,
            )
        )
        .all()
    )
    total_cost = Decimal(str(total_cost_result[0][0])) if total_cost_result and total_cost_result[0][0] else Decimal("0")

    return {
        "tenant_id": tenant_id,
        "from_date": str(from_date),
        "to_date": str(to_date),
        "total_cost_usd": float(total_cost),
        "total_allocated_cost_usd": float(allocated_total),
        "by_entity_type": by_type,
    }


# ============================================================================
# ANOMALY DETECTION
# ============================================================================

@router.get("/tenants/{tenant_id}/anomalies", response_model=AnomalyResponse)
async def get_anomalies(
    tenant_id: str,
    from_date: date = Query(...),
    to_date: date = Query(...),
    db: Session = Depends(get_db)
):
    tenant = get_tenant_or_404(db, tenant_id)

    results = db.query(Anomaly).filter(
        and_(
            Anomaly.tenant_id == tenant.id,
            Anomaly.date >= from_date,
            Anomaly.date <= to_date
        )
    ).order_by(Anomaly.date).all()

    items = [
        AnomalyItem(
            date=r.date,
            scope_type=r.scope_type,
            scope_id=r.scope_id,
            baseline_cost=Decimal(str(r.baseline_cost)),
            actual_cost=Decimal(str(r.actual_cost)),
            variance_percent=Decimal(str(r.variance_percent)),
            confidence=Decimal(str(r.confidence)) if r.confidence else Decimal("0")
        )
        for r in results
    ]

    return AnomalyResponse(
        tenant_id=tenant_id,
        from_date=from_date,
        to_date=to_date,
        items=items
    )


# ============================================================================
# BUDGETS
# ============================================================================

@router.get("/tenants/{tenant_id}/budgets", response_model=BudgetResponse)
async def get_budgets(
    tenant_id: str,
    include_forecast: bool = Query(True),
    db: Session = Depends(get_db)
):
    """
    Budget forecasting endpoint.

    If include_forecast=true (default): Auto-generates forecasts for all entities based on historical spending.
    Also includes manually created budgets from the budgets table.
    """
    tenant = get_tenant_or_404(db, tenant_id)

    items = []
    today = datetime.now().date()
    current_month_start = today.replace(day=1)

    # 1. Get manually configured budgets
    manual_budgets = db.query(Budget).filter(
        and_(
            Budget.tenant_id == tenant.id,
            Budget.is_active == True
        )
    ).all()

    # Process manual budgets
    for budget in manual_budgets:
        spent = db.query(func.sum(CostAggregateByEntity.cost_usd)).filter(
            and_(
                CostAggregateByEntity.tenant_id == tenant.id,
                CostAggregateByEntity.business_entity_type == budget.business_entity_type,
                CostAggregateByEntity.business_entity_id == budget.business_entity_id,
                CostAggregateByEntity.date >= budget.budget_period_start,
                CostAggregateByEntity.date <= budget.budget_period_end
            )
        ).scalar() or 0

        spent_amount = Decimal(str(spent))
        budget_amount = Decimal(str(budget.budget_amount))
        remaining = budget_amount - spent_amount

        days_elapsed = max(1, (today - budget.budget_period_start).days)
        total_days = (budget.budget_period_end - budget.budget_period_start).days
        days_remaining = max(0, (budget.budget_period_end - today).days)

        # Daily average spend
        daily_avg_spend = spent_amount / days_elapsed if days_elapsed > 0 else Decimal("0")

        # Projected spend at end of period
        projected_end_of_period_spend = daily_avg_spend * total_days

        # Overage (negative = under budget)
        projected_overage = projected_end_of_period_spend - budget_amount

        # Burn rate
        burn_rate = (spent_amount / budget_amount * 100) if budget_amount > 0 else Decimal("0")

        # Alert status based on burn rate thresholds
        if burn_rate >= Decimal("100"):
            alert_status = "critical"
            alert_threshold = Decimal("100")
        elif burn_rate >= Decimal("90"):
            alert_status = "alert"
            alert_threshold = Decimal("90")
        elif burn_rate >= Decimal("75"):
            alert_status = "caution"
            alert_threshold = Decimal("75")
        elif burn_rate >= Decimal("50"):
            alert_status = "caution"
            alert_threshold = Decimal("50")
        else:
            alert_status = "on-track"
            alert_threshold = Decimal("50")

        items.append(BudgetItem(
            entity_type=budget.business_entity_type,
            entity_id=budget.business_entity_id,
            budget_amount=budget_amount,
            spent_amount=spent_amount,
            remaining_amount=remaining,
            burn_rate_percent=burn_rate,
            period_start=budget.budget_period_start,
            period_end=budget.budget_period_end,
            days_elapsed=days_elapsed,
            days_remaining=days_remaining,
            daily_avg_spend=daily_avg_spend,
            projected_end_of_period_spend=projected_end_of_period_spend,
            projected_overage=projected_overage,
            alert_status=alert_status,
            alert_threshold_percent=alert_threshold
        ))

    # 2. Auto-generate forecasts from historical spending (if requested)
    if include_forecast:
        # Get all teams that have spending (from any period in the past)
        # Use this to project current month spending
        teams = (
            db.query(
                CostAggregateByEntity.business_entity_id,
                func.sum(CostAggregateByEntity.cost_usd),
                func.count(CostAggregateByEntity.date.distinct()),
            )
            .filter(
                and_(
                    CostAggregateByEntity.tenant_id == tenant.id,
                    CostAggregateByEntity.business_entity_type == "team"
                )
            )
            .group_by(CostAggregateByEntity.business_entity_id)
            .all()
        )

        for team_id, total_cost_all_time, num_days_with_spending in teams:
            if not team_id or total_cost_all_time is None:
                continue

            total_cost_all_time = Decimal(str(total_cost_all_time))

            # Skip if already has a manual budget (avoid duplicates)
            if any(item.entity_type == "team" and item.entity_id == team_id for item in items):
                continue

            # Calculate forecast based on average daily spend across all historical data
            if num_days_with_spending and num_days_with_spending > 0:
                daily_spend = total_cost_all_time / num_days_with_spending
            else:
                daily_spend = Decimal("0")

            # Project for current month (30 days)
            days_in_month = 30
            projected_monthly_spend = daily_spend * days_in_month
            month_end = (current_month_start.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            days_elapsed_this_month = (today - current_month_start).days + 1

            # Budget = projected spend with 20% buffer
            auto_budget_amount = projected_monthly_spend * Decimal("1.2")

            # Current month spend (get from aggregates where date >= current_month_start)
            current_month_spend = (
                db.query(func.sum(CostAggregateByEntity.cost_usd))
                .filter(
                    and_(
                        CostAggregateByEntity.tenant_id == tenant.id,
                        CostAggregateByEntity.business_entity_type == "team",
                        CostAggregateByEntity.business_entity_id == team_id,
                        CostAggregateByEntity.date >= current_month_start
                    )
                )
                .scalar() or 0
            )
            current_month_spend = Decimal(str(current_month_spend))

            spent_this_month = current_month_spend
            remaining = auto_budget_amount - spent_this_month
            burn_rate = (spent_this_month / auto_budget_amount * 100) if auto_budget_amount > 0 else Decimal("0")

            # Alert status
            if burn_rate >= Decimal("100"):
                alert_status = "critical"
                alert_threshold = Decimal("100")
            elif burn_rate >= Decimal("90"):
                alert_status = "alert"
                alert_threshold = Decimal("90")
            elif burn_rate >= Decimal("75"):
                alert_status = "caution"
                alert_threshold = Decimal("75")
            elif burn_rate >= Decimal("50"):
                alert_status = "caution"
                alert_threshold = Decimal("50")
            else:
                alert_status = "on-track"
                alert_threshold = Decimal("50")

            days_remaining_in_month = (month_end - today).days

            items.append(BudgetItem(
                entity_type="team",
                entity_id=team_id,
                budget_amount=auto_budget_amount,
                spent_amount=spent_this_month,
                remaining_amount=remaining,
                burn_rate_percent=burn_rate,
                period_start=current_month_start,
                period_end=month_end,
                days_elapsed=days_elapsed_this_month,
                days_remaining=max(0, days_remaining_in_month),
                daily_avg_spend=daily_spend,
                projected_end_of_period_spend=projected_monthly_spend,
                projected_overage=projected_monthly_spend - auto_budget_amount,
                alert_status=alert_status,
                alert_threshold_percent=alert_threshold
            ))

    return BudgetResponse(tenant_id=tenant_id, items=items)


# ============================================================================
# RECONCILIATION
# ============================================================================

@router.get("/tenants/{tenant_id}/reconciliation", response_model=ReconciliationResponse)
async def get_reconciliation(
    tenant_id: str,
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Reconciliation view: show data flow from raw → normalized → allocated → unallocated.
    Compares counts and totals at each stage to verify data integrity.
    """
    tenant = get_tenant_or_404(db, tenant_id)

    # Fetch reconciliation audits for this tenant
    query = db.query(ReconciliationAudit).filter(ReconciliationAudit.tenant_id == tenant.id)

    if from_date:
        query = query.filter(ReconciliationAudit.created_at >= from_date)
    if to_date:
        query = query.filter(ReconciliationAudit.created_at <= to_date)

    audits = query.order_by(ReconciliationAudit.created_at.desc()).all()

    items = []
    total_raw_count = 0
    total_raw_cost = Decimal("0")
    total_normalized_count = 0
    total_normalized_cost = Decimal("0")
    total_allocated_count = 0
    total_allocated_cost = Decimal("0")
    total_unallocated_cost = Decimal("0")

    for audit in audits:
        raw_cost = Decimal(str(audit.raw_total_cost)) if audit.raw_total_cost else Decimal("0")
        normalized_cost = Decimal(str(audit.normalized_total_cost)) if audit.normalized_total_cost else Decimal("0")
        allocated_cost = Decimal(str(audit.allocated_total_cost)) if audit.allocated_total_cost else Decimal("0")
        unallocated_cost = Decimal(str(audit.unallocated_total_cost)) if audit.unallocated_total_cost else Decimal("0")

        # Delta: should be 0 (no data loss in normalization)
        raw_to_normalized_delta = normalized_cost - raw_cost

        # Split calculation
        total_allocated_amount = allocated_cost + unallocated_cost
        if total_allocated_amount > 0:
            allocated_pct = (allocated_cost / total_allocated_amount) * 100
            unallocated_pct = (unallocated_cost / total_allocated_amount) * 100
            split_str = f"{allocated_pct:.1f}% allocated, {unallocated_pct:.1f}% unallocated"
        else:
            split_str = "No data"

        items.append(ReconciliationItem(
            batch_id=str(audit.batch_id),
            source_type=audit.source_type,
            raw_record_count=audit.raw_record_count or 0,
            raw_total_cost=raw_cost,
            normalized_record_count=audit.normalized_record_count or 0,
            normalized_total_cost=normalized_cost,
            allocated_count=audit.allocated_count or 0,
            allocated_total_cost=allocated_cost,
            unallocated_total_cost=unallocated_cost,
            raw_to_normalized_delta=raw_to_normalized_delta,
            allocated_to_unallocated_split=split_str,
            created_at=audit.created_at
        ))

        # Accumulate totals
        total_raw_count += audit.raw_record_count or 0
        total_raw_cost += raw_cost
        total_normalized_count += audit.normalized_record_count or 0
        total_normalized_cost += normalized_cost
        total_allocated_count += audit.allocated_count or 0
        total_allocated_cost += allocated_cost
        total_unallocated_cost += unallocated_cost

    # Summary statistics
    overall_delta = total_normalized_cost - total_raw_cost
    if (total_allocated_cost + total_unallocated_cost) > 0:
        overall_allocated_pct = (total_allocated_cost / (total_allocated_cost + total_unallocated_cost)) * 100
    else:
        overall_allocated_pct = 0

    summary = {
        "total_raw_records": total_raw_count,
        "total_raw_cost_usd": float(total_raw_cost),
        "total_normalized_records": total_normalized_count,
        "total_normalized_cost_usd": float(total_normalized_cost),
        "raw_to_normalized_delta_usd": float(overall_delta),
        "total_allocated_records": total_allocated_count,
        "total_allocated_cost_usd": float(total_allocated_cost),
        "total_unallocated_cost_usd": float(total_unallocated_cost),
        "overall_allocation_rate_percent": float(overall_allocated_pct),
        "audit_batches_count": len(audits)
    }

    return ReconciliationResponse(
        tenant_id=tenant_id,
        summary=summary,
        audits=items
    )


# ============================================================================
# AI UNIT ECONOMICS
# ============================================================================

@router.get("/tenants/{tenant_id}/ai-unit-economics", response_model=AIUnitEconomicsResponse)
async def get_ai_unit_economics(
    tenant_id: str,
    from_date: date = Query(...),
    to_date: date = Query(...),
    project_id: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    tenant = get_tenant_or_404(db, tenant_id)

    query = db.query(
        func.cast(func.jsonb_extract_text(NormalizedCostEvent.tags, 'project_id'), type_=type(None)),
        func.sum(NormalizedCostEvent.cost_usd),
        func.sum(NormalizedCostEvent.quantity),
        func.count(NormalizedCostEvent.id)
    ).filter(
        and_(
            NormalizedCostEvent.tenant_id == tenant.id,
            NormalizedCostEvent.event_date >= from_date,
            NormalizedCostEvent.event_date <= to_date,
            NormalizedCostEvent.provider == "ai"
        )
    )

    if project_id:
        query = query.filter(NormalizedCostEvent.tags["project_id"].astext == project_id)

    results = query.group_by("project_id").all()

    items = []
    for pid, total_cost, total_tokens, count in results:
        if total_cost and total_tokens:
            cost_per_1k_tokens = (Decimal(str(total_cost)) / Decimal(str(total_tokens))) * 1000
        else:
            cost_per_1k_tokens = Decimal("0")

        items.append(AIUnitEconomicsItem(
            project_id=pid or "unknown",
            total_cost_usd=Decimal(str(total_cost)) if total_cost else Decimal("0"),
            total_tokens=Decimal(str(total_tokens)) if total_tokens else Decimal("0"),
            cost_per_1k_tokens=cost_per_1k_tokens,
            total_requests=int(count) if count else 0
        ))

    return AIUnitEconomicsResponse(
        tenant_id=tenant_id,
        from_date=from_date,
        to_date=to_date,
        items=items
    )


# ============================================================================
# SCHEDULED JOBS (can be triggered manually or by external schedulers)
# ============================================================================

@router.post("/jobs/anomalies/daily")
async def trigger_daily_anomaly_detection(target_date: Optional[date] = Query(None)):
    """
    Manually trigger daily anomaly detection for all tenants.
    Normally runs automatically at 2am UTC via scheduler.

    Query params:
    - target_date: ISO date to detect anomalies for (default: yesterday)
    """
    try:
        from src.database.connection import DatabaseConnection
        from src.anomaly.detector import AnomalyDetector

        db = DatabaseConnection.get_session()
        if target_date is None:
            target_date = datetime.utcnow().date() - timedelta(days=1)

        try:
            tenants = db.query(Tenant).all()
            total_anomalies = 0
            failed = []

            for tenant in tenants:
                try:
                    detector = AnomalyDetector(db)
                    result = detector.detect_for_tenant(tenant.id, target_date=target_date, window="daily")
                    total_anomalies += result["anomalies_detected"]
                except Exception as e:
                    logger.error(f"Tenant {tenant.name} failed: {e}")
                    failed.append(tenant.name)

            return {
                "status": "success",
                "job": "daily",
                "target_date": str(target_date),
                "total_anomalies": total_anomalies,
                "tenants_processed": len(tenants),
                "failed_tenants": failed
            }
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Daily anomaly detection failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/jobs/anomalies/weekly")
async def trigger_weekly_anomaly_detection():
    """
    Manually trigger weekly anomaly detection for all tenants.
    Normally runs automatically on Mondays at 2am UTC via scheduler.
    """
    try:
        result = detect_anomalies_weekly()
        return {"status": "success", "result": result}
    except Exception as e:
        logger.error(f"Weekly anomaly detection failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/jobs/anomalies/monthly")
async def trigger_monthly_anomaly_detection():
    """
    Manually trigger monthly anomaly detection for all tenants.
    Normally runs automatically on the 1st of each month at 2am UTC via scheduler.
    """
    try:
        result = detect_anomalies_monthly()
        return {"status": "success", "result": result}
    except Exception as e:
        logger.error(f"Monthly anomaly detection failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
