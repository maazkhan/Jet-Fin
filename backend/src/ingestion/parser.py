import logging
import csv
import json
from io import BytesIO, StringIO
from datetime import datetime, date
from decimal import Decimal
from typing import List, Tuple
from abc import ABC, abstractmethod

from src.models import NormalizedCostEvent, CostSourceType, CostStatus

logger = logging.getLogger(__name__)


class CostParser(ABC):
    @abstractmethod
    def parse(self, file_bytes: BytesIO) -> Tuple[List[NormalizedCostEvent], List[str]]:
        pass


class AWSCURParser(CostParser):
    def parse(self, file_bytes: BytesIO) -> Tuple[List[NormalizedCostEvent], List[str]]:
        events = []
        errors = []

        try:
            file_bytes.seek(0)
            text = file_bytes.read().decode('utf-8')
            reader = csv.DictReader(StringIO(text))

            for row_idx, row in enumerate(reader, start=2):
                try:
                    # Parse tags from JSON string
                    tags = {}
                    tenant_id = "unknown"
                    if "tags" in row and row["tags"]:
                        try:
                            tags = json.loads(row["tags"]) if row["tags"].startswith("{") else {}
                            # Extract tenant from tags
                            tenant_id = tags.get("tenant", "unknown")
                        except:
                            pass

                    cost = Decimal(row.get("unblended_cost") or row.get("blended_cost") or "0")
                    event_date = datetime.fromisoformat(row.get("usage_start_time", "")).date()

                    event = NormalizedCostEvent(
                        tenant_id=tenant_id,
                        resource_id=row.get("resource_id", f"aws-{row.get('account_id')}-{row_idx}"),
                        service=row.get("service", "Unknown"),
                        provider="aws",
                        cost_usd=cost,
                        quantity=Decimal(row.get("usage_amount", "0")) if row.get("usage_amount") else None,
                        unit_type=row.get("pricing_unit"),
                        event_date=event_date,
                        event_hour=datetime.fromisoformat(row.get("usage_start_time", "")),
                        region=row.get("region"),
                        operation=row.get("operation"),
                        resource_type=row.get("product_name"),
                        tags=tags,
                        is_allocated=False,
                        status=CostStatus.PENDING
                    )
                    events.append(event)
                except Exception as e:
                    errors.append(f"Row {row_idx}: {str(e)}")

        except Exception as e:
            logger.error(f"AWS parser error: {e}")
            errors.append(f"Parser error: {str(e)}")

        return events, errors


class AzureCostParser(CostParser):
    def parse(self, file_bytes: BytesIO) -> Tuple[List[NormalizedCostEvent], List[str]]:
        events = []
        errors = []

        try:
            file_bytes.seek(0)
            text = file_bytes.read().decode('utf-8')
            reader = csv.DictReader(StringIO(text))

            for row_idx, row in enumerate(reader, start=2):
                try:
                    # Parse tags from JSON string
                    tags = {}
                    tenant_id = "unknown"
                    if "tags" in row and row["tags"]:
                        try:
                            tags = json.loads(row["tags"]) if row["tags"].startswith("{") else {}
                            # Extract tenant from tags
                            tenant_id = tags.get("tenant", "unknown")
                        except:
                            pass

                    # Preserve resource_group as a tag so allocation rules can match on it
                    if row.get("resource_group"):
                        tags["resource_group"] = row["resource_group"]

                    cost = Decimal(row.get("cost_in_billing_currency", "0"))
                    event_date = datetime.fromisoformat(row.get("date", "")).date() if row.get("date") else date.today()

                    service = row.get("consumed_service") or f"{row.get('meter_category', '')}-{row.get('meter_subcategory', '')}"

                    event = NormalizedCostEvent(
                        tenant_id=tenant_id,
                        resource_id=row.get("resource_id", f"azure-{row.get('subscription_id')}-{row_idx}"),
                        service=service,
                        provider="azure",
                        cost_usd=cost,
                        quantity=Decimal(row.get("quantity", "0")) if row.get("quantity") else None,
                        unit_type=row.get("unit_of_measure"),
                        event_date=event_date,
                        event_hour=datetime.fromisoformat(f"{event_date.isoformat()}T00:00:00"),
                        region=row.get("location"),
                        operation=row.get("meter_name"),
                        resource_type=row.get("resource_type"),
                        tags=tags,
                        is_allocated=False,
                        status=CostStatus.PENDING
                    )
                    events.append(event)
                except Exception as e:
                    errors.append(f"Row {row_idx}: {str(e)}")

        except Exception as e:
            logger.error(f"Azure parser error: {e}")
            errors.append(f"Parser error: {str(e)}")

        return events, errors


class AIEventParser(CostParser):
    def parse(self, file_bytes: BytesIO) -> Tuple[List[NormalizedCostEvent], List[str]]:
        events = []
        errors = []

        try:
            file_bytes.seek(0)
            text = file_bytes.read().decode('utf-8')

            for row_idx, line in enumerate(text.split('\n'), start=1):
                if not line.strip():
                    continue

                try:
                    row = json.loads(line)

                    tenant_id = row.get("tenant_id", "unknown")
                    tags = {
                        "project_id": row.get("project_id", ""),
                        "user_id": row.get("user_id", ""),
                        "model": row.get("model", ""),
                        "environment": row.get("environment", "")
                    }

                    total_tokens = (
                        int(row.get("input_tokens", 0)) +
                        int(row.get("output_tokens", 0)) +
                        int(row.get("cached_tokens", 0))
                    )

                    event_ts = row.get("timestamp", "")
                    try:
                        event_datetime = datetime.fromisoformat(event_ts.replace("Z", "+00:00")) if event_ts else datetime.utcnow()
                    except:
                        event_datetime = datetime.utcnow()

                    event = NormalizedCostEvent(
                        tenant_id=tenant_id,
                        resource_id=f"ai-{row.get('request_id', '')}-{row.get('model', '')}",
                        service=f"AI-{row.get('provider', 'unknown')}",
                        provider="ai",
                        cost_usd=Decimal(str(row.get("cost_usd", "0"))),
                        quantity=Decimal(str(total_tokens)) if total_tokens > 0 else None,
                        unit_type="tokens",
                        event_date=event_datetime.date(),
                        event_hour=event_datetime,
                        region=row.get("region"),
                        operation=f"model_{row.get('model', 'unknown')}",
                        resource_type="ai_request",
                        tags=tags,
                        is_allocated=False,
                        status=CostStatus.PENDING
                    )
                    events.append(event)
                except Exception as e:
                    errors.append(f"Line {row_idx}: {str(e)}")

        except Exception as e:
            logger.error(f"AI parser error: {e}")
            errors.append(f"Parser error: {str(e)}")

        return events, errors


class ParserFactory:
    @staticmethod
    def get_parser(source_type: CostSourceType) -> CostParser:
        if source_type == CostSourceType.AWS:
            return AWSCURParser()
        elif source_type == CostSourceType.AZURE:
            return AzureCostParser()
        elif source_type == CostSourceType.AI_EVENT:
            return AIEventParser()
        else:
            raise ValueError(f"Unknown source type: {source_type}")
