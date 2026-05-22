from fastapi import APIRouter, Depends, File, UploadFile, Query, HTTPException, status
from sqlalchemy.orm import Session
from io import BytesIO
import logging

from src.database.connection import get_db
from src.database.models import Tenant, AllocationRule
from src.models import CostSourceType, HealthResponse
from src.ingestion.orchestrator import IngestOrchestrator
from src.ingestion.validator import FileValidator
from src.allocation.engine import AllocationEngine, reload_rules

router = APIRouter(prefix="/api/v1", tags=["finops-ingestion"])
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
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        return HealthResponse(status="healthy", environment="production", database="postgresql")
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthResponse(status="unhealthy", environment="production", database="error")


# ============================================================================
# FILE INGESTION
# ============================================================================

@router.post("/ingest")
async def ingest_file(
    file: UploadFile = File(...),
    source_type: str = Query(...),
    db: Session = Depends(get_db)
):
    """Ingest cost data file. Tenant ID is extracted from the data itself."""
    try:
        source_type_enum = CostSourceType(source_type.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid source_type: {source_type}")

    try:
        # Validate file structure matches declared source type
        content = await file.read()
        file_bytes = BytesIO(content)

        is_valid, error_message = FileValidator.validate_file(file_bytes, source_type_enum)
        if not is_valid:
            raise HTTPException(
                status_code=400,
                detail=f"File validation failed: {error_message}. Expected {source_type} format."
            )

        # Reset file pointer for orchestrator
        file_bytes.seek(0)
        file.file = file_bytes

        orchestrator = IngestOrchestrator(db)
        result = await orchestrator.ingest_file(
            file=file,
            tenant_id=None,  # Let orchestrator extract from data
            source_type=source_type_enum
        )
        return {
            "status": "success",
            "batch_id": str(result.get("batch_id")),
            "records_ingested": result.get("records_ingested", 0),
            "records_with_errors": result.get("records_with_errors", 0),
            "errors": result.get("errors", []),
            "tenant_id": result.get("tenant_id")
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")


# ============================================================================
# ALLOCATION RULES & CONTROL
# ============================================================================

@router.post("/allocations/reload-rules")
async def reload_allocation_rules():
    """Hot-reload allocation_rules.yaml without restarting the server."""
    count = reload_rules()
    return {"status": "reloaded", "rules_loaded": count}


@router.post("/tenants/{tenant_id}/allocations/run")
async def run_allocation(
    tenant_id: str,
    db: Session = Depends(get_db)
):
    """
    Re-run the allocation engine for all pending/unallocated events of a tenant.
    Useful after editing allocation rules or to reprocess historical data.
    """
    tenant = get_tenant_or_404(db, tenant_id)
    try:
        engine = AllocationEngine(db)
        result = engine.run_for_tenant(tenant.id)
        return {
            "tenant_id": tenant_id,
            "status": "completed",
            **result
        }
    except Exception as e:
        logger.error(f"Allocation run failed for tenant {tenant_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Allocation failed: {str(e)}")


@router.get("/tenants/{tenant_id}/allocation-rules")
async def list_allocation_rules(
    tenant_id: str,
    db: Session = Depends(get_db)
):
    """List all allocation rules for a tenant, ordered by priority."""
    tenant = get_tenant_or_404(db, tenant_id)
    rules = (
        db.query(AllocationRule)
        .filter(AllocationRule.tenant_id == tenant.id)
        .order_by(AllocationRule.priority)
        .all()
    )
    return {
        "tenant_id": tenant_id,
        "rules": [
            {
                "id": str(r.id),
                "name": r.name,
                "priority": r.priority,
                "conditions": r.conditions,
                "action": r.action,
                "action_params": r.action_params,
                "is_active": r.is_active,
            }
            for r in rules
        ],
        "count": len(rules),
    }


@router.post("/tenants/{tenant_id}/allocation-rules")
async def create_allocation_rule(
    tenant_id: str,
    rule: dict,
    db: Session = Depends(get_db)
):
    """Create a new allocation rule for a tenant."""
    tenant = get_tenant_or_404(db, tenant_id)

    required = {"name", "action"}
    missing = required - set(rule.keys())
    if missing:
        raise HTTPException(status_code=422, detail=f"Missing required fields: {missing}")

    new_rule = AllocationRule(
        tenant_id=tenant.id,
        name=rule["name"],
        priority=rule.get("priority", 999),
        conditions=rule.get("conditions", {}),
        action=rule["action"],
        action_params=rule.get("action_params", {}),
        is_active=rule.get("is_active", True),
    )
    db.add(new_rule)
    try:
        db.commit()
        db.refresh(new_rule)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"Rule creation failed: {str(e)}")

    return {
        "id": str(new_rule.id),
        "tenant_id": tenant_id,
        "name": new_rule.name,
        "priority": new_rule.priority,
        "conditions": new_rule.conditions,
        "action": new_rule.action,
        "action_params": new_rule.action_params,
        "is_active": new_rule.is_active,
    }
