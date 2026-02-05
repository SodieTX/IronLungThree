"""Email sync - Synchronize email history."""

from datetime import datetime
from typing import Optional

from src.core.logging import get_logger
from src.db.database import Database
from src.integrations.outlook import OutlookClient

logger = get_logger(__name__)


class EmailSync:
    """Email history synchronization."""

    def __init__(self, db: Database, outlook: OutlookClient):
        self.db = db
        self.outlook = outlook

    def sync_sent(self, since: Optional[datetime] = None) -> int:
        """Sync sent emails. Returns count synced."""
        raise NotImplementedError("Phase 5, Step 5.5")

    def sync_received(self, since: Optional[datetime] = None) -> int:
        """Sync received emails. Returns count synced."""
        raise NotImplementedError("Phase 5, Step 5.5")

    def get_last_sync(self) -> Optional[datetime]:
        """Get last sync timestamp."""
        raise NotImplementedError("Phase 5, Step 5.5")
