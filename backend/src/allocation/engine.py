import re
import uuid
import logging
from decimal import Decimal
from pathlib import Path
from typing import List, Tuple, Optional

import yaml
from sqlalchemy.orm import Session

from src.database.models import AllocationRule, CostAllocation, NormalizedCostEvent, CostAggregateByEntity
from src.models import CostStatus

logger = logging.getLogger(__name__)

# Path to rules file — resolved relative to this file's location so it works
# regardless of working directory.
_RULES_FILE = Path(__file__).resolve().parents[2] / "allocation_rules.yaml"


# ---------------------------------------------------------------------------
# Rules loader
# ---------------------------------------------------------------------------

def load_rules_from_yaml(path: Path = _RULES_FILE) -> List[AllocationRule]:
    """
    Load allocation rules from YAML file and return as transient AllocationRule
    objects (not persisted to DB). Called once at startup and cached.
    """
    if not path.exists():
        logger.warning(f"Allocation rules file not found at {path}, using empty ruleset")
        return []

    with open(path) as f:
        data = yaml.safe_load(f)

    rules = []
    for entry in data.get("rules", []):
        r = AllocationRule()
        r.id = uuid.uuid4()
        r.tenant_id = None          # filled in per-tenant at runtime
        r.name = entry["name"]
        r.priority = entry.get("priority", 999)
        r.conditions = entry.get("conditions", {})
        r.action = entry["action"]
        r.action_params = entry.get("action_params", {})
        r.is_active = True
        rules.append(r)

    rules.sort(key=lambda r: r.priority)
    logger.info(f"Loaded {len(rules)} allocation rules from {path}")
    return rules


# Module-level cache — loaded once when the module is first imported.
_YAML_RULES: List[AllocationRule] = load_rules_from_yaml()


def reload_rules():
    """Hot-reload rules from disk without restarting. Call from an admin endpoint if needed."""
    global _YAML_RULES
    _YAML_RULES = load_rules_from_yaml()
    logger.info(f"Reloaded {len(_YAML_RULES)} allocation rules")
    return len(_YAML_RULES)


# ---------------------------------------------------------------------------
# Condition evaluators
# ---------------------------------------------------------------------------

def _get_tag(event: NormalizedCostEvent, key: str) -> Optional[str]:
    tags = event.tags or {}
    return tags.get(key)


def _evaluate_condition(event: NormalizedCostEvent, conditions: dict) -> bool:
    """Return True if every condition in the dict matches the event."""
    for condition_type, value in conditions.items():

        if condition_type == "has_tag":
            if _get_tag(event, value) is None:
                return False

        elif condition_type in ("tag_value", "tag_value2"):
            # {key: "env", value: "prod"}
            tag_val = _get_tag(event, value["key"])
            if tag_val != value["value"]:
                return False

        elif condition_type == "tag_regex":
            # {key: "resource_group", pattern: "rg-.*-prod-.*"}
            tag_val = _get_tag(event, value["key"])
            if tag_val is None or not re.fullmatch(value["pattern"], tag_val):
                return False

        elif condition_type == "resource_id_matches":
            if not re.search(value, event.resource_id or ""):
                return False

        elif condition_type == "service_matches":
            if not re.search(value, event.service or "", re.IGNORECASE):
                return False

        elif condition_type == "provider_matches":
            if (event.provider or "").lower() != value.lower():
                return False

        elif condition_type == "environment_is":
            env_tag = _get_tag(event, "env") or _get_tag(event, "environment")
            if env_tag != value:
                return False

        # Unknown condition types are silently ignored (permissive / forward-compatible)

    return True


# ---------------------------------------------------------------------------
# Action executors
# ---------------------------------------------------------------------------

def _execute_action(
    event: NormalizedCostEvent,
    action: str,
    action_params: dict,
    rule_name: str,
) -> List[Tuple[str, str, Decimal, str]]:
    """
    Execute a matched rule's action.
    Returns list of (entity_type, entity_id, allocated_amount, reason).
    split_percentage can return multiple tuples; all others return one.
    """
    cost = Decimal(str(event.cost_usd))
    results = []

    if action == "allocate_to_team":
        tag_key = action_params.get("tag_key", "owner_team")
        team = _get_tag(event, tag_key) or action_params.get("default", "unknown")
        results.append(("team", team, cost,
                        f"Rule '{rule_name}': tag '{tag_key}'={team}"))

    elif action == "allocate_to_project":
        tag_key = action_params.get("tag_key", "project")
        project = _get_tag(event, tag_key) or action_params.get("default", "unknown")
        results.append(("project", project, cost,
                        f"Rule '{rule_name}': tag '{tag_key}'={project}"))

    elif action == "allocate_to_cost_center":
        tag_key = action_params.get("tag_key", "cost_center")
        center = _get_tag(event, tag_key) or action_params.get("default", "shared")
        results.append(("cost_center", center, cost,
                        f"Rule '{rule_name}': tag '{tag_key}'={center}"))

    elif action == "allocate_to_entity":
        etype = action_params.get("entity_type", "team")
        eid = action_params.get("entity_id", "unknown")
        results.append((etype, eid, cost,
                        f"Rule '{rule_name}': static entity {etype}/{eid}"))

    elif action == "split_percentage":
        splits = action_params.get("splits", [])
        total_pct = sum(s.get("percent", 0) for s in splits)
        for split in splits:
            pct = Decimal(str(split.get("percent", 0)))
            amount = (cost * pct / 100).quantize(Decimal("0.0000000001"))
            etype = split.get("entity_type", "team")
            eid = split.get("entity_id", "unknown")
            results.append((etype, eid, amount,
                            f"Rule '{rule_name}': {pct}% split to {etype}/{eid} (total={total_pct}%)"))

    elif action == "mark_unallocated":
        pass  # caller handles status update

    return results


