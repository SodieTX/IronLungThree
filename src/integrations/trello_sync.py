"""Trello-to-Pipeline sync bridge.

Pulls cards from a Trello board and maps them into IronLung pipeline
prospects.  Each Trello list is mapped to a Population, and each card
becomes a prospect (or updates an existing one matched by name).

Usage:
    from src.integrations.trello_sync import TrelloPipelineSync

    sync = TrelloPipelineSync(db)
    result = sync.sync()
    print(result.summary)
"""

from dataclasses import dataclass, field
from typing import Optional

from src.core.logging import get_logger
from src.core.services import get_service_registry
from src.db.database import Database
from src.db.models import (
    Company,
    ContactMethod,
    ContactMethodType,
    Population,
    Prospect,
)
from src.integrations.trello import TrelloClient

logger = get_logger(__name__)

# Default mapping from Trello list names (case-insensitive) to populations.
# Users can customise the board-side names; we match fuzzily.
_DEFAULT_LIST_MAP: dict[str, Population] = {
    "broken": Population.BROKEN,
    "unengaged": Population.UNENGAGED,
    "engaged": Population.ENGAGED,
    "parked": Population.PARKED,
    "dead": Population.DEAD_DNC,
    "dnc": Population.DEAD_DNC,
    "dead_dnc": Population.DEAD_DNC,
    "lost": Population.LOST,
    "partnership": Population.PARTNERSHIP,
    "partnerships": Population.PARTNERSHIP,
    "closed": Population.CLOSED_WON,
    "closed_won": Population.CLOSED_WON,
    "won": Population.CLOSED_WON,
    # Common Trello-style names
    "new leads": Population.UNENGAGED,
    "prospects": Population.UNENGAGED,
    "in progress": Population.ENGAGED,
    "follow up": Population.ENGAGED,
    "follow-up": Population.ENGAGED,
    "demos": Population.ENGAGED,
    "nurture": Population.PARKED,
    "on hold": Population.PARKED,
    "do not contact": Population.DEAD_DNC,
}


@dataclass
class SyncResult:
    """Result of a Trello pipeline sync.

    Attributes:
        created: Number of new prospects created
        updated: Number of existing prospects updated
        skipped: Number of cards skipped (unmapped list, etc.)
        errors: Error messages for cards that failed
        lists_mapped: Which Trello lists mapped to which populations
        lists_unmapped: Trello lists that had no population mapping
        summary: Human-readable summary
    """

    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    lists_mapped: dict[str, str] = field(default_factory=dict)
    lists_unmapped: list[str] = field(default_factory=list)
    summary: str = ""

    def build_summary(self) -> None:
        """Build the human-readable summary string."""
        lines = []
        lines.append(
            f"Created: {self.created}  |  Updated: {self.updated}  |  Skipped: {self.skipped}"
        )
        if self.lists_mapped:
            lines.append("Mapped lists:")
            for list_name, pop in self.lists_mapped.items():
                lines.append(f"  {list_name} -> {pop}")
        if self.lists_unmapped:
            lines.append(f"Unmapped lists (skipped): {', '.join(self.lists_unmapped)}")
        if self.errors:
            lines.append(f"Errors ({len(self.errors)}):")
            for err in self.errors[:10]:
                lines.append(f"  - {err}")
            if len(self.errors) > 10:
                lines.append(f"  ... and {len(self.errors) - 10} more")
        self.summary = "\n".join(lines)


def _match_population(list_name: str) -> Optional[Population]:
    """Match a Trello list name to a Population enum value.

    Tries exact match first, then case-insensitive, then normalised.
    """
    key = list_name.strip().lower()
    if key in _DEFAULT_LIST_MAP:
        return _DEFAULT_LIST_MAP[key]

    # Try matching against Population enum values directly
    for pop in Population:
        if key == pop.value or key == pop.name.lower():
            return pop

    return None


def _parse_card_description(desc: str) -> dict[str, str]:
    """Extract structured fields from a Trello card description.

    Looks for lines like:
        Title: VP of Sales
        Company: ABC Lending
        Email: foo@bar.com
        Phone: 555-123-4567

    Returns dict of lowercase field name -> value.
    """
    fields: dict[str, str] = {}
    for line in desc.splitlines():
        line = line.strip()
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip().lower()
            value = value.strip()
            if key and value:
                fields[key] = value
    return fields


