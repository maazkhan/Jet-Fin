import hashlib
from src.models import CostSourceType, NormalizedCostEvent


def calculate_source_hash(event: NormalizedCostEvent, source_type: CostSourceType) -> str:
    """Calculate deterministic hash for idempotency.

    Key fields: source_type | resource_id | event_date | event_hour | cost_usd | service | region | operation
    Optional fields use empty-string sentinel so NULL != missing-entirely.
    """
    key_fields = (
        source_type.value,
        event.resource_id,
        event.event_date.isoformat(),
        event.event_hour.isoformat(),  # Hourly AWS CUR granularity
        str(event.cost_usd),
        event.service,
        event.region or "",  # Regional billing dimension
        event.operation or "",  # EC2 operation type (RunInstances, DataTransfer, etc.)
    )
    key_str = "|".join(key_fields)
    return hashlib.sha256(key_str.encode()).hexdigest()
