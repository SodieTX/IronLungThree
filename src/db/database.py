"""SQLite database connection and operations for IronLung 3.

Provides:
    - Connection management with WAL mode
    - Schema creation and migration
    - CRUD operations for all tables
    - Query builders with filtering

Usage:
    from src.db.database import Database

    db = Database()
    db.initialize()

    company = Company(name="ABC Lending, LLC", state="TX")
    company_id = db.create_company(company)
"""

import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

from src.core.config import get_config
from src.core.exceptions import DatabaseError
from src.core.logging import get_logger
from src.db.models import (
    Activity,
    Company,
    ContactMethod,
    EngagementStage,
    ImportSource,
    IntelNugget,
    Population,
    Prospect,
    ProspectTag,
    ResearchTask,
    normalize_company_name,
    timezone_from_state,
)

logger = get_logger(__name__)


# Schema version for migrations
SCHEMA_VERSION = 1


class Database:
    """SQLite database manager.

    Attributes:
        db_path: Path to database file
    """

    def __init__(self, db_path: Optional[str] = None):
        """Initialize database.

        Args:
            db_path: Path to database file. Use ":memory:" for in-memory.
                    Defaults to config path.
        """
        if db_path is None:
            config = get_config()
            self.db_path = str(config.db_path)
        else:
            self.db_path = db_path

        self._conn: Optional[sqlite3.Connection] = None

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self._conn is None:
            try:
                # Create directory if needed (unless in-memory)
                if self.db_path != ":memory:":
                    Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

                self._conn = sqlite3.connect(
                    self.db_path,
                    detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
                )
                self._conn.row_factory = sqlite3.Row

                # Enable foreign keys
                self._conn.execute("PRAGMA foreign_keys = ON")

                # Enable WAL mode for better concurrency
                if self.db_path != ":memory:":
                    self._conn.execute("PRAGMA journal_mode = WAL")

            except sqlite3.Error as e:
                raise DatabaseError(f"Cannot connect to database: {e}") from e

        return self._conn

    def close(self) -> None:
        """Close database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def initialize(self) -> None:
        """Create schema if not exists.

        Creates all tables, indexes, and initial schema version.
        """
        conn = self._get_connection()

        try:
            conn.executescript(self._get_schema_ddl())
            conn.commit()
            logger.info("Database initialized", extra={"context": {"path": self.db_path}})
        except sqlite3.Error as e:
            raise DatabaseError(f"Cannot initialize database: {e}") from e

    def _get_schema_ddl(self) -> str:
        """Return complete schema DDL."""
        return """
        -- Companies
        CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            name_normalized TEXT NOT NULL,
            domain TEXT,
            loan_types TEXT,
            size TEXT,
            state TEXT,
            timezone TEXT NOT NULL DEFAULT 'central',
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_companies_normalized ON companies(name_normalized);
        CREATE INDEX IF NOT EXISTS idx_companies_domain ON companies(domain);
        
        -- Prospects
        CREATE TABLE IF NOT EXISTS prospects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            title TEXT,
            population TEXT NOT NULL DEFAULT 'broken',
            engagement_stage TEXT,
            follow_up_date DATETIME,
            last_contact_date DATE,
            parked_month TEXT,
            attempt_count INTEGER DEFAULT 0,
            prospect_score INTEGER DEFAULT 0,
            data_confidence INTEGER DEFAULT 0,
            preferred_contact_method TEXT,
            source TEXT,
            referred_by_prospect_id INTEGER,
            dead_reason TEXT,
            dead_date DATE,
            lost_reason TEXT,
            lost_competitor TEXT,
            lost_date DATE,
            deal_value DECIMAL(10,2),
            close_date DATE,
            close_notes TEXT,
            notes TEXT,
            custom_fields TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (company_id) REFERENCES companies(id),
            FOREIGN KEY (referred_by_prospect_id) REFERENCES prospects(id)
        );
        
        CREATE INDEX IF NOT EXISTS idx_prospects_population ON prospects(population);
        CREATE INDEX IF NOT EXISTS idx_prospects_follow_up ON prospects(follow_up_date);
        CREATE INDEX IF NOT EXISTS idx_prospects_company ON prospects(company_id);
        CREATE INDEX IF NOT EXISTS idx_prospects_score ON prospects(prospect_score);
        CREATE INDEX IF NOT EXISTS idx_prospects_parked ON prospects(parked_month);
        CREATE INDEX IF NOT EXISTS idx_prospects_referrer ON prospects(referred_by_prospect_id);
        
        -- Contact Methods
        CREATE TABLE IF NOT EXISTS contact_methods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prospect_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            value TEXT NOT NULL,
            label TEXT,
            is_primary BOOLEAN DEFAULT 0,
            is_verified BOOLEAN DEFAULT 0,
            verified_date DATE,
            confidence_score INTEGER DEFAULT 0,
            is_suspect BOOLEAN DEFAULT 0,
            source TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (prospect_id) REFERENCES prospects(id) ON DELETE CASCADE
        );
        
        CREATE INDEX IF NOT EXISTS idx_contact_methods_prospect ON contact_methods(prospect_id);
        CREATE INDEX IF NOT EXISTS idx_contact_methods_email ON contact_methods(value) WHERE type='email';
        CREATE INDEX IF NOT EXISTS idx_contact_methods_phone ON contact_methods(value) WHERE type='phone';
        
        -- Activities
        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prospect_id INTEGER NOT NULL,
            activity_type TEXT NOT NULL,
            outcome TEXT,
            call_duration_seconds INTEGER,
            population_before TEXT,
            population_after TEXT,
            stage_before TEXT,
            stage_after TEXT,
            email_subject TEXT,
            email_body TEXT,
            follow_up_set DATETIME,
            attempt_type TEXT,
            notes TEXT,
            created_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (prospect_id) REFERENCES prospects(id) ON DELETE CASCADE
        );
        
        CREATE INDEX IF NOT EXISTS idx_activities_prospect ON activities(prospect_id);
        CREATE INDEX IF NOT EXISTS idx_activities_date ON activities(created_at);
        CREATE INDEX IF NOT EXISTS idx_activities_type ON activities(activity_type);
        
        -- Data Freshness
        CREATE TABLE IF NOT EXISTS data_freshness (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prospect_id INTEGER NOT NULL,
            field_name TEXT NOT NULL,
            verified_date DATE NOT NULL,
            verification_method TEXT,
            confidence INTEGER,
            previous_value TEXT,
            FOREIGN KEY (prospect_id) REFERENCES prospects(id) ON DELETE CASCADE
        );
        
        CREATE INDEX IF NOT EXISTS idx_freshness_prospect ON data_freshness(prospect_id);
        CREATE INDEX IF NOT EXISTS idx_freshness_date ON data_freshness(verified_date);
        
        -- Import Sources
        CREATE TABLE IF NOT EXISTS import_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_name TEXT NOT NULL,
            filename TEXT,
            total_records INTEGER,
            imported_records INTEGER,
            duplicate_records INTEGER,
            broken_records INTEGER,
            dnc_blocked_records INTEGER,
            import_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_import_date ON import_sources(import_date);
        
        -- Research Queue
        CREATE TABLE IF NOT EXISTS research_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prospect_id INTEGER NOT NULL,
            priority INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            attempts INTEGER DEFAULT 0,
            last_attempt_date TIMESTAMP,
            findings TEXT,
            FOREIGN KEY (prospect_id) REFERENCES prospects(id) ON DELETE CASCADE
        );
        
        CREATE INDEX IF NOT EXISTS idx_research_prospect ON research_queue(prospect_id);
        CREATE INDEX IF NOT EXISTS idx_research_status ON research_queue(status);
        
        -- Intel Nuggets
        CREATE TABLE IF NOT EXISTS intel_nuggets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prospect_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            content TEXT NOT NULL,
            source_activity_id INTEGER,
            extracted_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (prospect_id) REFERENCES prospects(id) ON DELETE CASCADE,
            FOREIGN KEY (source_activity_id) REFERENCES activities(id)
        );
        
        CREATE INDEX IF NOT EXISTS idx_nuggets_prospect ON intel_nuggets(prospect_id);
        CREATE INDEX IF NOT EXISTS idx_nuggets_category ON intel_nuggets(category);
        
        -- Prospect Tags
        CREATE TABLE IF NOT EXISTS prospect_tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prospect_id INTEGER NOT NULL,
            tag_name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (prospect_id) REFERENCES prospects(id) ON DELETE CASCADE,
            UNIQUE(prospect_id, tag_name)
        );
        
        CREATE INDEX IF NOT EXISTS idx_tags_prospect ON prospect_tags(prospect_id);
        CREATE INDEX IF NOT EXISTS idx_tags_name ON prospect_tags(tag_name);
        
        -- Schema Version
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        INSERT OR IGNORE INTO schema_version (version) VALUES (1);
        """

    # =========================================================================
    # COMPANY OPERATIONS
    # =========================================================================

    def create_company(self, company: Company) -> int:
        """Create a company record.

        Auto-normalizes name and assigns timezone from state.

        Args:
            company: Company to create

        Returns:
            New company ID
        """
        raise NotImplementedError("Phase 1, Step 1.6")

    def get_company(self, company_id: int) -> Optional[Company]:
        """Get company by ID."""
        raise NotImplementedError("Phase 1, Step 1.6")

    def get_company_by_normalized_name(self, name: str) -> Optional[Company]:
        """Find company by normalized name for dedup."""
        raise NotImplementedError("Phase 1, Step 1.6")

    def update_company(self, company: Company) -> bool:
        """Update company. Returns True if updated."""
        raise NotImplementedError("Phase 1, Step 1.6")

    def search_companies(self, query: str, limit: int = 50) -> list[Company]:
        """Search companies by partial name."""
        raise NotImplementedError("Phase 1, Step 1.6")

    # =========================================================================
    # PROSPECT OPERATIONS
    # =========================================================================

    def create_prospect(self, prospect: Prospect) -> int:
        """Create a prospect record."""
        raise NotImplementedError("Phase 1, Step 1.7")

    def get_prospect(self, prospect_id: int) -> Optional[Prospect]:
        """Get prospect by ID (basic fields only)."""
        raise NotImplementedError("Phase 1, Step 1.7")

    def get_prospect_full(self, prospect_id: int) -> Optional[dict[str, Any]]:
        """Get prospect with company, contact methods, activities."""
        raise NotImplementedError("Phase 1, Step 1.7")

    def update_prospect(self, prospect: Prospect) -> bool:
        """Update prospect. Returns True if updated."""
        raise NotImplementedError("Phase 1, Step 1.7")

    def get_prospects(
        self,
        population: Optional[Population] = None,
        company_id: Optional[int] = None,
        state: Optional[str] = None,
        score_min: Optional[int] = None,
        score_max: Optional[int] = None,
        search_query: Optional[str] = None,
        tags: Optional[list[str]] = None,
        sort_by: str = "prospect_score",
        sort_dir: str = "DESC",
        limit: int = 100,
        offset: int = 0,
    ) -> list[Prospect]:
        """Get prospects with filtering and pagination."""
        raise NotImplementedError("Phase 1, Step 1.7")

    def get_population_counts(self) -> dict[Population, int]:
        """Return count of prospects in each population."""
        raise NotImplementedError("Phase 1, Step 1.10")

    # =========================================================================
    # CONTACT METHOD OPERATIONS
    # =========================================================================

    def create_contact_method(self, method: ContactMethod) -> int:
        """Add contact method to prospect."""
        raise NotImplementedError("Phase 1, Step 1.8")

    def get_contact_methods(self, prospect_id: int) -> list[ContactMethod]:
        """Get all contact methods for prospect, primary first."""
        raise NotImplementedError("Phase 1, Step 1.8")

    def update_contact_method(self, method: ContactMethod) -> bool:
        """Update contact method."""
        raise NotImplementedError("Phase 1, Step 1.8")

    def find_prospect_by_email(self, email: str) -> Optional[int]:
        """Find prospect ID by email (case-insensitive)."""
        raise NotImplementedError("Phase 1, Step 1.8")

    def find_prospect_by_phone(self, phone: str) -> Optional[int]:
        """Find prospect ID by phone (digits-only match)."""
        raise NotImplementedError("Phase 1, Step 1.8")

    def is_dnc(self, email: Optional[str] = None, phone: Optional[str] = None) -> bool:
        """Check if email or phone belongs to a DNC prospect."""
        raise NotImplementedError("Phase 1, Step 1.8")

    # =========================================================================
    # ACTIVITY OPERATIONS
    # =========================================================================

    def create_activity(self, activity: Activity) -> int:
        """Log an activity."""
        raise NotImplementedError("Phase 1, Step 1.9")

    def get_activities(self, prospect_id: int, limit: int = 50) -> list[Activity]:
        """Get activities for prospect, most recent first."""
        raise NotImplementedError("Phase 1, Step 1.9")

    # =========================================================================
    # BULK OPERATIONS
    # =========================================================================

    def bulk_update_population(
        self,
        prospect_ids: list[int],
        population: Population,
        reason: str,
    ) -> tuple[int, int]:
        """Update population for multiple prospects.

        DNC records are skipped, not modified.

        Returns:
            Tuple of (updated_count, skipped_dnc_count)
        """
        raise NotImplementedError("Phase 1, Step 1.10")

    def bulk_set_follow_up(
        self,
        prospect_ids: list[int],
        follow_up_date: datetime,
    ) -> int:
        """Set follow-up date for multiple prospects."""
        raise NotImplementedError("Phase 1, Step 1.10")

    def bulk_park(
        self,
        prospect_ids: list[int],
        parked_month: str,
    ) -> tuple[int, int]:
        """Park prospects in a month (YYYY-MM).

        Returns:
            Tuple of (parked_count, skipped_dnc_count)
        """
        raise NotImplementedError("Phase 1, Step 1.10")

    # =========================================================================
    # TAG OPERATIONS
    # =========================================================================

    def add_tag(self, prospect_id: int, tag_name: str) -> bool:
        """Add tag to prospect."""
        raise NotImplementedError("Phase 1, Step 1.10")

    def remove_tag(self, prospect_id: int, tag_name: str) -> bool:
        """Remove tag from prospect."""
        raise NotImplementedError("Phase 1, Step 1.10")

    def get_tags(self, prospect_id: int) -> list[str]:
        """Get all tags for prospect."""
        raise NotImplementedError("Phase 1, Step 1.10")

    def get_all_tags(self) -> list[str]:
        """Get all unique tags in system."""
        raise NotImplementedError("Phase 1, Step 1.10")
