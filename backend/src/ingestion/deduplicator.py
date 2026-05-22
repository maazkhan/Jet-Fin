import logging
from typing import List, Tuple
from src.models import NormalizedCostEvent, CostSourceType
from src.utils.hash import calculate_source_hash

logger = logging.getLogger(__name__)


class Deduplicator:
    def __init__(self):
        self.seen_hashes = set()

    def deduplicate(self, events: List[NormalizedCostEvent], source_type: CostSourceType) -> Tuple[List[NormalizedCostEvent], List[str]]:
        """Remove duplicates within batch using canonical hash function.

        Uses the same hash key as calculate_source_hash to ensure consistency
        between in-batch and cross-batch deduplication.
        """
        deduped = []
        errors = []

        for event in events:
            key_str = calculate_source_hash(event, source_type)

            if key_str in self.seen_hashes:
                errors.append(f"Duplicate in batch: {key_str}")
            else:
                self.seen_hashes.add(key_str)
                deduped.append(event)

        return deduped, errors