class TrelloPipelineSync:
    """Syncs Trello board cards into IronLung pipeline prospects."""

    def __init__(self, db: Database) -> None:
        self._db = db
        self._client = TrelloClient()

    def is_available(self) -> bool:
        """Check if Trello sync is possible (configured and healthy)."""
        registry = get_service_registry()
        return registry.is_available("trello")

    def sync(self, board_id: Optional[str] = None) -> SyncResult:
        """Pull the full Trello board and sync cards into the pipeline.

        Args:
            board_id: Specific board ID, or None to use configured default

        Returns:
            SyncResult with counts and any errors
        """
        result = SyncResult()

        board = self._client.get_full_board(board_id)

        for list_name, cards in board.items():
            population = _match_population(list_name)
            if population is None:
                result.lists_unmapped.append(list_name)
                result.skipped += len(cards)
                continue

            result.lists_mapped[list_name] = population.value

            for card in cards:
                try:
                    self._sync_card(card.name, card.description, card.labels, population, result)
                except Exception as e:
                    result.errors.append(f"Card '{card.name}': {e}")
                    logger.error(
                        f"Trello sync error for card '{card.name}': {e}",
                        extra={"context": {"card": card.name, "list": list_name}},
                    )

        result.build_summary()
        logger.info(
            "Trello pipeline sync complete",
            extra={
                "context": {
                    "created": result.created,
                    "updated": result.updated,
                    "skipped": result.skipped,
                    "errors": len(result.errors),
                }
            },
        )
        return result

    def _sync_card(
        self,
        card_name: str,
        description: str,
        labels: list[str],
        population: Population,
        result: SyncResult,
    ) -> None:
        """Sync a single Trello card into the pipeline.

        Card name is treated as the prospect's full name.
        Description fields are parsed for title, company, email, phone.
        """
        # Parse the card name into first/last
        parts = card_name.strip().split(None, 1)
        first_name = parts[0] if parts else card_name.strip()
        last_name = parts[1] if len(parts) > 1 else ""

        if not first_name:
            result.skipped += 1
            return

        # Parse structured fields from description
        fields = _parse_card_description(description)
        title = fields.get("title", "")
        company_name = fields.get("company", "")
        email = fields.get("email", "")
        phone = fields.get("phone", "")

        # Check if prospect already exists by name match
        existing = self._find_prospect_by_name(first_name, last_name)

        if existing:
            # Update population if it changed
            if existing.population != population:
                existing.population = population
                if title and not existing.title:
                    existing.title = title
                # Append Trello labels to notes
                if labels:
                    label_text = f"[Trello: {', '.join(labels)}]"
                    if existing.notes:
                        if label_text not in existing.notes:
                            existing.notes += f"\n{label_text}"
                    else:
                        existing.notes = label_text
                self._db.update_prospect(existing)
                result.updated += 1
            else:
                result.skipped += 1
        else:
            # Create company if provided
            company_id = 0
            if company_name:
                company_id = self._find_or_create_company(company_name)

            # Build notes from labels
            notes = None
            if labels:
                notes = f"[Trello: {', '.join(labels)}]"

            prospect = Prospect(
                first_name=first_name,
                last_name=last_name,
                title=title or None,
                company_id=company_id,
                population=population,
                source="trello",
                notes=notes,
            )
            prospect_id = self._db.create_prospect(prospect)

            # Add contact methods if found
            if email:
                self._db.create_contact_method(
                    ContactMethod(
                        prospect_id=prospect_id,
                        type=ContactMethodType.EMAIL,
                        value=email,
                        is_primary=True,
                        source="trello",
                    )
                )
            if phone:
                self._db.create_contact_method(
                    ContactMethod(
                        prospect_id=prospect_id,
                        type=ContactMethodType.PHONE,
                        value=phone,
                        is_primary=not email,
                        source="trello",
                    )
                )
            result.created += 1

    def _find_prospect_by_name(self, first_name: str, last_name: str) -> Optional[Prospect]:
        """Find an existing prospect by first + last name."""
        prospects = self._db.get_prospects(limit=10000)
        for p in prospects:
            if (
                p.first_name.lower() == first_name.lower()
                and p.last_name.lower() == last_name.lower()
            ):
                return p
        return None

    def _find_or_create_company(self, name: str) -> int:
        """Find existing company by name or create a new one."""
        existing = self._db.get_company_by_normalized_name(name)
        if existing and existing.id:
            return existing.id

        company = Company(name=name)
        return self._db.create_company(company)
