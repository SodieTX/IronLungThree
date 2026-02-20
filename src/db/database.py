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
    ActivityOutcome,
    ActivityType,
    AttemptType,
    Company,
    ContactMethod,
    ContactMethodType,
    DeadReason,
    EngagementStage,
    ImportSource,
    IntelCategory,
    IntelNugget,
    LostReason,
    Population,
    Prospect,
    ProspectFull,
    ProspectTag,
    ResearchStatus,
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

    @staticmethod
    def _lastrowid(cursor: sqlite3.Cursor) -> int:
        """Extract lastrowid from cursor (always set after INSERT in SQLite)."""
        row_id = cursor.lastrowid
        assert row_id is not None, "lastrowid was None after INSERT"
        return row_id

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
    # ROW-TO-MODEL HELPERS
    # =========================================================================

    def _row_to_company(self, row: sqlite3.Row) -> Company:
        """Convert a database row to a Company dataclass."""
        return Company(
            id=row["id"],
            name=row["name"],
            name_normalized=row["name_normalized"],
            domain=row["domain"],
            loan_types=row["loan_types"],
            size=row["size"],
            state=row["state"],
            timezone=row["timezone"],
            notes=row["notes"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _row_to_prospect(self, row: sqlite3.Row) -> Prospect:
        """Convert a database row to a Prospect dataclass."""
        pop_val = row["population"]
        population = Population(pop_val) if pop_val else Population.BROKEN

        stage_val = row["engagement_stage"]
        engagement_stage = EngagementStage(stage_val) if stage_val else None

        lost_val = row["lost_reason"]
        lost_reason = LostReason(lost_val) if lost_val else None

        dead_val = row["dead_reason"]
        dead_reason = DeadReason(dead_val) if dead_val else None

        return Prospect(
            id=row["id"],
            company_id=row["company_id"],
            first_name=row["first_name"],
            last_name=row["last_name"],
            title=row["title"],
            population=population,
            engagement_stage=engagement_stage,
            follow_up_date=row["follow_up_date"],
            last_contact_date=row["last_contact_date"],
            parked_month=row["parked_month"],
            attempt_count=row["attempt_count"] or 0,
            prospect_score=row["prospect_score"] or 0,
            data_confidence=row["data_confidence"] or 0,
            preferred_contact_method=row["preferred_contact_method"],
            source=row["source"],
            referred_by_prospect_id=row["referred_by_prospect_id"],
            dead_reason=dead_reason,
            dead_date=row["dead_date"],
            lost_reason=lost_reason,
            lost_competitor=row["lost_competitor"],
            lost_date=row["lost_date"],
            deal_value=row["deal_value"],
            close_date=row["close_date"],
            close_notes=row["close_notes"],
            notes=row["notes"],
            custom_fields=row["custom_fields"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _row_to_contact_method(self, row: sqlite3.Row) -> ContactMethod:
        """Convert a database row to a ContactMethod dataclass."""
        return ContactMethod(
            id=row["id"],
            prospect_id=row["prospect_id"],
            type=ContactMethodType(row["type"]),
            value=row["value"],
            label=row["label"],
            is_primary=bool(row["is_primary"]),
            is_verified=bool(row["is_verified"]),
            verified_date=row["verified_date"],
            confidence_score=row["confidence_score"] or 0,
            is_suspect=bool(row["is_suspect"]),
            source=row["source"],
            created_at=row["created_at"],
        )

    def _row_to_activity(self, row: sqlite3.Row) -> Activity:
        """Convert a database row to an Activity dataclass."""
        activity_type = (
            ActivityType(row["activity_type"]) if row["activity_type"] else ActivityType.NOTE
        )

        outcome_val = row["outcome"]
        outcome = ActivityOutcome(outcome_val) if outcome_val else None

        pop_before = Population(row["population_before"]) if row["population_before"] else None
        pop_after = Population(row["population_after"]) if row["population_after"] else None
        stage_before = EngagementStage(row["stage_before"]) if row["stage_before"] else None
        stage_after = EngagementStage(row["stage_after"]) if row["stage_after"] else None
        attempt_val = row["attempt_type"]
        attempt_type = AttemptType(attempt_val) if attempt_val else None

        return Activity(
            id=row["id"],
            prospect_id=row["prospect_id"],
            activity_type=activity_type,
            outcome=outcome,
            call_duration_seconds=row["call_duration_seconds"],
            population_before=pop_before,
            population_after=pop_after,
            stage_before=stage_before,
            stage_after=stage_after,
            email_subject=row["email_subject"],
            email_body=row["email_body"],
            follow_up_set=row["follow_up_set"],
            attempt_type=attempt_type,
            notes=row["notes"],
            created_by=row["created_by"] or "user",
            created_at=row["created_at"],
        )

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
        conn = self._get_connection()
        name_norm = normalize_company_name(company.name)
        tz = timezone_from_state(company.state)

        try:
            cursor = conn.execute(
                """INSERT INTO companies
                   (name, name_normalized, domain, loan_types, size, state, timezone, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    company.name,
                    name_norm,
                    company.domain,
                    company.loan_types,
                    company.size,
                    company.state,
                    tz,
                    company.notes,
                ),
            )
            conn.commit()
            company_id = self._lastrowid(cursor)
            logger.info(
                "Company created",
                extra={"context": {"company_id": company_id, "name": company.name}},
            )
            return company_id
        except sqlite3.Error as e:
            conn.rollback()
            raise DatabaseError(f"Failed to create company: {e}") from e

    def get_company(self, company_id: int) -> Optional[Company]:
        """Get company by ID."""
        conn = self._get_connection()
        row = conn.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_company(row)

    def get_company_by_normalized_name(self, name: str) -> Optional[Company]:
        """Find company by normalized name for dedup."""
        conn = self._get_connection()
        name_norm = normalize_company_name(name)
        row = conn.execute(
            "SELECT * FROM companies WHERE name_normalized = ?", (name_norm,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_company(row)

    def update_company(self, company: Company) -> bool:
        """Update company. Returns True if updated."""
        if company.id is None:
            return False
        conn = self._get_connection()
        name_norm = normalize_company_name(company.name)
        tz = timezone_from_state(company.state)
        try:
            cursor = conn.execute(
                """UPDATE companies SET
                   name = ?, name_normalized = ?, domain = ?, loan_types = ?,
                   size = ?, state = ?, timezone = ?, notes = ?,
                   updated_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (
                    company.name,
                    name_norm,
                    company.domain,
                    company.loan_types,
                    company.size,
                    company.state,
                    tz,
                    company.notes,
                    company.id,
                ),
            )
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            conn.rollback()
            raise DatabaseError(f"Failed to update company: {e}") from e

    def search_companies(self, query: str, limit: int = 50) -> list[Company]:
        """Search companies by partial name."""
        conn = self._get_connection()
        pattern = f"%{query.lower()}%"
        rows = conn.execute(
            "SELECT * FROM companies WHERE name_normalized LIKE ? ORDER BY name LIMIT ?",
            (pattern, limit),
        ).fetchall()
        return [self._row_to_company(row) for row in rows]

    # =========================================================================
    # PROSPECT OPERATIONS
    # =========================================================================

    def create_prospect(self, prospect: Prospect) -> int:
        """Create a prospect record."""
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                """INSERT INTO prospects
                   (company_id, first_name, last_name, title, population,
                    engagement_stage, follow_up_date, last_contact_date, parked_month,
                    attempt_count, prospect_score, data_confidence,
                    preferred_contact_method, source, referred_by_prospect_id,
                    dead_reason, dead_date, lost_reason, lost_competitor, lost_date,
                    deal_value, close_date, close_notes, notes, custom_fields)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    prospect.company_id,
                    prospect.first_name,
                    prospect.last_name,
                    prospect.title,
                    (
                        prospect.population.value
                        if isinstance(prospect.population, Population)
                        else prospect.population
                    ),
                    prospect.engagement_stage.value if prospect.engagement_stage else None,
                    prospect.follow_up_date,
                    prospect.last_contact_date,
                    prospect.parked_month,
                    prospect.attempt_count,
                    prospect.prospect_score,
                    prospect.data_confidence,
                    prospect.preferred_contact_method,
                    prospect.source,
                    prospect.referred_by_prospect_id,
                    (
                        prospect.dead_reason.value
                        if isinstance(prospect.dead_reason, DeadReason)
                        else prospect.dead_reason
                    ),
                    prospect.dead_date,
                    prospect.lost_reason.value if prospect.lost_reason else None,
                    prospect.lost_competitor,
                    prospect.lost_date,
                    prospect.deal_value,
                    prospect.close_date,
                    prospect.close_notes,
                    prospect.notes,
                    prospect.custom_fields,
                ),
            )
            conn.commit()
            prospect_id = self._lastrowid(cursor)
            logger.info(
                "Prospect created",
                extra={"context": {"prospect_id": prospect_id, "name": prospect.full_name}},
            )
            return prospect_id
        except sqlite3.Error as e:
            conn.rollback()
            raise DatabaseError(f"Failed to create prospect: {e}") from e

    def get_prospect(self, prospect_id: int) -> Optional[Prospect]:
        """Get prospect by ID (basic fields only)."""
        conn = self._get_connection()
        row = conn.execute("SELECT * FROM prospects WHERE id = ?", (prospect_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_prospect(row)

    def get_prospect_full(self, prospect_id: int) -> Optional[ProspectFull]:
        """Get prospect with company, contact methods, activities."""
        prospect = self.get_prospect(prospect_id)
        if prospect is None:
            return None

        company = self.get_company(prospect.company_id) if prospect.company_id else None
        contact_methods = self.get_contact_methods(prospect_id)
        activities = self.get_activities(prospect_id)
        tags = self.get_tags(prospect_id)

        return ProspectFull(
            prospect=prospect,
            company=company,
            contact_methods=contact_methods,
            activities=activities,
            tags=tags,
        )

    def update_prospect(self, prospect: Prospect) -> bool:
        """Update prospect. Returns True if updated."""
        if prospect.id is None:
            return False
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                """UPDATE prospects SET
                   company_id = ?, first_name = ?, last_name = ?, title = ?,
                   population = ?, engagement_stage = ?,
                   follow_up_date = ?, last_contact_date = ?, parked_month = ?,
                   attempt_count = ?, prospect_score = ?, data_confidence = ?,
                   preferred_contact_method = ?, source = ?, referred_by_prospect_id = ?,
                   dead_reason = ?, dead_date = ?, lost_reason = ?,
                   lost_competitor = ?, lost_date = ?,
                   deal_value = ?, close_date = ?, close_notes = ?,
                   notes = ?, custom_fields = ?,
                   updated_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (
                    prospect.company_id,
                    prospect.first_name,
                    prospect.last_name,
                    prospect.title,
                    (
                        prospect.population.value
                        if isinstance(prospect.population, Population)
                        else prospect.population
                    ),
                    prospect.engagement_stage.value if prospect.engagement_stage else None,
                    prospect.follow_up_date,
                    prospect.last_contact_date,
                    prospect.parked_month,
                    prospect.attempt_count,
                    prospect.prospect_score,
                    prospect.data_confidence,
                    prospect.preferred_contact_method,
                    prospect.source,
                    prospect.referred_by_prospect_id,
                    (
                        prospect.dead_reason.value
                        if isinstance(prospect.dead_reason, DeadReason)
                        else prospect.dead_reason
                    ),
                    prospect.dead_date,
                    prospect.lost_reason.value if prospect.lost_reason else None,
                    prospect.lost_competitor,
                    prospect.lost_date,
                    prospect.deal_value,
                    prospect.close_date,
                    prospect.close_notes,
                    prospect.notes,
                    prospect.custom_fields,
                    prospect.id,
                ),
            )
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            conn.rollback()
            raise DatabaseError(f"Failed to update prospect: {e}") from e

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
        conn = self._get_connection()

        # Whitelist sort columns to prevent SQL injection
        allowed_sort_cols = {
            "prospect_score",
            "first_name",
            "last_name",
            "created_at",
            "updated_at",
            "follow_up_date",
            "attempt_count",
            "data_confidence",
        }
        if sort_by not in allowed_sort_cols:
            sort_by = "prospect_score"
        if sort_dir.upper() not in ("ASC", "DESC"):
            sort_dir = "DESC"

        conditions: list[str] = []
        params: list[Any] = []

        if population is not None:
            conditions.append("p.population = ?")
            params.append(population.value)

        if company_id is not None:
            conditions.append("p.company_id = ?")
            params.append(company_id)

        if state is not None:
            conditions.append("c.state = ?")
            params.append(state)

        if score_min is not None:
            conditions.append("p.prospect_score >= ?")
            params.append(score_min)

        if score_max is not None:
            conditions.append("p.prospect_score <= ?")
            params.append(score_max)

        if search_query:
            conditions.append("(p.first_name LIKE ? OR p.last_name LIKE ? OR c.name LIKE ?)")
            pattern = f"%{search_query}%"
            params.extend([pattern, pattern, pattern])

        if tags:
            placeholders = ",".join("?" for _ in tags)
            conditions.append(
                f"p.id IN (SELECT prospect_id FROM prospect_tags WHERE tag_name IN ({placeholders}))"
            )
            params.extend(tags)

        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)

        query = f"""
            SELECT p.* FROM prospects p
            LEFT JOIN companies c ON p.company_id = c.id
            {where_clause}
            ORDER BY p.{sort_by} {sort_dir}
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])

        rows = conn.execute(query, params).fetchall()
        return [self._row_to_prospect(row) for row in rows]

    def get_population_counts(self) -> dict[Population, int]:
        """Return count of prospects in each population."""
        conn = self._get_connection()
        rows = conn.execute(
            "SELECT population, COUNT(*) as cnt FROM prospects GROUP BY population"
        ).fetchall()
        counts: dict[Population, int] = {}
        for row in rows:
            try:
                pop = Population(row["population"])
                counts[pop] = row["cnt"]
            except ValueError:
                pass
        return counts

    # =========================================================================
    # CONTACT METHOD OPERATIONS
    # =========================================================================

    def create_contact_method(self, method: ContactMethod) -> int:
        """Add contact method to prospect."""
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                """INSERT INTO contact_methods
                   (prospect_id, type, value, label, is_primary, is_verified,
                    verified_date, confidence_score, is_suspect, source)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    method.prospect_id,
                    (
                        method.type.value
                        if isinstance(method.type, ContactMethodType)
                        else method.type
                    ),
                    method.value,
                    method.label,
                    1 if method.is_primary else 0,
                    1 if method.is_verified else 0,
                    method.verified_date,
                    method.confidence_score,
                    1 if method.is_suspect else 0,
                    method.source,
                ),
            )
            conn.commit()
            return self._lastrowid(cursor)
        except sqlite3.Error as e:
            conn.rollback()
            raise DatabaseError(f"Failed to create contact method: {e}") from e

    def get_contact_methods(self, prospect_id: int) -> list[ContactMethod]:
        """Get all contact methods for prospect, primary first."""
        conn = self._get_connection()
        rows = conn.execute(
            "SELECT * FROM contact_methods WHERE prospect_id = ? ORDER BY is_primary DESC, id ASC",
            (prospect_id,),
        ).fetchall()
        return [self._row_to_contact_method(row) for row in rows]

    def update_contact_method(self, method: ContactMethod) -> bool:
        """Update contact method."""
        if method.id is None:
            return False
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                """UPDATE contact_methods SET
                   type = ?, value = ?, label = ?, is_primary = ?, is_verified = ?,
                   verified_date = ?, confidence_score = ?, is_suspect = ?, source = ?
                   WHERE id = ?""",
                (
                    (
                        method.type.value
                        if isinstance(method.type, ContactMethodType)
                        else method.type
                    ),
                    method.value,
                    method.label,
                    1 if method.is_primary else 0,
                    1 if method.is_verified else 0,
                    method.verified_date,
                    method.confidence_score,
                    1 if method.is_suspect else 0,
                    method.source,
                    method.id,
                ),
            )
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            conn.rollback()
            raise DatabaseError(f"Failed to update contact method: {e}") from e

    def find_prospect_by_email(self, email: str) -> Optional[int]:
        """Find prospect ID by email (case-insensitive)."""
        conn = self._get_connection()
        row = conn.execute(
            "SELECT prospect_id FROM contact_methods WHERE LOWER(value) = LOWER(?) AND type = 'email'",
            (email,),
        ).fetchone()
        if row is None:
            return None
        return int(row["prospect_id"])

    def find_prospect_by_phone(self, phone: str) -> Optional[int]:
        """Find prospect ID by phone (normalized 10-digit US match).

        Strips non-digit characters and US country code prefix from both
        the input and stored values before comparing.
        """
        conn = self._get_connection()
        # Normalize input to digits, strip US country code
        digits = "".join(c for c in phone if c.isdigit())
        if not digits:
            return None
        if len(digits) == 11 and digits.startswith("1"):
            digits = digits[1:]
        # SQLite doesn't have a regex replace, so we fetch phone methods and compare in Python
        rows = conn.execute(
            "SELECT prospect_id, value FROM contact_methods WHERE type = 'phone'"
        ).fetchall()
        for row in rows:
            stored_digits = "".join(c for c in row["value"] if c.isdigit())
            if len(stored_digits) == 11 and stored_digits.startswith("1"):
                stored_digits = stored_digits[1:]
            if stored_digits == digits:
                return int(row["prospect_id"])
        return None

    def is_dnc(self, email: Optional[str] = None, phone: Optional[str] = None) -> bool:
        """Check if email or phone belongs to a DNC prospect."""
        if email:
            prospect_id = self.find_prospect_by_email(email)
            if prospect_id is not None:
                prospect = self.get_prospect(prospect_id)
                if prospect and prospect.population == Population.DEAD_DNC:
                    return True

        if phone:
            prospect_id = self.find_prospect_by_phone(phone)
            if prospect_id is not None:
                prospect = self.get_prospect(prospect_id)
                if prospect and prospect.population == Population.DEAD_DNC:
                    return True

        return False

    # =========================================================================
    # ACTIVITY OPERATIONS
    # =========================================================================

    def create_activity(self, activity: Activity) -> int:
        """Log an activity."""
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                """INSERT INTO activities
                   (prospect_id, activity_type, outcome, call_duration_seconds,
                    population_before, population_after, stage_before, stage_after,
                    email_subject, email_body, follow_up_set, attempt_type,
                    notes, created_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    activity.prospect_id,
                    (
                        activity.activity_type.value
                        if isinstance(activity.activity_type, ActivityType)
                        else activity.activity_type
                    ),
                    activity.outcome.value if activity.outcome else None,
                    activity.call_duration_seconds,
                    activity.population_before.value if activity.population_before else None,
                    activity.population_after.value if activity.population_after else None,
                    activity.stage_before.value if activity.stage_before else None,
                    activity.stage_after.value if activity.stage_after else None,
                    activity.email_subject,
                    activity.email_body,
                    activity.follow_up_set,
                    activity.attempt_type.value if activity.attempt_type else None,
                    activity.notes,
                    activity.created_by,
                ),
            )
            conn.commit()
            return self._lastrowid(cursor)
        except sqlite3.Error as e:
            conn.rollback()
            raise DatabaseError(f"Failed to create activity: {e}") from e

    def get_activities(self, prospect_id: int, limit: int = 50) -> list[Activity]:
        """Get activities for prospect, most recent first."""
        conn = self._get_connection()
        rows = conn.execute(
            "SELECT * FROM activities WHERE prospect_id = ? ORDER BY created_at DESC LIMIT ?",
            (prospect_id, limit),
        ).fetchall()
        return [self._row_to_activity(row) for row in rows]

    # =========================================================================
    # REMAINING TABLE OPERATIONS
    # =========================================================================

    def create_data_freshness(
        self,
        prospect_id: int,
        field_name: str,
        verified_date: date,
        verification_method: Optional[str] = None,
        confidence: Optional[int] = None,
        previous_value: Optional[str] = None,
    ) -> int:
        """Create a data freshness record."""
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                """INSERT INTO data_freshness
                   (prospect_id, field_name, verified_date, verification_method, confidence, previous_value)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    prospect_id,
                    field_name,
                    verified_date,
                    verification_method,
                    confidence,
                    previous_value,
                ),
            )
            conn.commit()
            return self._lastrowid(cursor)
        except sqlite3.Error as e:
            conn.rollback()
            raise DatabaseError(f"Failed to create data freshness: {e}") from e

    def get_data_freshness(self, prospect_id: int) -> list[dict[str, Any]]:
        """Get all data freshness records for a prospect."""
        conn = self._get_connection()
        rows = conn.execute(
            "SELECT * FROM data_freshness WHERE prospect_id = ? ORDER BY verified_date DESC",
            (prospect_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def get_latest_data_freshness(
        self, prospect_id: int, field_name: str
    ) -> Optional[dict[str, Any]]:
        """Get the most recent data-freshness record for a specific field.

        Used by the nightly cycle to check last-run timestamps.
        """
        conn = self._get_connection()
        row = conn.execute(
            "SELECT * FROM data_freshness WHERE prospect_id = ? AND field_name = ? "
            "ORDER BY verified_date DESC LIMIT 1",
            (prospect_id, field_name),
        ).fetchone()
        return dict(row) if row else None

    def get_recent_activities_with_notes(
        self, since: str, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Get recent activities that have meaningful notes.

        Args:
            since: ISO datetime string lower-bound for created_at
            limit: Max rows to return

        Returns:
            List of row dicts with id, prospect_id, notes, activity_type
        """
        conn = self._get_connection()
        rows = conn.execute(
            """SELECT id, prospect_id, notes, activity_type
               FROM activities
               WHERE created_at >= ?
               AND notes IS NOT NULL
               AND LENGTH(notes) > 20
               ORDER BY created_at DESC
               LIMIT ?""",
            (since, limit),
        ).fetchall()
        return [dict(row) for row in rows]

    def create_import_source(self, source: ImportSource) -> int:
        """Create an import source record."""
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                """INSERT INTO import_sources
                   (source_name, filename, total_records, imported_records,
                    duplicate_records, broken_records, dnc_blocked_records)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    source.source_name,
                    source.filename,
                    source.total_records,
                    source.imported_records,
                    source.duplicate_records,
                    source.broken_records,
                    source.dnc_blocked_records,
                ),
            )
            conn.commit()
            return self._lastrowid(cursor)
        except sqlite3.Error as e:
            conn.rollback()
            raise DatabaseError(f"Failed to create import source: {e}") from e

    def get_import_sources(self, limit: int = 50) -> list[ImportSource]:
        """Get import sources, most recent first."""
        conn = self._get_connection()
        rows = conn.execute(
            "SELECT * FROM import_sources ORDER BY import_date DESC LIMIT ?", (limit,)
        ).fetchall()
        result = []
        for row in rows:
            result.append(
                ImportSource(
                    id=row["id"],
                    source_name=row["source_name"],
                    filename=row["filename"],
                    total_records=row["total_records"] or 0,
                    imported_records=row["imported_records"] or 0,
                    duplicate_records=row["duplicate_records"] or 0,
                    broken_records=row["broken_records"] or 0,
                    dnc_blocked_records=row["dnc_blocked_records"] or 0,
                    import_date=row["import_date"],
                )
            )
        return result

    def create_research_task(self, task: ResearchTask) -> int:
        """Create a research queue entry."""
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                """INSERT INTO research_queue
                   (prospect_id, priority, status, attempts, last_attempt_date, findings)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    task.prospect_id,
                    task.priority,
                    task.status.value if isinstance(task.status, ResearchStatus) else task.status,
                    task.attempts,
                    task.last_attempt_date,
                    task.findings,
                ),
            )
            conn.commit()
            return self._lastrowid(cursor)
        except sqlite3.Error as e:
            conn.rollback()
            raise DatabaseError(f"Failed to create research task: {e}") from e

    def get_research_tasks(
        self, status: Optional[str] = None, limit: int = 50
    ) -> list[ResearchTask]:
        """Get research tasks, optionally filtered by status."""
        conn = self._get_connection()
        if status:
            rows = conn.execute(
                "SELECT * FROM research_queue WHERE status = ? ORDER BY priority DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM research_queue ORDER BY priority DESC LIMIT ?", (limit,)
            ).fetchall()
        result = []
        for row in rows:
            result.append(
                ResearchTask(
                    id=row["id"],
                    prospect_id=row["prospect_id"],
                    priority=row["priority"] or 0,
                    status=(
                        ResearchStatus(row["status"]) if row["status"] else ResearchStatus.PENDING
                    ),
                    attempts=row["attempts"] or 0,
                    last_attempt_date=row["last_attempt_date"],
                    findings=row["findings"],
                )
            )
        return result

    def create_intel_nugget(self, nugget: IntelNugget) -> int:
        """Create an intel nugget."""
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                """INSERT INTO intel_nuggets
                   (prospect_id, category, content, source_activity_id)
                   VALUES (?, ?, ?, ?)""",
                (
                    nugget.prospect_id,
                    (
                        nugget.category.value
                        if isinstance(nugget.category, IntelCategory)
                        else nugget.category
                    ),
                    nugget.content,
                    nugget.source_activity_id,
                ),
            )
            conn.commit()
            return self._lastrowid(cursor)
        except sqlite3.Error as e:
            conn.rollback()
            raise DatabaseError(f"Failed to create intel nugget: {e}") from e

    def get_intel_nuggets(self, prospect_id: int) -> list[IntelNugget]:
        """Get intel nuggets for prospect."""
        conn = self._get_connection()
        rows = conn.execute(
            "SELECT * FROM intel_nuggets WHERE prospect_id = ? ORDER BY extracted_date DESC",
            (prospect_id,),
        ).fetchall()
        result = []
        for row in rows:
            result.append(
                IntelNugget(
                    id=row["id"],
                    prospect_id=row["prospect_id"],
                    category=(
                        IntelCategory(row["category"])
                        if row["category"]
                        else IntelCategory.KEY_FACT
                    ),
                    content=row["content"],
                    source_activity_id=row["source_activity_id"],
                    extracted_date=row["extracted_date"],
                )
            )
        return result

    # =========================================================================
    # BULK OPERATIONS
    # =========================================================================

    def bulk_update_population(
        self,
        prospect_ids: list[int],
        population: Population,
        reason: str,
    ) -> tuple[int, int, int]:
        """Update population for multiple prospects.

        DNC records are skipped, not modified.
        Invalid transitions (per population rules) are skipped.

        Returns:
            Tuple of (updated_count, skipped_dnc_count, skipped_invalid_count)
        """
        from src.engine.populations import can_transition

        conn = self._get_connection()
        updated = 0
        skipped_dnc = 0
        skipped_invalid = 0

        for pid in prospect_ids:
            prospect = self.get_prospect(pid)
            if prospect is None:
                continue
            if prospect.population == Population.DEAD_DNC:
                skipped_dnc += 1
                continue

            old_pop = prospect.population
            if not can_transition(old_pop, population):
                skipped_invalid += 1
                logger.warning(
                    "Bulk update skipped invalid transition",
                    extra={
                        "context": {
                            "prospect_id": pid,
                            "from": old_pop.value,
                            "to": population.value,
                        }
                    },
                )
                continue

            try:
                conn.execute(
                    "UPDATE prospects SET population = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (population.value, pid),
                )
                # Log activity for each transition
                conn.execute(
                    """INSERT INTO activities
                       (prospect_id, activity_type, population_before, population_after,
                        notes, created_by)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        pid,
                        ActivityType.STATUS_CHANGE.value,
                        old_pop.value,
                        population.value,
                        reason,
                        "user",
                    ),
                )
                updated += 1
            except sqlite3.Error:
                continue

        conn.commit()
        return (updated, skipped_dnc, skipped_invalid)

    def bulk_set_follow_up(
        self,
        prospect_ids: list[int],
        follow_up_date: datetime,
    ) -> int:
        """Set follow-up date for multiple prospects."""
        conn = self._get_connection()
        updated = 0
        for pid in prospect_ids:
            try:
                cursor = conn.execute(
                    "UPDATE prospects SET follow_up_date = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (follow_up_date, pid),
                )
                if cursor.rowcount > 0:
                    updated += 1
            except sqlite3.Error:
                continue
        conn.commit()
        return updated

    def bulk_park(
        self,
        prospect_ids: list[int],
        parked_month: str,
    ) -> tuple[int, int, int]:
        """Park prospects in a month (YYYY-MM).

        Invalid transitions (per population rules) are skipped.

        Returns:
            Tuple of (parked_count, skipped_dnc_count, skipped_invalid_count)
        """
        from src.engine.populations import can_transition

        conn = self._get_connection()
        parked = 0
        skipped_dnc = 0
        skipped_invalid = 0

        for pid in prospect_ids:
            prospect = self.get_prospect(pid)
            if prospect is None:
                continue
            if prospect.population == Population.DEAD_DNC:
                skipped_dnc += 1
                continue

            old_pop = prospect.population
            if not can_transition(old_pop, Population.PARKED):
                skipped_invalid += 1
                logger.warning(
                    "Bulk park skipped invalid transition",
                    extra={
                        "context": {
                            "prospect_id": pid,
                            "from": old_pop.value,
                        }
                    },
                )
                continue

            try:
                conn.execute(
                    """UPDATE prospects SET
                       population = ?, parked_month = ?, updated_at = CURRENT_TIMESTAMP
                       WHERE id = ?""",
                    (Population.PARKED.value, parked_month, pid),
                )
                conn.execute(
                    """INSERT INTO activities
                       (prospect_id, activity_type, population_before, population_after,
                        notes, created_by)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        pid,
                        ActivityType.STATUS_CHANGE.value,
                        old_pop.value,
                        Population.PARKED.value,
                        f"Parked until {parked_month}",
                        "user",
                    ),
                )
                parked += 1
            except sqlite3.Error:
                continue

        conn.commit()
        return (parked, skipped_dnc, skipped_invalid)

    # =========================================================================
    # TAG OPERATIONS
    # =========================================================================

    def add_tag(self, prospect_id: int, tag_name: str) -> bool:
        """Add tag to prospect. Returns True if added (False if already exists)."""
        conn = self._get_connection()
        try:
            conn.execute(
                "INSERT OR IGNORE INTO prospect_tags (prospect_id, tag_name) VALUES (?, ?)",
                (prospect_id, tag_name),
            )
            conn.commit()
            return True
        except sqlite3.Error:
            return False

    def remove_tag(self, prospect_id: int, tag_name: str) -> bool:
        """Remove tag from prospect."""
        conn = self._get_connection()
        cursor = conn.execute(
            "DELETE FROM prospect_tags WHERE prospect_id = ? AND tag_name = ?",
            (prospect_id, tag_name),
        )
        conn.commit()
        return cursor.rowcount > 0

    def get_tags(self, prospect_id: int) -> list[str]:
        """Get all tags for prospect."""
        conn = self._get_connection()
        rows = conn.execute(
            "SELECT tag_name FROM prospect_tags WHERE prospect_id = ? ORDER BY tag_name",
            (prospect_id,),
        ).fetchall()
        return [row["tag_name"] for row in rows]

    def get_all_tags(self) -> list[str]:
        """Get all unique tags in system."""
        conn = self._get_connection()
        rows = conn.execute(
            "SELECT DISTINCT tag_name FROM prospect_tags ORDER BY tag_name"
        ).fetchall()
        return [row["tag_name"] for row in rows]
