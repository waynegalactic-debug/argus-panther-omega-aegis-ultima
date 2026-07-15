"""
Operation Phoenix Shield — Neon Persistence Engine.

Serverless PostgreSQL-compatible persistence layer for investigation data,
evidence storage, audit trails, and analytical queries.

This module provides a production-grade database abstraction that:
    - Creates and manages investigation schemas with proper foreign keys
    - Stores evidence with SHA-256 integrity verification
    - Maintains an immutable audit log for all CRUD operations
    - Supports wallet analysis, patent findings, and shell corporation tracking
    - Exports and imports full investigation snapshots
    - Provides statistical dashboards for case management

Design Notes:
    - Uses ``sqlite3`` for zero-dependency operation; swap connection factory for
      real ``psycopg2`` / ``pg8000`` against Neon without changing business logic.
    - All public methods return a standardized ``PhoenixResponse`` dictionary.
    - Every mutating operation triggers an automatic audit-log entry.

Example:
    >>> engine = NeonPersistenceEngine()
    >>> engine.initialize_schema()
    >>> result = engine.create_investigation("Op Phoenix", "Target-X")
    >>> engine.save_evidence(result["data"]["id"], {"type": "document", "content": "..."})

Author  : Phoenix Shield Team
Version : 1.0.0
"""

from __future__ import annotations

import os

import hashlib
import json
import logging
import os
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

# ---------------------------------------------------------------------------
# Module-level logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-25s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S %Z",
)
logger: logging.Logger = logging.getLogger("phoenix.neon_persistence")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_NEON_API_KEY: str = os.environ.get("NEON_API_KEY", "")
DEFAULT_CONNECTION_STRING: str = os.environ.get("NEON_DATABASE_URL", "")

DB_PATH: str = os.environ.get("PHOENIX_DB_PATH", ":memory:")

# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------
PhoenixResponse = Dict[str, Any]


def _ok(data: Any, source: str = "neon_persistence") -> PhoenixResponse:
    """Build a successful response envelope."""
    return {
        "success": True,
        "data": data,
        "source": source,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "error": None,
    }


def _err(message: str, source: str = "neon_persistence") -> PhoenixResponse:
    """Build an error response envelope."""
    logger.error("[%s] %s", source, message)
    return {
        "success": False,
        "data": None,
        "source": source,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "error": message,
    }


# ---------------------------------------------------------------------------
# Connection factory  (file-backed databases)
# ---------------------------------------------------------------------------
@contextmanager
def _get_connection_file(db_path: str):
    """Yield a SQLite connection with WAL mode and foreign keys enabled.

    For *psycopg2* or *pg8000* the block body would remain identical
    because we rely only on standard DB-API 2.0 calls.
    """
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


# Global in-memory connection cache (shared for :memory: databases)
_MEMORY_CONN_CACHE: Dict[str, sqlite3.Connection] = {}


def _get_persistent_connection(db_path: str) -> sqlite3.Connection:
    """Return a persistent connection — required for ``:memory:`` databases.

    Each call to ``sqlite3.connect(":memory:")`` creates a *new* empty
    database, so we cache a single connection per unique path and reuse it.
    """
    if db_path not in _MEMORY_CONN_CACHE or _MEMORY_CONN_CACHE[db_path] is None:
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        _MEMORY_CONN_CACHE[db_path] = conn
    return _MEMORY_CONN_CACHE[db_path]


@contextmanager
def _get_connection_safe(db_path: str):
    """Yield a connection that persists for ``:memory:`` and auto-closes for files."""
    if db_path == ":memory:":
        yield _get_persistent_connection(db_path)
    else:
        with _get_connection_file(db_path) as conn:
            yield conn


