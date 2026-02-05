# ADR 001: SQLite Over PostgreSQL

## Status

Accepted

## Date

February 5, 2026

## Context

IronLung 3 needs a database to store prospects, companies, activities, and related data. The system is a single-user Windows desktop application used by one sales professional (Jeff).

Options considered:
1. **PostgreSQL** - Full-featured relational database
2. **SQLite** - Embedded single-file database
3. **MongoDB** - Document database
4. **Flat files (JSON/CSV)** - File-based storage

## Decision

We will use **SQLite** as the database.

## Rationale

### Why SQLite

1. **Zero infrastructure**: No server to install, configure, or maintain. Database is a single file.

2. **Ships with Python**: `sqlite3` module is built into Python stdlib. No additional dependencies.

3. **Local-first**: All data stays on Jeff's machine. No network latency for queries.

4. **Performance**: SQLite handles 300,000+ records without blinking. Jeff's dataset is 300-400 contacts.

5. **Backup simplicity**: Backup = copy the file. Restore = replace the file.

6. **WAL mode**: Write-Ahead Logging provides concurrent read/write without locking issues.

7. **Proven**: SQLite powers iOS, Android, browsers, and countless desktop apps.

### Why Not PostgreSQL

- Requires server installation and maintenance
- Overkill for single-user desktop app
- Network dependency even for local operations
- Backup/restore more complex

### Why Not MongoDB

- Document model doesn't fit relational prospect/company data well
- Requires server installation
- Query patterns are SQL-friendly

### Why Not Flat Files

- Would require building query/filter logic manually
- Poor performance as data grows
- No transaction support
- No referential integrity

## Consequences

### Positive

- Simpler deployment: just distribute the app
- Simpler operations: no database admin required
- Fast queries: no network round-trips
- Easy backup: file copy to OneDrive

### Negative

- No multi-user support (not needed)
- No network access (could add REST API later if needed)
- Limited concurrent write performance (single-user, not an issue)

### Risks

- **Data loss if laptop dies**: Mitigated by nightly backups to OneDrive
- **Schema migrations**: Handled via `schema_version` table and migration scripts

## Related

- ADR 002: tkinter Over Electron (similar "simple is better" philosophy)
- `../SCHEMA-SPEC.md` - Complete schema definition
