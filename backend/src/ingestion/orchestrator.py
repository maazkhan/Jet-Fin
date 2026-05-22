import logging
from io import BytesIO
from uuid import uuid4
from fastapi import UploadFile
from sqlalchemy.orm import Session
from decimal import Decimal
import hashlib
import json
from datetime import datetime, date

from src.models import CostSourceType, CostStatus
from src.database.models import RawCostEvent, NormalizedCostEvent, Tenant, CostAggregateDaily, ReconciliationAudit
from src.ingestion.parser import ParserFactory
from src.ingestion.deduplicator import Deduplicator
from src.utils.hash import calculate_source_hash
from src.allocation.engine import AllocationEngine
from sqlalchemy import func

logger = logging.getLogger(__name__)

# Late-arriving data threshold: flag events older than this many days
LATE_ARRIVING_THRESHOLD_DAYS = 7


def serialize_for_json(obj):
    """Convert non-JSON-serializable objects to serializable types."""
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, (date, datetime)):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: serialize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [serialize_for_json(item) for item in obj]
    return obj


class IngestOrchestrator:
    def __init__(self, db: Session):
        self.db = db
        self.deduplicator = Deduplicator()

    async def ingest_file(self, file: UploadFile, tenant_id, source_type: CostSourceType):
        batch_id = uuid4()

        try:
            content = await file.read()
            file_bytes = BytesIO(content)

            parser = ParserFactory.get_parser(source_type)
            events, errors = parser.parse(file_bytes)

            logger.info(f"Parsed {len(events)} events with {len(errors)} errors")

            if not events:
                return {
                    "batch_id": batch_id,
                    "records_ingested": 0,
                    "records_with_errors": len(errors),
                    "errors": errors[:100],
                    "tenants_processed": []
                }

            # Group events by tenant_id
            events_by_tenant = {}
            for event in events:
                tid = event.tenant_id or "unknown"
                if tid not in events_by_tenant:
                    events_by_tenant[tid] = []
                events_by_tenant[tid].append(event)

            logger.info(f"File contains {len(events_by_tenant)} distinct tenants: {list(events_by_tenant.keys())}")

            # Deduplicate in-memory
            deduped_events, dedup_errors = self.deduplicator.deduplicate(events, source_type)
            errors.extend(dedup_errors)

            # Regroup deduped events by tenant
            deduped_by_tenant = {}
            for event in deduped_events:
                tid = event.tenant_id or "unknown"
                if tid not in deduped_by_tenant:
                    deduped_by_tenant[tid] = []
                deduped_by_tenant[tid].append(event)

            # Process each tenant's events
            inserted_count = 0
            tenants_processed = []

            for tenant_name, tenant_events in deduped_by_tenant.items():
                try:
                    logger.info(f"Processing {len(tenant_events)} events for tenant {tenant_name}")

                    # Ensure tenant exists
                    tenant = self.db.query(Tenant).filter(Tenant.name == tenant_name).first()
                    if not tenant:
                        tenant = Tenant(name=tenant_name)
                        self.db.add(tenant)
                        self.db.flush()
                        logger.info(f"Created new tenant: {tenant_name}")

                    tenants_processed.append(tenant_name)

                    # Batch cross-tenant dedup: fetch all hashes that already exist in DB
                    all_hashes = [calculate_source_hash(e, source_type) for e in tenant_events]
                    existing_hashes = set(
                        row[0] for row in self.db.query(RawCostEvent.source_hash).filter(
                            RawCostEvent.tenant_id == tenant.id,
                            RawCostEvent.source_hash.in_(all_hashes)
                        ).all()
                    )
                    logger.info(f"Batch dedup: {len(existing_hashes)} already exist out of {len(all_hashes)} in tenant {tenant_name}")

                    # Collect all event dates for aggregate refresh
                    event_dates = set()

                    # Insert events for this tenant
                    for event in tenant_events:
                        try:
                            raw_hash = calculate_source_hash(event, source_type)

                            # Cross-batch dedup using pre-fetched set (O(1) lookup vs O(N) queries)
                            if raw_hash in existing_hashes:
                                logger.debug(f"Duplicate record found: {raw_hash}")
                                continue

                            # Late-arriving data detection
                            today = date.today()
                            lag_days = (today - event.event_date).days
                            is_late = lag_days > LATE_ARRIVING_THRESHOLD_DAYS


                            # Convert event to dict and serialize all non-JSON-serializable types
                            event_dict = serialize_for_json(event.dict())

                            # Insert raw event
                            raw_event = RawCostEvent(
                                tenant_id=tenant.id,
                                source_type=source_type.value,
                                source_hash=raw_hash,
                                raw_data=event_dict,
                                batch_id=batch_id
                            )
                            self.db.add(raw_event)
                            self.db.flush()

                            # Insert normalized event with late-arriving metadata
                            normalized_event = NormalizedCostEvent(
                                tenant_id=tenant.id,
                                raw_event_id=raw_event.id,
                                resource_id=event.resource_id,
                                resource_type=event.resource_type,
                                service=event.service,
                                operation=event.operation,
                                region=event.region,
                                cost_usd=event.cost_usd,
                                quantity=event.quantity,
                                unit_type=event.unit_type,
                                provider=event.provider,
                                event_date=event.event_date,
                                event_hour=event.event_hour,
                                tags=event.tags,
                                is_allocated=False,
                                status=CostStatus.PENDING.value,
                                is_late_arriving=is_late,
                                ingestion_lag_days=lag_days
                            )
                            self.db.add(normalized_event)
                            event_dates.add(event.event_date)
                            inserted_count += 1

                        except Exception as e:
                            logger.error(f"Error inserting event for tenant {tenant_name}: {e}")
                            # Do NOT rollback here — skip this event and continue with the rest
                            errors.append(f"Tenant {tenant_name} - Database insert error: {str(e)}")

                    # Commit, then allocate, then refresh aggregates, then record reconciliation
                    self.db.commit()
                    try:
                        engine = AllocationEngine(self.db)
                        alloc_result = engine.run_for_tenant(tenant.id)
                        logger.info(f"Allocation for tenant {tenant_name}: {alloc_result}")
                    except Exception as ae:
                        logger.warning(f"Allocation failed for tenant {tenant_name} (non-blocking): {ae}")
                    self._refresh_aggregates(tenant.id, event_dates)
                    self._record_reconciliation_audit(tenant.id, batch_id, source_type)

                except Exception as e:
                    logger.error(f"Error processing tenant {tenant_name}: {e}")
                    self.db.rollback()
                    errors.append(f"Tenant {tenant_name} - Processing error: {str(e)}")

            logger.info(f"Inserted {inserted_count} normalized events across {len(tenants_processed)} tenants")

            return {
                "batch_id": batch_id,
                "records_ingested": inserted_count,
                "records_with_errors": len(errors),
                "errors": errors[:100],  # Limit error list
                "tenants_processed": tenants_processed
            }

        except Exception as e:
            logger.error(f"Ingestion failed: {e}")
            self.db.rollback()
            raise

    def _refresh_aggregates(self, tenant_id, event_dates: set):
        """Refresh daily aggregates for specific dates in the batch (not just today).

        This ensures backfilled or late-arriving historical data correctly updates
        the pre-computed aggregate tables.
        """
        try:
            # Refresh aggregates for each date in the batch
            for target_date in event_dates:
                # Delete existing aggregates for this date
                self.db.query(CostAggregateDaily).filter(
                    (CostAggregateDaily.tenant_id == tenant_id) &
                    (CostAggregateDaily.date == target_date)
                ).delete()

                # Recompute aggregates from normalized events for this date
                from sqlalchemy import case
                aggregates = self.db.query(
                    NormalizedCostEvent.service,
                    NormalizedCostEvent.region,
                    func.sum(NormalizedCostEvent.cost_usd),
                    func.sum(case((NormalizedCostEvent.is_allocated.is_(True), NormalizedCostEvent.cost_usd), else_=0)),
                    func.sum(case((NormalizedCostEvent.is_allocated.is_(False), NormalizedCostEvent.cost_usd), else_=0)),
                    func.count(NormalizedCostEvent.id)
                ).filter(
                    (NormalizedCostEvent.tenant_id == tenant_id) &
                    (NormalizedCostEvent.event_date == target_date)
                ).group_by(
                    NormalizedCostEvent.service,
                    NormalizedCostEvent.region
                ).all()

                # Insert computed aggregates for this date
                for service, region, total_cost, allocated_cost, unallocated_cost, count in aggregates:
                    agg = CostAggregateDaily(
                        tenant_id=tenant_id,
                        date=target_date,
                        service=service,
                        region=region,
                        cost_usd=total_cost or 0,
                        allocated_cost_usd=allocated_cost or 0,
                        unallocated_cost_usd=unallocated_cost or 0,
                        record_count=count or 0
                    )
                    self.db.add(agg)

            self.db.commit()
            logger.info(f"Refreshed aggregates for tenant {tenant_id} across {len(event_dates)} dates")
        except Exception as e:
            logger.warning(f"Failed to refresh aggregates (non-blocking): {e}")
            self.db.rollback()

    def _record_reconciliation_audit(self, tenant_id, batch_id, source_type: CostSourceType):
        """Record data flow statistics for reconciliation: raw → normalized → allocated."""
        try:
            # Raw events for this batch - sum from raw_data JSONB
            from sqlalchemy import cast, Numeric
            raw_stats = (
                self.db.query(
                    func.count(RawCostEvent.id),
                    func.sum(cast(RawCostEvent.raw_data['cost_usd'].astext, Numeric))
                )
                .filter(
                    RawCostEvent.tenant_id == tenant_id,
                    RawCostEvent.batch_id == batch_id
                )
                .all()
            )
            raw_count = raw_stats[0][0] if raw_stats else 0
            raw_cost = Decimal(str(raw_stats[0][1])) if raw_stats and raw_stats[0][1] else Decimal("0")

            # Normalized events for this batch
            normalized_stats = (
                self.db.query(
                    func.count(NormalizedCostEvent.id),
                    func.sum(NormalizedCostEvent.cost_usd)
                )
                .filter(
                    NormalizedCostEvent.tenant_id == tenant_id,
                    NormalizedCostEvent.raw_event_id.in_(
                        self.db.query(RawCostEvent.id).filter(
                            RawCostEvent.tenant_id == tenant_id,
                            RawCostEvent.batch_id == batch_id
                        )
                    )
                )
                .all()
            )
            normalized_count = normalized_stats[0][0] if normalized_stats else 0
            normalized_cost = Decimal(str(normalized_stats[0][1])) if normalized_stats and normalized_stats[0][1] else Decimal("0")

            # Allocated vs unallocated split
            allocated_stats = (
                self.db.query(
                    func.count(NormalizedCostEvent.id),
                    func.sum(NormalizedCostEvent.cost_usd)
                )
                .filter(
                    NormalizedCostEvent.tenant_id == tenant_id,
                    NormalizedCostEvent.is_allocated == True,
                    NormalizedCostEvent.raw_event_id.in_(
                        self.db.query(RawCostEvent.id).filter(
                            RawCostEvent.tenant_id == tenant_id,
                            RawCostEvent.batch_id == batch_id
                        )
                    )
                )
                .all()
            )
            allocated_count = allocated_stats[0][0] if allocated_stats else 0
            allocated_cost = Decimal(str(allocated_stats[0][1])) if allocated_stats and allocated_stats[0][1] else Decimal("0")

            unallocated_cost = normalized_cost - allocated_cost

            # Record audit
            audit = ReconciliationAudit(
                tenant_id=tenant_id,
                batch_id=batch_id,
                source_type=source_type.value,
                raw_record_count=raw_count,
                raw_total_cost=raw_cost,
                normalized_record_count=normalized_count,
                normalized_total_cost=normalized_cost,
                allocated_count=allocated_count,
                allocated_total_cost=allocated_cost,
                unallocated_total_cost=unallocated_cost
            )
            self.db.add(audit)
            self.db.commit()
            logger.info(f"Reconciliation audit recorded: {raw_count} raw → {normalized_count} normalized → {allocated_count} allocated")
        except Exception as e:
            logger.warning(f"Failed to record reconciliation audit (non-blocking): {e}")
            self.db.rollback()
