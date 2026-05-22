import logging
import csv
import json
from io import BytesIO, StringIO
from src.models import CostSourceType

logger = logging.getLogger(__name__)


class FileValidator:
    """Validates that uploaded file structure matches the declared source type."""

    AWS_REQUIRED_FIELDS = {'unblended_cost', 'blended_cost', 'usage_start_time', 'service', 'resource_id', 'account_id'}
    AZURE_REQUIRED_FIELDS = {'cost_in_billing_currency', 'date', 'subscription_id', 'resource_id', 'consumed_service', 'location'}
    AI_EVENT_REQUIRED_FIELDS = {'tenant_id', 'cost_usd'}

    @staticmethod
    def validate_file(file_bytes: BytesIO, source_type: CostSourceType) -> tuple[bool, str]:
        """
        Validate that the file structure matches the declared source type.
        Returns (is_valid, error_message)
        """
        try:
            file_bytes.seek(0)
            content = file_bytes.read().decode('utf-8')

            if source_type == CostSourceType.AWS:
                return FileValidator._validate_aws(content)
            elif source_type == CostSourceType.AZURE:
                return FileValidator._validate_azure(content)
            elif source_type == CostSourceType.AI_EVENT:
                return FileValidator._validate_ai_event(content)
            else:
                return False, f"Unknown source type: {source_type}"

        except Exception as e:
            logger.error(f"Validation error: {e}")
            return False, f"Failed to validate file: {str(e)}"

    @staticmethod
    def _validate_aws(content: str) -> tuple[bool, str]:
        """Validate AWS CUR file structure."""
        try:
            reader = csv.DictReader(StringIO(content))
            headers = set(reader.fieldnames or [])

            if not headers:
                return False, "CSV file is empty or malformed"

            # Check for AWS-specific fields (need at least one cost field and usage_start_time)
            has_cost = 'unblended_cost' in headers or 'blended_cost' in headers
            has_usage_time = 'usage_start_time' in headers
            has_service = 'service' in headers

            if not (has_cost and has_usage_time and has_service):
                return False, "File does not appear to be AWS CUR format. Missing required fields: usage_start_time, service, or cost field."

            # Check first data row to ensure values are present
            for row in reader:
                if row.get('usage_start_time') and (row.get('unblended_cost') or row.get('blended_cost')):
                    return True, ""
                break

            return False, "File appears to be AWS format but contains no valid data rows."

        except Exception as e:
            return False, f"Failed to parse as AWS CUR: {str(e)}"

    @staticmethod
    def _validate_azure(content: str) -> tuple[bool, str]:
        """Validate Azure Cost Export file structure."""
        try:
            reader = csv.DictReader(StringIO(content))
            headers = set(reader.fieldnames or [])

            if not headers:
                return False, "CSV file is empty or malformed"

            # Check for Azure-specific fields
            has_cost = 'cost_in_billing_currency' in headers
            has_date = 'date' in headers
            has_subscription = 'subscription_id' in headers or 'subscription_name' in headers

            if not (has_cost and has_date and has_subscription):
                return False, "File does not appear to be Azure Cost Export format. Missing required fields: cost_in_billing_currency, date, or subscription info."

            # Check first data row
            for row in reader:
                if row.get('date') and row.get('cost_in_billing_currency'):
                    return True, ""
                break

            return False, "File appears to be Azure format but contains no valid data rows."

        except Exception as e:
            return False, f"Failed to parse as Azure Cost Export: {str(e)}"

    @staticmethod
    def _validate_ai_event(content: str) -> tuple[bool, str]:
        """Validate AI Event JSONL file structure."""
        try:
            lines = content.strip().split('\n')

            if not lines or not lines[0].strip():
                return False, "JSONL file is empty"

            # Check first few lines for JSONL structure
            valid_lines = 0
            for line_idx, line in enumerate(lines[:10]):
                if not line.strip():
                    continue

                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        # Check for AI event required fields: tenant_id and cost_usd
                        has_tenant = 'tenant_id' in obj
                        has_cost = 'cost_usd' in obj

                        if has_tenant and has_cost:
                            valid_lines += 1
                        else:
                            return False, f"Line {line_idx + 1}: Missing required AI event fields (tenant_id, cost_usd)."
                    else:
                        return False, f"Line {line_idx + 1}: Expected JSON object, got {type(obj).__name__}"
                except json.JSONDecodeError as e:
                    return False, f"Line {line_idx + 1}: Invalid JSON: {str(e)}"

            if valid_lines > 0:
                return True, ""
            else:
                return False, "File does not appear to be AI Event JSONL format."

        except Exception as e:
            return False, f"Failed to parse as AI Event JSONL: {str(e)}"
