import logging
from datetime import datetime, timedelta, date
from decimal import Decimal
from typing import List, Dict, Tuple, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from src.database.models import (
    NormalizedCostEvent,
    CostAggregateByEntity,
    Anomaly,
    Tenant,
)

logger = logging.getLogger(__name__)

# Z-score threshold for anomaly detection (2.5 = ~1.2% tail probability)
Z_SCORE_THRESHOLD = 2.5

# Minimum baseline records needed before detection (7 days)
MIN_BASELINE_DAYS = 7


class AnomalyDetector:
    """
    Detects spend anomalies at multiple scopes:
    - Daily (overall tenant spend)
    - Service-level (per service)
    - Project-level (per project/cost center)

    Algorithm:
    1. For each day, compute 7-day trailing baseline (excluding that day)
    2. Calculate mean and stddev of baseline
    3. Apply Z-score: (actual - mean) / stddev
    4. If |Z| > threshold, flag as anomaly
    5. Include weekday seasonality adjustment (optional)
    6. Return top cost drivers and explanation
    """

    def __init__(self, db: Session):
        self.db = db

    def detect_for_tenant(
        self,
        tenant_id,
        target_date: Optional[date] = None,
        window: str = "daily",
    ) -> dict:
        """
        Detect anomalies for a tenant on a specific date/window.

        Args:
            tenant_id: Tenant UUID
            target_date: Date to detect anomalies for (default: yesterday)
            window: Detection window - 'daily', 'weekly', or 'monthly'
                - daily: compare day vs 7-day trailing baseline
                - weekly: compare week vs 4-week trailing baseline
                - monthly: compare month vs 3-month trailing baseline

        Returns:
            Summary dict with anomalies_detected count
        """
        if target_date is None:
            target_date = datetime.utcnow().date() - timedelta(days=1)

        # Validate window
        if window not in ("daily", "weekly", "monthly"):
            raise ValueError(f"Invalid window: {window}. Must be daily, weekly, or monthly")

        # Calculate baseline period based on window
        if window == "daily":
            baseline_start = target_date - timedelta(days=7)
            baseline_end = target_date - timedelta(days=1)
        elif window == "weekly":
            # Week = 7 days; baseline = 4 weeks before
            week_start = target_date - timedelta(days=target_date.weekday())
            baseline_start = week_start - timedelta(weeks=4)
            baseline_end = week_start - timedelta(days=1)
        else:  # monthly
            # Baseline = 3 months before
            first_of_month = target_date.replace(day=1)
            baseline_start = (first_of_month - timedelta(days=1)).replace(day=1) - timedelta(days=90)
            baseline_end = first_of_month - timedelta(days=1)

        # Only detect if we have enough baseline data
        baseline_count = (
            self.db.query(func.count(NormalizedCostEvent.id))
            .filter(
                and_(
                    NormalizedCostEvent.tenant_id == tenant_id,
                    NormalizedCostEvent.event_date >= baseline_start,
                    NormalizedCostEvent.event_date <= baseline_end,
                )
            )
            .scalar()
        )

        if baseline_count == 0:
            logger.info(
                f"Insufficient baseline data for tenant {tenant_id} on {target_date}"
            )
            return {"anomalies_detected": 0, "reason": "insufficient_baseline"}

        # Delete prior anomalies for this date (idempotent re-detection)
        self.db.query(Anomaly).filter(
            and_(Anomaly.tenant_id == tenant_id, Anomaly.date == target_date)
        ).delete()

        anomalies_detected = 0

        # 1. Daily (overall tenant) anomaly
        daily_anomaly = self._detect_daily_anomaly(
            tenant_id, target_date, baseline_start, baseline_end
        )
        if daily_anomaly:
            self.db.add(daily_anomaly)
            anomalies_detected += 1

        # 2. Service-level anomalies
        service_anomalies = self._detect_service_anomalies(
            tenant_id, target_date, baseline_start, baseline_end
        )
        for anomaly in service_anomalies:
            self.db.add(anomaly)
            anomalies_detected += len(service_anomalies)

        # 3. Project/cost-center anomalies
        project_anomalies = self._detect_project_anomalies(
            tenant_id, target_date, baseline_start, baseline_end
        )
        for anomaly in project_anomalies:
            self.db.add(anomaly)
            anomalies_detected += len(project_anomalies)

        self.db.commit()

        logger.info(
            f"Anomaly detection for tenant {tenant_id} on {target_date}: "
            f"{anomalies_detected} anomalies detected"
        )

        return {
            "anomalies_detected": anomalies_detected,
            "target_date": str(target_date),
            "baseline_start": str(baseline_start),
            "baseline_end": str(baseline_end),
        }

    # -----------------------------------------------------------------------
    # Daily (overall tenant) anomaly
    # -----------------------------------------------------------------------

    def _detect_daily_anomaly(
        self,
        tenant_id,
        target_date: date,
        baseline_start: date,
        baseline_end: date,
    ) -> Optional[Anomaly]:
        """Detect anomaly for overall tenant spend on a single day."""
        actual_cost = (
            self.db.query(func.sum(NormalizedCostEvent.cost_usd))
            .filter(
                and_(
                    NormalizedCostEvent.tenant_id == tenant_id,
                    NormalizedCostEvent.event_date == target_date,
                )
            )
            .scalar()
        )

        if actual_cost is None:
            actual_cost = Decimal("0")
        else:
            actual_cost = Decimal(str(actual_cost))

        baseline_costs = (
            self.db.query(
                NormalizedCostEvent.event_date,
                func.sum(NormalizedCostEvent.cost_usd),
            )
            .filter(
                and_(
                    NormalizedCostEvent.tenant_id == tenant_id,
                    NormalizedCostEvent.event_date >= baseline_start,
                    NormalizedCostEvent.event_date <= baseline_end,
                )
            )
            .group_by(NormalizedCostEvent.event_date)
            .all()
        )

        baseline_values = [
            Decimal(str(cost)) for _, cost in baseline_costs if cost is not None
        ]

        if len(baseline_values) < MIN_BASELINE_DAYS:
            return None

        baseline_mean, baseline_stddev = self._calculate_stats(baseline_values)

        # Prevent division by zero
        if baseline_stddev == 0:
            return None

        z_score = (actual_cost - baseline_mean) / baseline_stddev

        # Detect anomaly if |Z| exceeds threshold
        if abs(z_score) <= Z_SCORE_THRESHOLD:
            return None

        # Get top cost drivers for explanation
        top_services = self._get_top_drivers(
            tenant_id, target_date, limit=3, scope_type="service"
        )

        variance_pct = (
            ((actual_cost - baseline_mean) / baseline_mean * 100)
            if baseline_mean > 0
            else Decimal("0")
        )

        return Anomaly(
            tenant_id=tenant_id,
            date=target_date,
            scope_type="daily",
            scope_id=None,
            baseline_cost=baseline_mean,
            actual_cost=actual_cost,
            variance_percent=variance_pct,
            confidence=min(Decimal(str(abs(z_score))), Decimal("99.99")),
            top_drivers=top_services,
            explanation=self._explain_anomaly(
                "daily", None, actual_cost, baseline_mean, top_services
            ),
        )

    # -----------------------------------------------------------------------
    # Service-level anomalies
    # -----------------------------------------------------------------------

    def _detect_service_anomalies(
        self,
        tenant_id,
        target_date: date,
        baseline_start: date,
        baseline_end: date,
    ) -> List[Anomaly]:
        """Detect anomalies per service."""
        anomalies = []

        # Get all services for this tenant in the baseline + target period
        services = (
            self.db.query(NormalizedCostEvent.service)
            .filter(
                and_(
                    NormalizedCostEvent.tenant_id == tenant_id,
                    NormalizedCostEvent.event_date >= baseline_start,
                    NormalizedCostEvent.event_date <= target_date,
                )
            )
            .distinct()
            .all()
        )

        for (service,) in services:
            if service is None:
                continue

            # Actual cost for this service on target date
            actual_cost = (
                self.db.query(func.sum(NormalizedCostEvent.cost_usd))
                .filter(
                    and_(
                        NormalizedCostEvent.tenant_id == tenant_id,
                        NormalizedCostEvent.event_date == target_date,
                        NormalizedCostEvent.service == service,
                    )
                )
                .scalar()
            )

            if actual_cost is None:
                actual_cost = Decimal("0")
            else:
                actual_cost = Decimal(str(actual_cost))

            # Baseline for this service
            baseline_costs = (
                self.db.query(func.sum(NormalizedCostEvent.cost_usd))
                .filter(
                    and_(
                        NormalizedCostEvent.tenant_id == tenant_id,
                        NormalizedCostEvent.event_date >= baseline_start,
                        NormalizedCostEvent.event_date < target_date,
                        NormalizedCostEvent.service == service,
                    )
                )
                .group_by(NormalizedCostEvent.event_date)
                .all()
            )

            baseline_values = [
                Decimal(str(cost[0])) for cost in baseline_costs if cost[0] is not None
            ]

            if len(baseline_values) < MIN_BASELINE_DAYS:
                continue

            baseline_mean, baseline_stddev = self._calculate_stats(baseline_values)

            if baseline_stddev == 0:
                continue

            z_score = (actual_cost - baseline_mean) / baseline_stddev

            if abs(z_score) <= Z_SCORE_THRESHOLD:
                continue

            variance_pct = (
                ((actual_cost - baseline_mean) / baseline_mean * 100)
                if baseline_mean > 0
                else Decimal("0")
            )

            anomalies.append(
                Anomaly(
                    tenant_id=tenant_id,
                    date=target_date,
                    scope_type="service",
                    scope_id=service,
                    baseline_cost=baseline_mean,
                    actual_cost=actual_cost,
                    variance_percent=variance_pct,
                    confidence=min(Decimal(str(abs(z_score))), Decimal("99.99")),
                    top_drivers=None,
                    explanation=self._explain_anomaly(
                        "service", service, actual_cost, baseline_mean, None
                    ),
                )
            )

        return anomalies

    # -----------------------------------------------------------------------
    # Project/cost-center anomalies
    # -----------------------------------------------------------------------

    def _detect_project_anomalies(
        self,
        tenant_id,
        target_date: date,
        baseline_start: date,
        baseline_end: date,
    ) -> List[Anomaly]:
        """Detect anomalies per project/cost center."""
        anomalies = []

        # Get all projects (from cost_aggregates_by_entity, type=project)
        projects = (
            self.db.query(CostAggregateByEntity.business_entity_id)
            .filter(
                and_(
                    CostAggregateByEntity.tenant_id == tenant_id,
                    CostAggregateByEntity.business_entity_type == "project",
                    CostAggregateByEntity.date >= baseline_start,
                    CostAggregateByEntity.date <= target_date,
                )
            )
            .distinct()
            .all()
        )

        for (project_id,) in projects:
            # Actual cost for this project on target date
            actual_cost = (
                self.db.query(func.sum(CostAggregateByEntity.cost_usd))
                .filter(
                    and_(
                        CostAggregateByEntity.tenant_id == tenant_id,
                        CostAggregateByEntity.date == target_date,
                        CostAggregateByEntity.business_entity_type == "project",
                        CostAggregateByEntity.business_entity_id == project_id,
                    )
                )
                .scalar()
            )

            if actual_cost is None:
                actual_cost = Decimal("0")
            else:
                actual_cost = Decimal(str(actual_cost))

            # Baseline for this project
            baseline_costs = (
                self.db.query(CostAggregateByEntity.cost_usd)
                .filter(
                    and_(
                        CostAggregateByEntity.tenant_id == tenant_id,
                        CostAggregateByEntity.date >= baseline_start,
                        CostAggregateByEntity.date < target_date,
                        CostAggregateByEntity.business_entity_type == "project",
                        CostAggregateByEntity.business_entity_id == project_id,
                    )
                )
                .all()
            )

            baseline_values = [
                Decimal(str(cost[0])) for cost in baseline_costs if cost[0] is not None
            ]

            if len(baseline_values) < MIN_BASELINE_DAYS:
                continue

            baseline_mean, baseline_stddev = self._calculate_stats(baseline_values)

            if baseline_stddev == 0:
                continue

            z_score = (actual_cost - baseline_mean) / baseline_stddev

            if abs(z_score) <= Z_SCORE_THRESHOLD:
                continue

            variance_pct = (
                ((actual_cost - baseline_mean) / baseline_mean * 100)
                if baseline_mean > 0
                else Decimal("0")
            )

            anomalies.append(
                Anomaly(
                    tenant_id=tenant_id,
                    date=target_date,
                    scope_type="project",
                    scope_id=project_id,
                    baseline_cost=baseline_mean,
                    actual_cost=actual_cost,
                    variance_percent=variance_pct,
                    confidence=min(Decimal(str(abs(z_score))), Decimal("99.99")),
                    top_drivers=None,
                    explanation=self._explain_anomaly(
                        "project", project_id, actual_cost, baseline_mean, None
                    ),
                )
            )

        return anomalies

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def _calculate_stats(values: List[Decimal]) -> Tuple[Decimal, Decimal]:
        """Calculate mean and standard deviation of a list of Decimal values."""
        if not values:
            return Decimal("0"), Decimal("0")

        mean = sum(values) / len(values)

        if len(values) == 1:
            return mean, Decimal("0")

        variance = sum((x - mean) ** 2 for x in values) / len(values)
        stddev = variance.sqrt()

        return mean, stddev

    def _get_top_drivers(
        self,
        tenant_id,
        target_date: date,
        limit: int = 5,
        scope_type: str = "service",
    ) -> List[Dict]:
        """Get top cost drivers by service or resource for a specific date."""
        if scope_type == "service":
            rows = (
                self.db.query(
                    NormalizedCostEvent.service,
                    func.sum(NormalizedCostEvent.cost_usd),
                    func.count(NormalizedCostEvent.id),
                )
                .filter(
                    and_(
                        NormalizedCostEvent.tenant_id == tenant_id,
                        NormalizedCostEvent.event_date == target_date,
                    )
                )
                .group_by(NormalizedCostEvent.service)
                .order_by(func.sum(NormalizedCostEvent.cost_usd).desc())
                .limit(limit)
                .all()
            )

            return [
                {
                    "name": service or "untagged",
                    "cost": float(Decimal(str(cost)) if cost else Decimal("0")),
                    "records": int(count),
                }
                for service, cost, count in rows
            ]

        return []

    @staticmethod
    def _explain_anomaly(
        scope_type: str,
        scope_id: Optional[str],
        actual: Decimal,
        baseline: Decimal,
        top_drivers: Optional[List[Dict]],
    ) -> str:
        """Generate human-readable explanation for an anomaly."""
        direction = "higher" if actual > baseline else "lower"
        pct_change = (
            abs((actual - baseline) / baseline * 100) if baseline > 0 else Decimal("0")
        )

        explanation = (
            f"{scope_type.title()} spend on {scope_type}"
            if scope_id is None
            else f"{scope_type.title()} '{scope_id}' spend"
        )

        explanation += (
            f" was {float(pct_change):.1f}% {direction} than baseline "
            f"(${float(actual):.2f} vs ${float(baseline):.2f} expected)"
        )

        if top_drivers:
            explanation += f". Top drivers: {', '.join(d['name'] for d in top_drivers[:3])}"

        return explanation
