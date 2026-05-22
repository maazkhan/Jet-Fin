import logging
from datetime import datetime, date, timedelta

from src.database.connection import DatabaseConnection
from src.database.models import Tenant
from src.anomaly.detector import AnomalyDetector

logger = logging.getLogger(__name__)


def detect_anomalies_daily():
    """
    Scheduled job: Run daily at 2am UTC.
    Detects anomalies for all tenants for yesterday (daily window).
    """
    db = DatabaseConnection.get_session()
    try:
        target_date = datetime.utcnow().date() - timedelta(days=1)
        logger.info(f"Starting daily anomaly detection for {target_date}")

        tenants = db.query(Tenant).all()
        total_anomalies = 0
        failed_tenants = []

        for tenant in tenants:
            try:
                detector = AnomalyDetector(db)
                result = detector.detect_for_tenant(
                    tenant.id, target_date=target_date, window="daily"
                )
                total_anomalies += result["anomalies_detected"]
                logger.info(f"  Tenant {tenant.name}: {result['anomalies_detected']} anomalies")
            except Exception as e:
                logger.error(f"  Tenant {tenant.name} failed: {e}")
                failed_tenants.append((tenant.name, str(e)))

        logger.info(
            f"Daily anomaly detection complete: {total_anomalies} total anomalies, "
            f"{len(failed_tenants)} failed tenants"
        )
        if failed_tenants:
            logger.warning(f"Failed tenants: {failed_tenants}")

        return {
            "job": "detect_anomalies_daily",
            "target_date": str(target_date),
            "total_anomalies": total_anomalies,
            "tenants_processed": len(tenants),
            "failed_tenants": len(failed_tenants),
        }
    finally:
        db.close()


def detect_anomalies_weekly():
    """
    Scheduled job: Run weekly on Mondays at 2am UTC.
    Detects anomalies for all tenants for last week (weekly window).
    """
    db = DatabaseConnection.get_session()
    try:
        # Last Sunday (end of previous week)
        today = datetime.utcnow().date()
        days_since_sunday = (today.weekday() + 1) % 7
        last_sunday = today - timedelta(days=days_since_sunday + 1) if days_since_sunday > 0 else today - timedelta(days=1)

        logger.info(f"Starting weekly anomaly detection for week ending {last_sunday}")

        tenants = db.query(Tenant).all()
        total_anomalies = 0
        failed_tenants = []

        for tenant in tenants:
            try:
                detector = AnomalyDetector(db)
                result = detector.detect_for_tenant(
                    tenant.id, target_date=last_sunday, window="weekly"
                )
                total_anomalies += result["anomalies_detected"]
                logger.info(f"  Tenant {tenant.name}: {result['anomalies_detected']} anomalies")
            except Exception as e:
                logger.error(f"  Tenant {tenant.name} failed: {e}")
                failed_tenants.append((tenant.name, str(e)))

        logger.info(
            f"Weekly anomaly detection complete: {total_anomalies} total anomalies, "
            f"{len(failed_tenants)} failed tenants"
        )
        if failed_tenants:
            logger.warning(f"Failed tenants: {failed_tenants}")

        return {
            "job": "detect_anomalies_weekly",
            "target_period_end": str(last_sunday),
            "total_anomalies": total_anomalies,
            "tenants_processed": len(tenants),
            "failed_tenants": len(failed_tenants),
        }
    finally:
        db.close()


def detect_anomalies_monthly():
    """
    Scheduled job: Run on the 1st of each month at 2am UTC.
    Detects anomalies for all tenants for last month (monthly window).
    """
    db = DatabaseConnection.get_session()
    try:
        today = datetime.utcnow().date()
        # Last day of previous month
        first_of_this_month = today.replace(day=1)
        last_day_of_prev_month = first_of_this_month - timedelta(days=1)

        logger.info(f"Starting monthly anomaly detection for month ending {last_day_of_prev_month}")

        tenants = db.query(Tenant).all()
        total_anomalies = 0
        failed_tenants = []

        for tenant in tenants:
            try:
                detector = AnomalyDetector(db)
                result = detector.detect_for_tenant(
                    tenant.id, target_date=last_day_of_prev_month, window="monthly"
                )
                total_anomalies += result["anomalies_detected"]
                logger.info(f"  Tenant {tenant.name}: {result['anomalies_detected']} anomalies")
            except Exception as e:
                logger.error(f"  Tenant {tenant.name} failed: {e}")
                failed_tenants.append((tenant.name, str(e)))

        logger.info(
            f"Monthly anomaly detection complete: {total_anomalies} total anomalies, "
            f"{len(failed_tenants)} failed tenants"
        )
        if failed_tenants:
            logger.warning(f"Failed tenants: {failed_tenants}")

        return {
            "job": "detect_anomalies_monthly",
            "target_month": str(last_day_of_prev_month.strftime("%Y-%m")),
            "total_anomalies": total_anomalies,
            "tenants_processed": len(tenants),
            "failed_tenants": len(failed_tenants),
        }
    finally:
        db.close()