# ---------------------------------------------------------------------------
# Main engine
# ---------------------------------------------------------------------------

class AllocationEngine:
    """
    Evaluates allocation rules (loaded from allocation_rules.yaml) in priority
    order for each unallocated event. Per-tenant DB rules take precedence over
    the YAML defaults when present.

    Each event is evaluated across all dimensions (team / project / cost_center)
    independently — first matching rule per dimension wins. This means one event
    can produce allocation records to team AND project AND cost_center simultaneously.
    """

    def __init__(self, db: Session):
        self.db = db

    def run_for_tenant(self, tenant_id) -> dict:
        """
        Allocate all pending/unallocated events for the given tenant UUID.
        Returns a summary dict.
        """
        # Prefer tenant-specific DB rules; fall back to YAML defaults.
        db_rules = (
            self.db.query(AllocationRule)
            .filter(
                AllocationRule.tenant_id == tenant_id,
                AllocationRule.is_active == True,
            )
            .order_by(AllocationRule.priority)
            .all()
        )

        if db_rules:
            rules = db_rules
            using_db_rules = True
        else:
            # Stamp tenant_id onto the shared YAML rule objects at runtime.
            # We clone them to avoid mutating the module-level cache.
            rules = self._stamp_tenant(_YAML_RULES, tenant_id)
            using_db_rules = False

        events = (
            self.db.query(NormalizedCostEvent)
            .filter(
                NormalizedCostEvent.tenant_id == tenant_id,
                NormalizedCostEvent.is_allocated == False,
            )
            .all()
        )

        allocated = 0
        unallocated = 0
        allocation_records = []

        for event in events:
            # Resolve each dimension independently; first-match wins per dimension.
            # mark_unallocated only fires if no dimension matched at all.
            allocated_dimensions = {}

            for rule in rules:
                if not _evaluate_condition(event, rule.conditions or {}):
                    continue

                action = rule.action
                params = rule.action_params or {}

                if action == "mark_unallocated":
                    if not allocated_dimensions:
                        pass  # fall through to unallocated handling below
                    break

                alloc_tuples = _execute_action(event, action, params, rule.name)
                for etype, eid, amount, reason in alloc_tuples:
                    if etype not in allocated_dimensions:
                        allocated_dimensions[etype] = True
                        rule_id = rule.id if using_db_rules else None
                        allocation_records.append(CostAllocation(
                            tenant_id=tenant_id,
                            normalized_event_id=event.id,
                            allocation_rule_id=rule_id,
                            business_entity_type=etype,
                            business_entity_id=eid,
                            allocated_amount=amount,
                            allocation_reason=reason,
                        ))

            if allocated_dimensions:
                event.is_allocated = True
                event.status = CostStatus.ALLOCATED.value
                allocated += 1
            else:
                event.is_allocated = False
                event.status = CostStatus.UNALLOCATED.value
                unallocated += 1

        if allocation_records:
            self.db.bulk_save_objects(allocation_records)

        self.db.commit()
        self._refresh_entity_aggregates(tenant_id)
        self.db.commit()

        logger.info(
            f"Allocation complete for tenant {tenant_id}: "
            f"{allocated} allocated, {unallocated} unallocated "
            f"({'db rules' if using_db_rules else 'yaml rules'})"
        )
        return {
            "allocated": allocated,
            "unallocated": unallocated,
            "rules_evaluated": len(rules),
            "allocation_records_created": len(allocation_records),
            "rules_source": "db" if using_db_rules else "yaml",
        }

    @staticmethod
    def _stamp_tenant(rules: List[AllocationRule], tenant_id) -> List[AllocationRule]:
        """Return shallow copies of YAML rules with tenant_id set."""
        stamped = []
        for r in rules:
            copy = AllocationRule()
            copy.id = r.id
            copy.tenant_id = tenant_id
            copy.name = r.name
            copy.priority = r.priority
            copy.conditions = r.conditions
            copy.action = r.action
            copy.action_params = r.action_params
            copy.is_active = r.is_active
            stamped.append(copy)
        return stamped

    # -----------------------------------------------------------------------
    # Entity aggregate refresh
    # -----------------------------------------------------------------------

    def _refresh_entity_aggregates(self, tenant_id):
        """Rebuild cost_aggregates_by_entity from cost_allocations for this tenant."""
        try:
            from sqlalchemy import func

            self.db.query(CostAggregateByEntity).filter(
                CostAggregateByEntity.tenant_id == tenant_id
            ).delete()

            rows = (
                self.db.query(
                    NormalizedCostEvent.event_date,
                    CostAllocation.business_entity_type,
                    CostAllocation.business_entity_id,
                    func.sum(CostAllocation.allocated_amount),
                    func.count(CostAllocation.id),
                )
                .join(CostAllocation, CostAllocation.normalized_event_id == NormalizedCostEvent.id)
                .filter(NormalizedCostEvent.tenant_id == tenant_id)
                .group_by(
                    NormalizedCostEvent.event_date,
                    CostAllocation.business_entity_type,
                    CostAllocation.business_entity_id,
                )
                .all()
            )

            for event_date, etype, eid, total_cost, count in rows:
                self.db.add(CostAggregateByEntity(
                    tenant_id=tenant_id,
                    date=event_date,
                    business_entity_type=etype,
                    business_entity_id=eid,
                    cost_usd=total_cost or 0,
                    record_count=count or 0,
                ))

            logger.info(f"Refreshed entity aggregates for tenant {tenant_id}: {len(rows)} rows")
        except Exception as e:
            logger.warning(f"Failed to refresh entity aggregates (non-blocking): {e}")
            self.db.rollback()
