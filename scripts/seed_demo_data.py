"""Create a small demo database for manual Phase 1 smoke checks."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.db.database import Database


def main() -> None:
    demo_dir = Path("data/demo")
    demo_dir.mkdir(parents=True, exist_ok=True)
    demo_db = demo_dir / "ironlung3_demo.db"

    db = Database(str(demo_db))
    db.initialize()
    conn = db._get_connection()

    conn.execute(
        """
        INSERT INTO companies (name, name_normalized, state, timezone)
        VALUES (?, ?, ?, ?)
        """,
        ("Acme Lending, LLC", "acme lending", "TX", "central"),
    )
    company_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    conn.execute(
        """
        INSERT INTO prospects (company_id, first_name, last_name, title, population)
        VALUES (?, ?, ?, ?, ?)
        """,
        (company_id, "Casey", "Jordan", "Branch Manager", "unengaged"),
    )

    conn.commit()
    db.close()

    print(f"Demo database ready: {demo_db}")


if __name__ == "__main__":
    main()