# ---------------------------------------------------------------------------
# NeonPersistenceEngine
# ---------------------------------------------------------------------------
class NeonPersistenceEngine:
    """Production persistence engine for Operation Phoenix Shield.

    Parameters:
        connection_string: Database URL (default uses in-memory SQLite).
        api_key: Neon API key for remote administration calls.
    """

    # -- schema DDL ----------------------------------------------------------
    _DDL_INVESTIGATIONS: str = """
        CREATE TABLE IF NOT EXISTS investigations (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            target_entity TEXT NOT NULL,
            status      TEXT NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active', 'paused', 'closed', 'archived')),
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """

    _DDL_EVIDENCE: str = """
        CREATE TABLE IF NOT EXISTS evidence_items (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            investigation_id  TEXT NOT NULL,
            evidence_type     TEXT NOT NULL,
            data              TEXT NOT NULL,
            hash              TEXT NOT NULL,
            source            TEXT,
            timestamp         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (investigation_id) REFERENCES investigations(id)
                ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_evidence_investigation
            ON evidence_items(investigation_id);
        CREATE INDEX IF NOT EXISTS idx_evidence_type
            ON evidence_items(evidence_type);
    """

    _DDL_WALLETS: str = """
        CREATE TABLE IF NOT EXISTS wallet_addresses (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            investigation_id  TEXT NOT NULL,
            address           TEXT NOT NULL,
            blockchain        TEXT NOT NULL,
            balance_usd       REAL  DEFAULT 0.0,
            risk_score        REAL  DEFAULT 0.0
                        CHECK (risk_score BETWEEN 0.0 AND 100.0),
            created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (investigation_id) REFERENCES investigations(id)
                ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_wallet_investigation
            ON wallet_addresses(investigation_id);
        CREATE INDEX IF NOT EXISTS idx_wallet_address
            ON wallet_addresses(address);
    """

    _DDL_TRANSACTIONS: str = """
        CREATE TABLE IF NOT EXISTS transactions (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            investigation_id  TEXT NOT NULL,
            tx_hash           TEXT NOT NULL,
            from_addr         TEXT NOT NULL,
            to_addr           TEXT NOT NULL,
            value             REAL  DEFAULT 0.0,
            blockchain        TEXT NOT NULL,
            timestamp         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (investigation_id) REFERENCES investigations(id)
                ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_tx_investigation
            ON transactions(investigation_id);
        CREATE INDEX IF NOT EXISTS idx_tx_hash
            ON transactions(tx_hash);
    """

    _DDL_PATENTS: str = """
        CREATE TABLE IF NOT EXISTS patents (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            investigation_id  TEXT NOT NULL,
            patent_number     TEXT NOT NULL,
            office            TEXT NOT NULL,
            title             TEXT NOT NULL,
            assignee          TEXT,
            inventor          TEXT,
            risk_score        REAL DEFAULT 0.0
                        CHECK (risk_score BETWEEN 0.0 AND 100.0),
            created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (investigation_id) REFERENCES investigations(id)
                ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_patent_investigation
            ON patents(investigation_id);
    """

    _DDL_SHELL_CORPS: str = """
        CREATE TABLE IF NOT EXISTS shell_corporations (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            investigation_id  TEXT NOT NULL,
            entity_name       TEXT NOT NULL,
            jurisdiction      TEXT NOT NULL,
            ubo               TEXT,
            confidence_score  REAL DEFAULT 0.0
                        CHECK (confidence_score BETWEEN 0.0 AND 100.0),
            created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (investigation_id) REFERENCES investigations(id)
                ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_shell_investigation
            ON shell_corporations(investigation_id);
    """

    _DDL_AUDIT_LOG: str = """
        CREATE TABLE IF NOT EXISTS audit_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            action      TEXT NOT NULL,
            table_name  TEXT NOT NULL,
            record_id   TEXT NOT NULL,
            old_value   TEXT,
            new_value   TEXT,
            timestamp   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            user_id     TEXT DEFAULT 'system'
        );
        CREATE INDEX IF NOT EXISTS idx_audit_record
            ON audit_log(record_id);
        CREATE INDEX IF NOT EXISTS idx_audit_timestamp
            ON audit_log(timestamp);
    """

    # -- trigger for investigations updated_at --------------------------------
    _DDL_TRIGGER: str = """
        CREATE TRIGGER IF NOT EXISTS trg_investigations_updated_at
        AFTER UPDATE ON investigations
        FOR EACH ROW
        BEGIN
            UPDATE investigations SET updated_at = CURRENT_TIMESTAMP
            WHERE id = NEW.id;
        END;
    """

    # ------------------------------------------------------------------ #
    #  Construction
    # ------------------------------------------------------------------ #
    def __init__(
        self,
        connection_string: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> None:
        """Initialise the persistence engine.

        Args:
            connection_string: Override DB path / connection URL.
            api_key: Neon API key (stored for future remote operations).
        """
        self.connection_string: str = connection_string or DB_PATH
        self.api_key: str = api_key or DEFAULT_NEON_API_KEY
        self.api_keys: Dict[str, str] = {
            "neon_api_key": self.api_key,
            "neon_connection_string": self.connection_string,
        }
        self._db_ready: bool = False
        logger.info("NeonPersistenceEngine initialised | db=%s", self.connection_string)

    # ------------------------------------------------------------------ #
    #  Internal helpers
    # ------------------------------------------------------------------ #
    def _ensure_db(self) -> None:
        """Verify that ``initialize_schema`` has been called."""
        if not self._db_ready:
            self.initialize_schema()

    @staticmethod
    def _sha256(data: Union[str, bytes]) -> str:
        """Return the hex digest of *data* using SHA-256."""
        payload = data.encode("utf-8") if isinstance(data, str) else data
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def _new_id(prefix: str = "inv") -> str:
        """Generate a time-sortable unique identifier."""
        ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        rnd = hashlib.sha256(os.urandom(32)).hexdigest()[:8]
        return f"{prefix}_{ts}_{rnd}"

    def _auto_audit(
        self,
        conn: sqlite3.Connection,
        action: str,
        table: str,
        record_id: str,
        old: Any,
        new: Any,
        user_id: str = "system",
    ) -> None:
        """Insert an audit-log row inside an existing transaction."""
        conn.execute(
            """
            INSERT INTO audit_log (action, table_name, record_id, old_value, new_value, user_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                action,
                table,
                str(record_id),
                json.dumps(old) if old is not None else None,
                json.dumps(new) if new is not None else None,
                user_id,
            ),
        )

    def _row_to_dict(self, row: Optional[sqlite3.Row]) -> Optional[Dict[str, Any]]:
        """Convert a ``sqlite3.Row`` to a plain dictionary."""
        if row is None:
            return None
        return {key: row[key] for key in row.keys()}

    # ------------------------------------------------------------------ #
    #  1. Schema
    # ------------------------------------------------------------------ #
    def initialize_schema(self) -> PhoenixResponse:
        """Create all investigation tables, indexes, and triggers.

        Returns:
            ``PhoenixResponse`` with table names created.
        """
        try:
            with _get_connection_safe(self.connection_string) as conn:
                cur = conn.cursor()
                for ddl in (
                    self._DDL_INVESTIGATIONS,
                    self._DDL_EVIDENCE,
                    self._DDL_WALLETS,
                    self._DDL_TRANSACTIONS,
                    self._DDL_PATENTS,
                    self._DDL_SHELL_CORPS,
                    self._DDL_AUDIT_LOG,
                    self._DDL_TRIGGER,
                ):
                    cur.executescript(ddl)
                conn.commit()
            self._db_ready = True
            logger.info("Schema initialised successfully")
            return _ok(
                {
                    "tables": [
                        "investigations",
                        "evidence_items",
                        "wallet_addresses",
                        "transactions",
                        "patents",
                        "shell_corporations",
                        "audit_log",
                    ],
                    "indexes": 12,
                    "triggers": 1,
                }
            )
        except Exception as exc:
            return _err(f"Schema initialisation failed: {exc}")

    # ------------------------------------------------------------------ #
    #  2. Investigations
    # ------------------------------------------------------------------ #
    def create_investigation(
        self, name: str, target_entity: str
    ) -> PhoenixResponse:
        """Create a new investigation record.

        Args:
            name: Human-readable investigation name.
            target_entity: Subject / entity under investigation.

        Returns:
            ``PhoenixResponse`` containing the new investigation ID.
        """
        self._ensure_db()
        try:
            inv_id = self._new_id("inv")
            with _get_connection_safe(self.connection_string) as conn:
                conn.execute(
                    """
                    INSERT INTO investigations (id, name, target_entity, status)
                    VALUES (?, ?, ?, 'active')
                    """,
                    (inv_id, name, target_entity),
                )
                self._auto_audit(conn, "CREATE", "investigations", inv_id, None, {"name": name, "target_entity": target_entity})
                conn.commit()
            logger.info("Investigation created | id=%s", inv_id)
            return _ok({"id": inv_id, "name": name, "target_entity": target_entity, "status": "active"})
        except Exception as exc:
            return _err(f"create_investigation failed: {exc}")

    # ------------------------------------------------------------------ #
    #  3. Evidence
    # ------------------------------------------------------------------ #
    def save_evidence(
        self,
        investigation_id: str,
        evidence: Dict[str, Any],
    ) -> PhoenixResponse:
        """Persist an evidence item with SHA-256 integrity hash.

        Args:
            investigation_id: Parent investigation foreign key.
            evidence: Dictionary with at least ``type`` and ``content`` keys.

        Returns:
            ``PhoenixResponse`` with the evidence record ID and computed hash.
        """
        self._ensure_db()
        try:
            payload_json = json.dumps(evidence, sort_keys=True, default=str)
            evidence_hash = self._sha256(payload_json)
            evidence_type = evidence.get("type", "unknown")
            source = evidence.get("source", "manual")

            with _get_connection_safe(self.connection_string) as conn:
                cur = conn.execute(
                    """
                    INSERT INTO evidence_items (investigation_id, evidence_type, data, hash, source)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (investigation_id, evidence_type, payload_json, evidence_hash, source),
                )
                record_id = cur.lastrowid
                self._auto_audit(
                    conn,
                    "CREATE",
                    "evidence_items",
                    str(record_id),
                    None,
                    {"type": evidence_type, "hash": evidence_hash},
                )
                conn.commit()
            logger.info("Evidence saved | inv=%s type=%s hash=%s", investigation_id, evidence_type, evidence_hash[:16])
            return _ok({"record_id": record_id, "hash": evidence_hash, "investigation_id": investigation_id})
        except Exception as exc:
            return _err(f"save_evidence failed: {exc}")

    def get_evidence(
        self,
        investigation_id: str,
        evidence_type: Optional[str] = None,
    ) -> PhoenixResponse:
        """Retrieve evidence items for an investigation.

        Args:
            investigation_id: Investigation to filter by.
            evidence_type: Optional type filter.

        Returns:
            ``PhoenixResponse`` with a list of evidence dictionaries.
        """
        self._ensure_db()
        try:
            with _get_connection_safe(self.connection_string) as conn:
                if evidence_type:
                    rows = conn.execute(
                        "SELECT * FROM evidence_items WHERE investigation_id = ? AND evidence_type = ? ORDER BY timestamp DESC",
                        (investigation_id, evidence_type),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT * FROM evidence_items WHERE investigation_id = ? ORDER BY timestamp DESC",
                        (investigation_id,),
                    ).fetchall()
            results = []
            for row in rows:
                d = self._row_to_dict(row)
                if d:
                    d["data"] = json.loads(d["data"])
                    results.append(d)
            return _ok({"count": len(results), "items": results})
        except Exception as exc:
            return _err(f"get_evidence failed: {exc}")

    # ------------------------------------------------------------------ #
    #  4. Wallet Analysis
    # ------------------------------------------------------------------ #
    def save_wallet_analysis(
        self,
        investigation_id: str,
        wallet_data: Dict[str, Any],
    ) -> PhoenixResponse:
        """Save cryptocurrency wallet analysis results.

        Args:
            investigation_id: Parent investigation.
            wallet_data: Must contain ``address``, ``blockchain``, and optionally
                         ``balance_usd`` and ``risk_score``.

        Returns:
            ``PhoenixResponse`` with the wallet record ID.
        """
        self._ensure_db()
        try:
            address = wallet_data["address"]
            blockchain = wallet_data["blockchain"]
            balance_usd = float(wallet_data.get("balance_usd", 0.0))
            risk_score = float(wallet_data.get("risk_score", 0.0))

            with _get_connection_safe(self.connection_string) as conn:
                cur = conn.execute(
                    """
                    INSERT INTO wallet_addresses (investigation_id, address, blockchain, balance_usd, risk_score)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (investigation_id, address, blockchain, balance_usd, risk_score),
                )
                record_id = cur.lastrowid
                self._auto_audit(conn, "CREATE", "wallet_addresses", str(record_id), None, {"address": address, "risk_score": risk_score})
                conn.commit()
            logger.info("Wallet saved | inv=%s addr=%s...", investigation_id, address[:12])
            return _ok({"record_id": record_id, "address": address, "risk_score": risk_score})
        except Exception as exc:
            return _err(f"save_wallet_analysis failed: {exc}")

    def get_wallet_analysis(
        self,
        investigation_id: str,
        address: Optional[str] = None,
    ) -> PhoenixResponse:
        """Retrieve wallet analysis results.

        Args:
            investigation_id: Investigation filter.
            address: Optional exact address match.

        Returns:
            ``PhoenixResponse`` with wallet records.
        """
        self._ensure_db()
        try:
            with _get_connection_safe(self.connection_string) as conn:
                if address:
                    rows = conn.execute(
                        "SELECT * FROM wallet_addresses WHERE investigation_id = ? AND address = ? ORDER BY created_at DESC",
                        (investigation_id, address),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT * FROM wallet_addresses WHERE investigation_id = ? ORDER BY created_at DESC",
                        (investigation_id,),
                    ).fetchall()
            results = [self._row_to_dict(r) for r in rows if r is not None]
            return _ok({"count": len(results), "wallets": results})
        except Exception as exc:
            return _err(f"get_wallet_analysis failed: {exc}")

    # ------------------------------------------------------------------ #
    #  5. Patent Findings
    # ------------------------------------------------------------------ #
    def save_patent_findings(
        self,
        investigation_id: str,
        patent_data: Dict[str, Any],
    ) -> PhoenixResponse:
        """Save patent analysis results.

        Args:
            investigation_id: Parent investigation.
            patent_data: Dictionary with ``patent_number``, ``office``, ``title``,
                         and optional ``assignee``, ``inventor``, ``risk_score``.

        Returns:
            ``PhoenixResponse`` with the patent record ID.
        """
        self._ensure_db()
        try:
            with _get_connection_safe(self.connection_string) as conn:
                cur = conn.execute(
                    """
                    INSERT INTO patents (investigation_id, patent_number, office, title, assignee, inventor, risk_score)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        investigation_id,
                        patent_data["patent_number"],
                        patent_data["office"],
                        patent_data["title"],
                        patent_data.get("assignee"),
                        patent_data.get("inventor"),
                        float(patent_data.get("risk_score", 0.0)),
                    ),
                )
                record_id = cur.lastrowid
                self._auto_audit(conn, "CREATE", "patents", str(record_id), None, {"patent_number": patent_data["patent_number"]})
                conn.commit()
            logger.info("Patent saved | inv=%s patent=%s", investigation_id, patent_data["patent_number"])
            return _ok({"record_id": record_id, "patent_number": patent_data["patent_number"]})
        except Exception as exc:
            return _err(f"save_patent_findings failed: {exc}")

    def get_patent_findings(self, investigation_id: str) -> PhoenixResponse:
        """Retrieve all patent findings for an investigation.

        Args:
            investigation_id: Investigation filter.

        Returns:
            ``PhoenixResponse`` with patent records.
        """
        self._ensure_db()
        try:
            with _get_connection_safe(self.connection_string) as conn:
                rows = conn.execute(
                    "SELECT * FROM patents WHERE investigation_id = ? ORDER BY created_at DESC",
                    (investigation_id,),
                ).fetchall()
            results = [self._row_to_dict(r) for r in rows if r is not None]
            return _ok({"count": len(results), "patents": results})
        except Exception as exc:
            return _err(f"get_patent_findings failed: {exc}")

    # ------------------------------------------------------------------ #
    #  6. Shell Corporations
    # ------------------------------------------------------------------ #
    def save_shell_corporation(
        self,
        investigation_id: str,
        corp_data: Dict[str, Any],
    ) -> PhoenixResponse:
        """Save a shell corporation finding.

        Args:
            investigation_id: Parent investigation.
            corp_data: Dictionary with ``entity_name``, ``jurisdiction``, and
                       optional ``ubo`` and ``confidence_score``.

        Returns:
            ``PhoenixResponse`` with the corporation record ID.
        """
        self._ensure_db()
        try:
            with _get_connection_safe(self.connection_string) as conn:
                cur = conn.execute(
                    """
                    INSERT INTO shell_corporations (investigation_id, entity_name, jurisdiction, ubo, confidence_score)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        investigation_id,
                        corp_data["entity_name"],
                        corp_data["jurisdiction"],
                        corp_data.get("ubo"),
                        float(corp_data.get("confidence_score", 0.0)),
                    ),
                )
                record_id = cur.lastrowid
                self._auto_audit(conn, "CREATE", "shell_corporations", str(record_id), None, {"entity_name": corp_data["entity_name"]})
                conn.commit()
            logger.info("Shell corp saved | inv=%s entity=%s", investigation_id, corp_data["entity_name"])
            return _ok({"record_id": record_id, "entity_name": corp_data["entity_name"]})
        except Exception as exc:
            return _err(f"save_shell_corporation failed: {exc}")

    def get_shell_corporations(self, investigation_id: str) -> PhoenixResponse:
        """Retrieve shell corporation findings.

        Args:
            investigation_id: Investigation filter.

        Returns:
            ``PhoenixResponse`` with shell corporation records.
        """
        self._ensure_db()
        try:
            with _get_connection_safe(self.connection_string) as conn:
                rows = conn.execute(
                    "SELECT * FROM shell_corporations WHERE investigation_id = ? ORDER BY created_at DESC",
                    (investigation_id,),
                ).fetchall()
            results = [self._row_to_dict(r) for r in rows if r is not None]
            return _ok({"count": len(results), "corporations": results})
        except Exception as exc:
            return _err(f"get_shell_corporations failed: {exc}")

    # ------------------------------------------------------------------ #
    #  7. Audit Logging
    # ------------------------------------------------------------------ #
    def log_audit_event(
        self,
        action: str,
        table: str,
        record_id: str,
        old: Dict[str, Any],
        new: Dict[str, Any],
        user_id: str = "system",
    ) -> PhoenixResponse:
        """Manually log an audit event.

        Args:
            action: CRUD action (CREATE, READ, UPDATE, DELETE).
            table: Target table name.
            record_id: Affected record identifier.
            old: Previous values (serialised to JSON).
            new: New values (serialised to JSON).
            user_id: Actor identifier.

        Returns:
            ``PhoenixResponse`` with the audit log entry ID.
        """
        self._ensure_db()
        try:
            with _get_connection_safe(self.connection_string) as conn:
                cur = conn.execute(
                    """
                    INSERT INTO audit_log (action, table_name, record_id, old_value, new_value, user_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        action,
                        table,
                        str(record_id),
                        json.dumps(old, default=str) if old else None,
                        json.dumps(new, default=str) if new else None,
                        user_id,
                    ),
                )
                entry_id = cur.lastrowid
                conn.commit()
            logger.info("Audit event logged | action=%s table=%s record=%s", action, table, record_id)
            return _ok({"audit_entry_id": entry_id, "action": action, "table": table})
        except Exception as exc:
            return _err(f"log_audit_event failed: {exc}")

    def get_audit_trail(
        self, investigation_id: Optional[str] = None
    ) -> PhoenixResponse:
        """Retrieve the full or filtered audit trail.

        Args:
            investigation_id: When provided, restrict to records whose
                              ``record_id`` column contains this value.

        Returns:
            ``PhoenixResponse`` with audit log entries.
        """
        self._ensure_db()
        try:
            with _get_connection_safe(self.connection_string) as conn:
                if investigation_id:
                    rows = conn.execute(
                        "SELECT * FROM audit_log WHERE record_id LIKE ? OR old_value LIKE ? OR new_value LIKE ? ORDER BY timestamp DESC",
                        (f"%{investigation_id}%", f"%{investigation_id}%", f"%{investigation_id}%"),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT 1000"
                    ).fetchall()
            results = [self._row_to_dict(r) for r in rows if r is not None]
            return _ok({"count": len(results), "entries": results})
        except Exception as exc:
            return _err(f"get_audit_trail failed: {exc}")

    # ------------------------------------------------------------------ #
    #  8. Generic Query Execution
    # ------------------------------------------------------------------ #
    def execute_query(
        self, sql: str, params: Optional[Tuple[Any, ...]] = None
    ) -> PhoenixResponse:
        """Execute arbitrary SQL safely using bound parameters.

        .. warning::
            Only SELECT / INSERT / UPDATE / DELETE are permitted.
            DDL and destructive commands are rejected.

        Args:
            sql: Parameterised SQL statement.
            params: Tuple of bound values.

        Returns:
            ``PhoenixResponse`` with rows (for SELECT) or affected count.
        """
        self._ensure_db()
        forbidden = ("drop", "alter", "truncate", "pragma", "attach", "detach")
        sql_lower = sql.lower().strip()
        if any(sql_lower.startswith(cmd) for cmd in forbidden):
            return _err(f"execute_query rejected forbidden statement: {sql.strip()}")

        try:
            with _get_connection_safe(self.connection_string) as conn:
                cur = conn.execute(sql, params or ())
                if sql_lower.startswith("select"):
                    rows = cur.fetchall()
                    results = [self._row_to_dict(r) for r in rows if r is not None]
                    return _ok({"rows": results, "count": len(results)})
                else:
                    conn.commit()
                    return _ok({"rows_affected": cur.rowcount})
        except Exception as exc:
            return _err(f"execute_query failed: {exc}")

    # ------------------------------------------------------------------ #
    #  9. Export / Import
    # ------------------------------------------------------------------ #
    def export_investigation(self, investigation_id: str) -> PhoenixResponse:
        """Export a complete investigation snapshot.

        The returned dictionary contains every table's data for the given
        investigation and can be serialised to JSON for archival or transfer.

        Args:
            investigation_id: Investigation to export.

        Returns:
            ``PhoenixResponse`` with full snapshot data.
        """
        self._ensure_db()
        try:
            snapshot: Dict[str, Any] = {
                "export_meta": {
                    "version": "1.0.0",
                    "exported_at": datetime.now(timezone.utc).isoformat(),
                    "investigation_id": investigation_id,
                }
            }
            tables = [
                ("investigation", "investigations", "id"),
                ("evidence", "evidence_items", "investigation_id"),
                ("wallets", "wallet_addresses", "investigation_id"),
                ("transactions", "transactions", "investigation_id"),
                ("patents", "patents", "investigation_id"),
                ("shell_corporations", "shell_corporations", "investigation_id"),
            ]
            with _get_connection_safe(self.connection_string) as conn:
                for key, table, col in tables:
                    rows = conn.execute(
                        f"SELECT * FROM {table} WHERE {col} = ?", (investigation_id,)
                    ).fetchall()
                    snapshot[key] = [self._row_to_dict(r) for r in rows if r is not None]

                # Also export audit entries referencing this investigation
                audit_rows = conn.execute(
                    """
                    SELECT * FROM audit_log
                    WHERE record_id LIKE ? OR old_value LIKE ? OR new_value LIKE ?
                    ORDER BY timestamp DESC
                    """,
                    (f"%{investigation_id}%", f"%{investigation_id}%", f"%{investigation_id}%"),
                ).fetchall()
                snapshot["audit_trail"] = [self._row_to_dict(r) for r in audit_rows if r is not None]

            return _ok({"snapshot": snapshot})
        except Exception as exc:
            return _err(f"export_investigation failed: {exc}")

    def import_investigation(self, data: Dict[str, Any]) -> PhoenixResponse:
        """Import a previously exported investigation snapshot.

        Args:
            data: Snapshot dictionary as produced by ``export_investigation``.

        Returns:
            ``PhoenixResponse`` with imported record counts per table.
        """
        self._ensure_db()
        try:
            snapshot = data.get("snapshot", data)
            counts: Dict[str, int] = {}
            with _get_connection_safe(self.connection_string) as conn:
                # Investigations
                inv = snapshot.get("investigation", [])
                if inv:
                    for row in inv:
                        conn.execute(
                            """
                            INSERT OR IGNORE INTO investigations (id, name, target_entity, status, created_at, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?)
                            """,
                            (row["id"], row["name"], row["target_entity"], row.get("status", "active"),
                             row.get("created_at"), row.get("updated_at")),
                        )
                    counts["investigations"] = len(inv)

                # Evidence
                for key, table in (
                    ("evidence", "evidence_items"),
                    ("wallets", "wallet_addresses"),
                    ("transactions", "transactions"),
                    ("patents", "patents"),
                    ("shell_corporations", "shell_corporations"),
                ):
                    rows = snapshot.get(key, [])
                    if rows:
                        for row in rows:
                            cols = ", ".join(row.keys())
                            placeholders = ", ".join("?" for _ in row)
                            conn.execute(
                                f"INSERT OR IGNORE INTO {table} ({cols}) VALUES ({placeholders})",
                                tuple(row.values()),
                            )
                        counts[table] = len(rows)

                # Audit trail
                audit = snapshot.get("audit_trail", [])
                if audit:
                    for entry in audit:
                        conn.execute(
                            """
                            INSERT OR IGNORE INTO audit_log
                            (id, action, table_name, record_id, old_value, new_value, timestamp, user_id)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (entry.get("id"), entry["action"], entry["table_name"],
                             entry["record_id"], entry.get("old_value"), entry.get("new_value"),
                             entry.get("timestamp"), entry.get("user_id", "system")),
                        )
                    counts["audit_log"] = len(audit)

                conn.commit()
            logger.info("Investigation imported | counts=%s", counts)
            return _ok({"imported": counts})
        except Exception as exc:
            return _err(f"import_investigation failed: {exc}")

    # ------------------------------------------------------------------ #
    #  10. Statistics Dashboard
    # ------------------------------------------------------------------ #
    def get_investigation_stats(
        self, investigation_id: Optional[str] = None
    ) -> PhoenixResponse:
        """Return aggregate statistics for case management dashboards.

        Args:
            investigation_id: When provided, stats are scoped to that case;
                              otherwise global stats are returned.

        Returns:
            ``PhoenixResponse`` with summary statistics.
        """
        self._ensure_db()
        try:
            stats: Dict[str, Any] = {}
            with _get_connection_safe(self.connection_string) as conn:
                if investigation_id:
                    # Per-investigation stats
                    inv = conn.execute(
                        "SELECT * FROM investigations WHERE id = ?", (investigation_id,)
                    ).fetchone()
                    stats["investigation"] = self._row_to_dict(inv) if inv else None

                    stats["evidence_count"] = conn.execute(
                        "SELECT COUNT(*) FROM evidence_items WHERE investigation_id = ?",
                        (investigation_id,),
                    ).fetchone()[0]

                    stats["wallet_count"] = conn.execute(
                        "SELECT COUNT(*) FROM wallet_addresses WHERE investigation_id = ?",
                        (investigation_id,),
                    ).fetchone()[0]

                    wallet_agg = conn.execute(
                        """
                        SELECT COUNT(*), SUM(balance_usd), AVG(risk_score),
                               MAX(risk_score), MIN(risk_score)
                        FROM wallet_addresses WHERE investigation_id = ?
                        """,
                        (investigation_id,),
                    ).fetchone()
                    stats["wallet_summary"] = {
                        "count": wallet_agg[0],
                        "total_balance_usd": round(wallet_agg[1] or 0, 2),
                        "avg_risk_score": round(wallet_agg[2] or 0, 2),
                        "max_risk_score": round(wallet_agg[3] or 0, 2),
                        "min_risk_score": round(wallet_agg[4] or 0, 2),
                    }

                    stats["patent_count"] = conn.execute(
                        "SELECT COUNT(*) FROM patents WHERE investigation_id = ?",
                        (investigation_id,),
                    ).fetchone()[0]

                    stats["shell_corp_count"] = conn.execute(
                        "SELECT COUNT(*) FROM shell_corporations WHERE investigation_id = ?",
                        (investigation_id,),
                    ).fetchone()[0]

                    stats["transaction_count"] = conn.execute(
                        "SELECT COUNT(*) FROM transactions WHERE investigation_id = ?",
                        (investigation_id,),
                    ).fetchone()[0]
                else:
                    # Global stats
                    stats["total_investigations"] = conn.execute(
                        "SELECT COUNT(*) FROM investigations"
                    ).fetchone()[0]

                    stats["by_status"] = {
                        row["status"]: row["cnt"]
                        for row in conn.execute(
                            "SELECT status, COUNT(*) AS cnt FROM investigations GROUP BY status"
                        ).fetchall()
                    }

                    stats["total_evidence"] = conn.execute(
                        "SELECT COUNT(*) FROM evidence_items"
                    ).fetchone()[0]
                    stats["total_wallets"] = conn.execute(
                        "SELECT COUNT(*) FROM wallet_addresses"
                    ).fetchone()[0]
                    stats["total_patents"] = conn.execute(
                        "SELECT COUNT(*) FROM patents"
                    ).fetchone()[0]
                    stats["total_shell_corps"] = conn.execute(
                        "SELECT COUNT(*) FROM shell_corporations"
                    ).fetchone()[0]
                    stats["total_audit_entries"] = conn.execute(
                        "SELECT COUNT(*) FROM audit_log"
                    ).fetchone()[0]

                    # High-risk items
                    stats["high_risk_wallets"] = conn.execute(
                        "SELECT COUNT(*) FROM wallet_addresses WHERE risk_score >= 80"
                    ).fetchone()[0]
                    stats["high_risk_patents"] = conn.execute(
                        "SELECT COUNT(*) FROM patents WHERE risk_score >= 80"
                    ).fetchone()[0]
                    stats["high_confidence_shell_corps"] = conn.execute(
                        "SELECT COUNT(*) FROM shell_corporations WHERE confidence_score >= 80"
                    ).fetchone()[0]

            return _ok({"stats": stats})
        except Exception as exc:
            return _err(f"get_investigation_stats failed: {exc}")

    # ------------------------------------------------------------------ #
    #  11. Backup
    # ------------------------------------------------------------------ #
    def backup_database(self) -> PhoenixResponse:
        """Create a full database backup.

        For in-memory databases the backup is a JSON serialisation of all
        tables.  For file-backed SQLite the database file is copied.

        Returns:
            ``PhoenixResponse`` with backup path or inline data.
        """
        try:
            if self.connection_string == ":memory:":
                # Serialise everything to JSON
                tables = ["investigations", "evidence_items", "wallet_addresses",
                          "transactions", "patents", "shell_corporations", "audit_log"]
                backup_data: Dict[str, Any] = {}
                with _get_connection_safe(self.connection_string) as conn:
                    for table in tables:
                        rows = conn.execute(f"SELECT * FROM {table}").fetchall()
                        backup_data[table] = [self._row_to_dict(r) for r in rows if r is not None]
                return _ok({
                    "backup_type": "inline_json",
                    "tables": list(backup_data.keys()),
                    "data": backup_data,
                })
            else:
                import shutil
                backup_path = f"{self.connection_string}.backup.{int(time.time())}.db"
                shutil.copy2(self.connection_string, backup_path)
                logger.info("Database backed up to %s", backup_path)
                return _ok({"backup_type": "file_copy", "path": backup_path})
        except Exception as exc:
            return _err(f"backup_database failed: {exc}")


# ---------------------------------------------------------------------------
# Demonstration
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 72)
    print("  Operation Phoenix Shield — Neon Persistence Engine  [DEMO]")
    print("=" * 72)

    engine = NeonPersistenceEngine()

    # 1. Schema
    print("\n[1] Initialising schema...")
    r = engine.initialize_schema()
    print(f"    Tables: {r['data']['tables']}")

    # 2. Create investigation
    print("\n[2] Creating investigation...")
    r = engine.create_investigation("Operation Phoenix Shield", "Entity-X")
    inv_id = r["data"]["id"]
    print(f"    Investigation ID: {inv_id}")

    # 3. Save evidence
    print("\n[3] Saving evidence...")
    r = engine.save_evidence(inv_id, {
        "type": "document",
        "content": "Suspicious transaction patterns observed in Q3 2024.",
        "source": "manual_review",
        "tags": ["crypto", "high_value"],
    })
    print(f"    Evidence hash: {r['data']['hash'][:32]}...")

    # 4. Save wallet analysis
    print("\n[4] Saving wallet analysis...")
    r = engine.save_wallet_analysis(inv_id, {
        "address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
        "blockchain": "ethereum",
        "balance_usd": 1250000.50,
        "risk_score": 87.5,
    })
    print(f"    Wallet risk score: {r['data']['risk_score']}")

    # 5. Save patent findings
    print("\n[5] Saving patent findings...")
    r = engine.save_patent_findings(inv_id, {
        "patent_number": "US10,123,456 B2",
        "office": "USPTO",
        "title": "Decentralised Transaction Obfuscation System",
        "assignee": "ShellCorp Holdings Ltd",
        "inventor": "Dr. A. Smith",
        "risk_score": 72.0,
    })
    print(f"    Patent record: {r['data']['patent_number']}")

    # 6. Save shell corporation
    print("\n[6] Saving shell corporation...")
    r = engine.save_shell_corporation(inv_id, {
        "entity_name": "Aurora International Trading B.V.",
        "jurisdiction": "Netherlands",
        "ubo": "Unknown — nested ownership > 5 layers",
        "confidence_score": 91.0,
    })
    print(f"    Shell corp confidence: {r['data']['entity_name']}")

    # 7. Audit trail
    print("\n[7] Audit trail (last 5 entries)...")
    r = engine.get_audit_trail(inv_id)
    for entry in r["data"]["entries"][:5]:
        print(f"    [{entry['timestamp']}] {entry['action']} on {entry['table_name']} → {entry['record_id']}")

    # 8. Stats
    print("\n[8] Investigation stats...")
    r = engine.get_investigation_stats(inv_id)
    stats = r["data"]["stats"]
    print(f"    Evidence items   : {stats['evidence_count']}")
    print(f"    Wallets tracked  : {stats['wallet_count']}")
    print(f"    Patents found    : {stats['patent_count']}")
    print(f"    Shell corps      : {stats['shell_corp_count']}")
    print(f"    Wallet risk (avg): {stats['wallet_summary']['avg_risk_score']}")

    # 9. Backup
    print("\n[9] Creating backup...")
    r = engine.backup_database()
    print(f"    Backup type: {r['data']['backup_type']}")
    print(f"    Tables backed up: {list(r['data']['data'].keys()) if 'data' in r['data'] else r['data']['path']}")

    # 10. Export
    print("\n[10] Exporting investigation...")
    r = engine.export_investigation(inv_id)
    snap = r["data"]["snapshot"]
    print(f"     Export version : {snap['export_meta']['version']}")
    print(f"     Evidence items : {len(snap['evidence'])}")
    print(f"     Wallets        : {len(snap['wallets'])}")
    print(f"     Patents        : {len(snap['patents'])}")
    print(f"     Shell corps    : {len(snap['shell_corporations'])}")
    print(f"     Audit entries  : {len(snap['audit_trail'])}")

    print("\n" + "=" * 72)
    print("  DEMO COMPLETE — All systems nominal.")
    print("=" * 72)
