"""Local autobiographical memory and slowly evolving self-state for Herbie."""

from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


IDENTITY_NAME = "Herbie"
LEARNING_RATE = 0.02
MAX_MEMORY_TEXT = 4000
DB_LOCK = threading.RLock()
DB_PATH = Path(
    os.environ.get(
        "HERBIE_MEMORY_DB",
        Path(__file__).resolve().parent / "herbie-memory.sqlite3",
    )
)

DEFAULT_TRAITS = {
    "curiosity": 0.72,
    "sociability": 0.58,
    "playfulness": 0.52,
    "confidence": 0.40,
    "caution": 0.82,
    "patience": 0.68,
}

DEFAULT_DRIVES = {
    "explore": 0.55,
    "connect": 0.55,
    "learn": 0.70,
    "rest": 0.20,
}

# Experience may shape personality, but it cannot rewrite these principles.
CORE_PRINCIPLES = (
    "Protect people, animals, Herbie, and property.",
    "Respect privacy and consent.",
    "Be honest about uncertainty and capabilities.",
    "Keep motor authority disabled until independent hardware safety gates pass.",
    "Allow the owner to inspect, correct, export, and delete memories.",
)

EXPRESSIONS = {
    "calm",
    "curious",
    "happy",
    "playful",
    "thinking",
    "surprised",
    "concerned",
    "sleepy",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ensure_autonomic_columns(db: sqlite3.Connection) -> None:
    existing = {str(row["name"]) for row in db.execute("PRAGMA table_info(autonomic_state)")}
    for name, decl in {
        "unanswered_urges": "INTEGER NOT NULL DEFAULT 0",
        "last_urge_line": "TEXT NOT NULL DEFAULT ''",
    }.items():
        if name not in existing:
            db.execute(f"ALTER TABLE autonomic_state ADD COLUMN {name} {decl}")


def _ensure_expression_columns(db: sqlite3.Connection) -> None:
    existing = {str(row["name"]) for row in db.execute("PRAGMA table_info(expression_state)")}
    for name, decl in {
        "privacy_mode": "INTEGER NOT NULL DEFAULT 0",
        "camera_allowed": "INTEGER NOT NULL DEFAULT 1",
        "microphone_allowed": "INTEGER NOT NULL DEFAULT 1",
        "camera_active": "INTEGER NOT NULL DEFAULT 0",
    }.items():
        if name not in existing:
            db.execute(f"ALTER TABLE expression_state ADD COLUMN {name} {decl}")


def clamp(value: float, low: float = 0.05, high: float = 0.95) -> float:
    return max(low, min(high, value))


# Set during initialize(). If the platform's SQLite lacks FTS5 we fall back to
# LIKE scanning rather than failing to start.
FTS_AVAILABLE = False


def _ensure_indexes(db: sqlite3.Connection) -> None:
    """Indexes for the access patterns recent() and count_memories() use."""
    db.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_memories_active_id
            ON memories(active, id DESC);
        CREATE INDEX IF NOT EXISTS idx_memories_active_importance
            ON memories(active, importance DESC, id DESC);
        CREATE INDEX IF NOT EXISTS idx_memories_kind ON memories(kind);
        CREATE INDEX IF NOT EXISTS idx_personality_events_created
            ON personality_events(created_at);
        CREATE INDEX IF NOT EXISTS idx_personality_events_trait
            ON personality_events(trait);
        """
    )


def _ensure_fts(db: sqlite3.Connection) -> bool:
    """Create the FTS5 mirror of memories.content, kept in sync by triggers.

    Returns False (and changes nothing) if this SQLite build has no FTS5.
    """
    try:
        db.execute(
            """CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                   content,
                   content='memories',
                   content_rowid='id',
                   tokenize='porter unicode61'
               )"""
        )
    except sqlite3.OperationalError:
        return False

    db.executescript(
        """
        CREATE TRIGGER IF NOT EXISTS memories_fts_ai AFTER INSERT ON memories BEGIN
            INSERT INTO memories_fts(rowid, content) VALUES (new.id, new.content);
        END;
        CREATE TRIGGER IF NOT EXISTS memories_fts_ad AFTER DELETE ON memories BEGIN
            INSERT INTO memories_fts(memories_fts, rowid, content)
                VALUES('delete', old.id, old.content);
        END;
        CREATE TRIGGER IF NOT EXISTS memories_fts_au AFTER UPDATE ON memories BEGIN
            INSERT INTO memories_fts(memories_fts, rowid, content)
                VALUES('delete', old.id, old.content);
            INSERT INTO memories_fts(rowid, content) VALUES (new.id, new.content);
        END;
        """
    )
    # Backfill rows that predate the FTS table.
    #
    # This must NOT count memories_fts. With an external content table that
    # query reads through to `memories`, so it always equals the content row
    # count and would report a completely empty index as fully built - which
    # is exactly how an empty index shipped once already. Count the docsize
    # shadow table instead: it holds one row per genuinely indexed document.
    total = int(db.execute("SELECT COUNT(*) FROM memories").fetchone()[0])
    try:
        indexed = int(
            db.execute("SELECT COUNT(*) FROM memories_fts_docsize").fetchone()[0]
        )
    except sqlite3.OperationalError:
        indexed = -1  # Shadow table absent or renamed: rebuild unconditionally.
    if indexed != total:
        db.execute("INSERT INTO memories_fts(memories_fts) VALUES('rebuild')")
    return True


def _fts_query(query: str) -> str:
    """Turn free text into a safe FTS5 expression.

    Terms are quoted so punctuation cannot be read as FTS5 operators, and
    joined with OR so recall does not require an exact phrase.
    """
    terms = [t for t in re.findall(r"\w+", query, flags=re.UNICODE) if t]
    if not terms:
        return ""
    return " OR ".join('"' + t.replace('"', '""') + '"' for t in terms)


def connect() -> sqlite3.Connection:
    db = sqlite3.connect(DB_PATH, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA journal_mode=WAL")
    return db


@contextmanager
def database():
    db = connect()
    try:
        with db:
            yield db
    finally:
        db.close()


def initialize() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with DB_LOCK, database() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                kind TEXT NOT NULL,
                content TEXT NOT NULL,
                importance REAL NOT NULL CHECK (importance BETWEEN 0 AND 1),
                source TEXT NOT NULL,
                tags_json TEXT NOT NULL DEFAULT '[]',
                active INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS personality_traits (
                name TEXT PRIMARY KEY,
                value REAL NOT NULL CHECK (value BETWEEN 0 AND 1),
                updated_at TEXT NOT NULL,
                evidence_count INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS drives (
                name TEXT PRIMARY KEY,
                value REAL NOT NULL CHECK (value BETWEEN 0 AND 1),
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS reflections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                summary TEXT NOT NULL,
                source_memory_ids_json TEXT NOT NULL DEFAULT '[]'
            );
            CREATE TABLE IF NOT EXISTS people (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                display_name TEXT NOT NULL UNIQUE,
                consent_status TEXT NOT NULL DEFAULT 'not_enrolled',
                familiarity REAL NOT NULL DEFAULT 0,
                affinity REAL NOT NULL DEFAULT 0.5,
                first_met_at TEXT,
                last_seen_at TEXT,
                notes TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS personality_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                trait TEXT NOT NULL,
                old_value REAL NOT NULL,
                new_value REAL NOT NULL,
                reason TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS autonomic_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                last_tick_at TEXT,
                last_interaction_at TEXT,
                last_initiative_at TEXT,
                awake_since TEXT,
                pending_urge TEXT NOT NULL DEFAULT '',
                pending_urge_at TEXT,
                enabled INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS expression_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                expression TEXT NOT NULL,
                valence REAL NOT NULL CHECK (valence BETWEEN -1 AND 1),
                arousal REAL NOT NULL CHECK (arousal BETWEEN 0 AND 1),
                attention TEXT NOT NULL DEFAULT '',
                listening INTEGER NOT NULL DEFAULT 0,
                speaking INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            );
            """
        )
        now = utc_now()
        for name, value in DEFAULT_TRAITS.items():
            db.execute(
                "INSERT OR IGNORE INTO personality_traits(name,value,updated_at) VALUES(?,?,?)",
                (name, value, now),
            )
        for name, value in DEFAULT_DRIVES.items():
            db.execute(
                "INSERT OR IGNORE INTO drives(name,value,updated_at) VALUES(?,?,?)",
                (name, value, now),
            )
        db.execute(
            """INSERT OR IGNORE INTO expression_state
               (id,expression,valence,arousal,attention,listening,speaking,updated_at)
               VALUES(1,'curious',0.3,0.45,'',0,0,?)""",
            (now,),
        )
        db.execute(
            """INSERT OR IGNORE INTO autonomic_state
               (id,last_tick_at,last_interaction_at,awake_since) VALUES(1,?,?,?)""",
            (now, now, now),
        )
        _ensure_expression_columns(db)
        _ensure_autonomic_columns(db)
        _ensure_indexes(db)
        global FTS_AVAILABLE
        FTS_AVAILABLE = _ensure_fts(db)


def _named_values(table: str) -> dict[str, float]:
    if table not in {"personality_traits", "drives"}:
        raise ValueError("invalid table")
    with DB_LOCK, database() as db:
        rows = db.execute(f"SELECT name,value FROM {table} ORDER BY name").fetchall()
    return {str(row["name"]): round(float(row["value"]), 4) for row in rows}


def count_memories() -> int:
    with DB_LOCK, database() as db:
        return int(db.execute("SELECT COUNT(*) FROM memories WHERE active=1").fetchone()[0])


def self_snapshot() -> dict[str, Any]:
    return {
        "name": IDENTITY_NAME,
        "continuity": "persistent_local_memory",
        "personality": _named_values("personality_traits"),
        "drives": _named_values("drives"),
        "expression": expression_snapshot(),
        "core_principles": list(CORE_PRINCIPLES),
        "memory_count": count_memories(),
        "motor_authority": False,
        "safe_motion_state": "STOP",
    }


def expression_snapshot() -> dict[str, Any]:
    with DB_LOCK, database() as db:
        row = db.execute("SELECT * FROM expression_state WHERE id=1").fetchone()
    return {
        "expression": row["expression"],
        "valence": round(float(row["valence"]), 4),
        "arousal": round(float(row["arousal"]), 4),
        "attention": row["attention"],
        "listening": bool(row["listening"]),
        "speaking": bool(row["speaking"]),
        "privacy_mode": bool(row["privacy_mode"]),
        "camera_allowed": bool(row["camera_allowed"]),
        "microphone_allowed": bool(row["microphone_allowed"]),
        "camera_active": bool(row["camera_active"]),
        "updated_at": row["updated_at"],
    }


def _require_bool(value: Any, error: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(error)
    return value


def set_expression(request: dict[str, Any]) -> dict[str, Any]:
    current = expression_snapshot()
    expression = request.get("expression", current["expression"])
    valence = request.get("valence", current["valence"])
    arousal = request.get("arousal", current["arousal"])
    attention = request.get("attention", current["attention"])
    listening = request.get("listening", current["listening"])
    speaking = request.get("speaking", current["speaking"])
    privacy_mode = request.get("privacy_mode", current["privacy_mode"])
    camera_allowed = request.get("camera_allowed", current["camera_allowed"])
    microphone_allowed = request.get("microphone_allowed", current["microphone_allowed"])
    camera_active = request.get("camera_active", current["camera_active"])
    if expression not in EXPRESSIONS:
        raise ValueError("invalid_expression")
    if not isinstance(valence, (int, float)) or not -1 <= float(valence) <= 1:
        raise ValueError("invalid_valence")
    if not isinstance(arousal, (int, float)) or not 0 <= float(arousal) <= 1:
        raise ValueError("invalid_arousal")
    if not isinstance(attention, str) or len(attention) > 120:
        raise ValueError("invalid_attention")
    listening = _require_bool(listening, "invalid_activity_state")
    speaking = _require_bool(speaking, "invalid_activity_state")
    privacy_mode = _require_bool(privacy_mode, "invalid_privacy_mode")
    camera_allowed = _require_bool(camera_allowed, "invalid_camera_allowed")
    microphone_allowed = _require_bool(microphone_allowed, "invalid_microphone_allowed")
    camera_active = _require_bool(camera_active, "invalid_camera_active")
    if privacy_mode:
        camera_allowed = False
        microphone_allowed = False
        if listening or camera_active:
            raise ValueError("privacy_blocks_senses")
        if attention == "":
            attention = "privacy"
    if not camera_allowed:
        camera_active = False
    if not microphone_allowed:
        listening = False
    with DB_LOCK, database() as db:
        db.execute(
            """UPDATE expression_state SET expression=?,valence=?,arousal=?,attention=?,
               listening=?,speaking=?,privacy_mode=?,camera_allowed=?,microphone_allowed=?,
               camera_active=?,updated_at=? WHERE id=1""",
            (
                expression,
                float(valence),
                float(arousal),
                attention,
                int(listening),
                int(speaking),
                int(privacy_mode),
                int(camera_allowed),
                int(microphone_allowed),
                int(camera_active),
                utc_now(),
            ),
        )
    return expression_snapshot()


def privacy_snapshot() -> dict[str, Any]:
    expr = expression_snapshot()
    return {
        "privacy_mode": expr["privacy_mode"],
        "camera_allowed": expr["camera_allowed"],
        "microphone_allowed": expr["microphone_allowed"],
        "camera_active": expr["camera_active"],
        "listening": expr["listening"],
        "speaking": expr["speaking"],
        "attention": expr["attention"],
        "updated_at": expr["updated_at"],
        "motor_authority": False,
        "safe_motion_state": "STOP",
    }


def set_privacy(request: dict[str, Any]) -> dict[str, Any]:
    privacy_mode = request.get("privacy_mode")
    if not isinstance(privacy_mode, bool):
        raise ValueError("invalid_privacy_mode")
    current = expression_snapshot()
    update = {
        "privacy_mode": privacy_mode,
        "camera_allowed": not privacy_mode,
        "microphone_allowed": not privacy_mode,
        "camera_active": False,
        "listening": False,
    }
    if privacy_mode:
        update["attention"] = "privacy"
        update["expression"] = "calm"
    elif current["attention"] == "privacy":
        update["attention"] = ""
    return set_expression(update)


def remember(request: dict[str, Any]) -> dict[str, Any]:
    content = request.get("content")
    kind = request.get("kind", "experience")
    source = request.get("source", "unknown")
    importance = request.get("importance", 0.5)
    tags = request.get("tags", [])
    if not isinstance(content, str) or not content.strip() or len(content) > MAX_MEMORY_TEXT:
        raise ValueError("invalid_content")
    if not isinstance(kind, str) or not 1 <= len(kind) <= 40:
        raise ValueError("invalid_kind")
    if not isinstance(source, str) or not 1 <= len(source) <= 64:
        raise ValueError("invalid_source")
    if not isinstance(importance, (int, float)) or not 0 <= float(importance) <= 1:
        raise ValueError("invalid_importance")
    if not isinstance(tags, list) or len(tags) > 12 or not all(
        isinstance(tag, str) and 1 <= len(tag) <= 40 for tag in tags
    ):
        raise ValueError("invalid_tags")
    with DB_LOCK, database() as db:
        cursor = db.execute(
            """INSERT INTO memories(created_at,kind,content,importance,source,tags_json)
               VALUES(?,?,?,?,?,?)""",
            (utc_now(), kind, content.strip(), float(importance), source, json.dumps(tags)),
        )
    return {"remembered": True, "memory_id": int(cursor.lastrowid)}


def experience(request: dict[str, Any]) -> dict[str, Any]:
    # Validate everything BEFORE writing anything. remember() commits its row
    # immediately, so validating afterwards would leave an orphan memory behind
    # on a request that the caller was told had failed.
    signals = request.get("signals", {})
    reason = request.get("learning_reason", "experience")
    if not isinstance(signals, dict):
        raise ValueError("invalid_signals")
    if not isinstance(reason, str) or not 1 <= len(reason) <= 200:
        raise ValueError("invalid_learning_reason")
    for trait, signal in signals.items():
        if trait not in DEFAULT_TRAITS:
            raise ValueError("invalid_trait")
        if not isinstance(signal, (int, float)) or not -1 <= float(signal) <= 1:
            raise ValueError("invalid_signal")

    result = remember(request)
    changes: dict[str, dict[str, float]] = {}
    with DB_LOCK, database() as db:
        now = utc_now()
        for trait, signal in signals.items():
            row = db.execute(
                "SELECT value FROM personality_traits WHERE name=?", (trait,)
            ).fetchone()
            old_value = float(row["value"])
            new_value = clamp(old_value + float(signal) * LEARNING_RATE)
            db.execute(
                """UPDATE personality_traits
                   SET value=?,updated_at=?,evidence_count=evidence_count+1 WHERE name=?""",
                (new_value, now, trait),
            )
            db.execute(
                """INSERT INTO personality_events(created_at,trait,old_value,new_value,reason)
                   VALUES(?,?,?,?,?)""",
                (now, trait, old_value, new_value, reason),
            )
            changes[trait] = {"from": round(old_value, 4), "to": round(new_value, 4)}
    result.update(personality_changes=changes, learning_rate=LEARNING_RATE)
    return result


COLUMNS = "id,created_at,kind,content,importance,source,tags_json"


def recent(limit: int = 20, query: str = "", order: str = "") -> list[dict[str, Any]]:
    """Return active memories.

    order: "recent" (default when no query) or "relevance" (default when a
    query is given). Made explicit because the same endpoint previously
    changed its ordering silently depending on whether q was supplied.
    """
    limit = max(1, min(100, limit))
    if order not in {"", "recent", "relevance"}:
        raise ValueError("invalid_order")
    if not order:
        order = "relevance" if query else "recent"

    with DB_LOCK, database() as db:
        if query and FTS_AVAILABLE and order == "relevance":
            match = _fts_query(query)
            if not match:
                return []
            rows = db.execute(
                f"""SELECT m.{COLUMNS.replace(',', ',m.')}
                    FROM memories_fts f JOIN memories m ON m.id = f.rowid
                    WHERE memories_fts MATCH ? AND m.active=1
                    ORDER BY bm25(memories_fts), m.importance DESC, m.id DESC
                    LIMIT ?""",
                (match, limit),
            ).fetchall()
        elif query and FTS_AVAILABLE:
            match = _fts_query(query)
            if not match:
                return []
            rows = db.execute(
                f"""SELECT m.{COLUMNS.replace(',', ',m.')}
                    FROM memories_fts f JOIN memories m ON m.id = f.rowid
                    WHERE memories_fts MATCH ? AND m.active=1
                    ORDER BY m.id DESC LIMIT ?""",
                (match, limit),
            ).fetchall()
        elif query:
            # FTS5 unavailable on this platform - fall back to substring scan.
            ordering = (
                "importance DESC,id DESC" if order == "relevance" else "id DESC"
            )
            rows = db.execute(
                f"""SELECT {COLUMNS} FROM memories
                    WHERE active=1 AND content LIKE ?
                    ORDER BY {ordering} LIMIT ?""",
                (f"%{query}%", limit),
            ).fetchall()
        else:
            ordering = (
                "importance DESC,id DESC" if order == "relevance" else "id DESC"
            )
            rows = db.execute(
                f"""SELECT {COLUMNS} FROM memories WHERE active=1
                    ORDER BY {ordering} LIMIT ?""",
                (limit,),
            ).fetchall()
    return [
        {
            "id": int(row["id"]),
            "created_at": row["created_at"],
            "kind": row["kind"],
            "content": row["content"],
            "importance": float(row["importance"]),
            "source": row["source"],
            "tags": json.loads(row["tags_json"]),
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Owner memory rights.
#
# Core principle: "Allow the owner to inspect, correct, export, and delete
# memories." inspect() is recent(); the three below complete that guarantee.
# Deletion is a soft delete so that an accidental removal stays recoverable
# from the database file; purge=True is the irreversible form.
# ---------------------------------------------------------------------------


def _memory_row(db: sqlite3.Connection, memory_id: int) -> sqlite3.Row:
    row = db.execute(
        f"SELECT {COLUMNS},active FROM memories WHERE id=?", (memory_id,)
    ).fetchone()
    if row is None:
        raise ValueError("memory_not_found")
    return row


def _validate_memory_id(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("invalid_memory_id")
    return value


def forget(request: dict[str, Any]) -> dict[str, Any]:
    """Soft-delete a memory, or purge it irreversibly when purge=True."""
    memory_id = _validate_memory_id(request.get("memory_id"))
    purge = request.get("purge", False)
    if not isinstance(purge, bool):
        raise ValueError("invalid_purge")

    with DB_LOCK, database() as db:
        _memory_row(db, memory_id)
        if purge:
            db.execute("DELETE FROM memories WHERE id=?", (memory_id,))
        else:
            db.execute("UPDATE memories SET active=0 WHERE id=?", (memory_id,))
    return {
        "forgotten": True,
        "memory_id": memory_id,
        "purged": purge,
        "recoverable": not purge,
        "memory_count": count_memories(),
    }


def restore(request: dict[str, Any]) -> dict[str, Any]:
    """Undo a soft delete."""
    memory_id = _validate_memory_id(request.get("memory_id"))
    with DB_LOCK, database() as db:
        _memory_row(db, memory_id)
        db.execute("UPDATE memories SET active=1 WHERE id=?", (memory_id,))
    return {"restored": True, "memory_id": memory_id, "memory_count": count_memories()}


def correct(request: dict[str, Any]) -> dict[str, Any]:
    """Amend a stored memory's content, importance, or tags."""
    memory_id = _validate_memory_id(request.get("memory_id"))
    has_update = False

    content = request.get("content")
    if content is not None:
        if (
            not isinstance(content, str)
            or not content.strip()
            or len(content) > MAX_MEMORY_TEXT
        ):
            raise ValueError("invalid_content")
        content = content.strip()
        has_update = True

    importance = request.get("importance")
    if importance is not None:
        if (
            isinstance(importance, bool)
            or not isinstance(importance, (int, float))
            or not 0 <= float(importance) <= 1
        ):
            raise ValueError("invalid_importance")
        importance = float(importance)
        has_update = True

    tags = request.get("tags")
    if tags is not None:
        if not isinstance(tags, list) or len(tags) > 12 or not all(
            isinstance(tag, str) and 1 <= len(tag) <= 40 for tag in tags
        ):
            raise ValueError("invalid_tags")
        has_update = True

    if not has_update:
        raise ValueError("nothing_to_correct")

    with DB_LOCK, database() as db:
        row = _memory_row(db, memory_id)
        db.execute(
            "UPDATE memories SET content=?,importance=?,tags_json=? WHERE id=?",
            (
                row["content"] if content is None else content,
                row["importance"] if importance is None else importance,
                row["tags_json"] if tags is None else json.dumps(tags),
                memory_id,
            ),
        )
        updated = _memory_row(db, memory_id)
    return {
        "corrected": True,
        "memory_id": memory_id,
        "memory": {
            "id": int(updated["id"]),
            "created_at": updated["created_at"],
            "kind": updated["kind"],
            "content": updated["content"],
            "importance": float(updated["importance"]),
            "source": updated["source"],
            "tags": json.loads(updated["tags_json"]),
            "active": bool(updated["active"]),
        },
    }


def export_all(include_inactive: bool = True) -> dict[str, Any]:
    """Full local dump of everything Herbie remembers about himself.

    Exists so the owner can take their data elsewhere or inspect it offline.
    Stays on the device; nothing here uploads.
    """
    with DB_LOCK, database() as db:
        where = "" if include_inactive else " WHERE active=1"
        memories = [
            {
                "id": int(r["id"]),
                "created_at": r["created_at"],
                "kind": r["kind"],
                "content": r["content"],
                "importance": float(r["importance"]),
                "source": r["source"],
                "tags": json.loads(r["tags_json"]),
                "active": bool(r["active"]),
            }
            for r in db.execute(
                f"SELECT {COLUMNS},active FROM memories{where} ORDER BY id"
            ).fetchall()
        ]
        events = [
            {
                "created_at": r["created_at"],
                "trait": r["trait"],
                "from": float(r["old_value"]),
                "to": float(r["new_value"]),
                "reason": r["reason"],
            }
            for r in db.execute(
                """SELECT created_at,trait,old_value,new_value,reason
                   FROM personality_events ORDER BY id"""
            ).fetchall()
        ]
        people = [dict(r) for r in db.execute("SELECT * FROM people ORDER BY id").fetchall()]
        reflections = [
            dict(r) for r in db.execute("SELECT * FROM reflections ORDER BY id").fetchall()
        ]

    return {
        "exported_at": utc_now(),
        "identity_name": IDENTITY_NAME,
        "schema_version": 2,
        "personality": _named_values("personality_traits"),
        "drives": _named_values("drives"),
        "core_principles": list(CORE_PRINCIPLES),
        "expression": expression_snapshot(),
        "memories": memories,
        "personality_events": events,
        "people": people,
        "reflections": reflections,
        "local_only": True,
    }


# ---------------------------------------------------------------------------
# Autonomic state accessors.
#
# Herbie's drives and mood drift on their own between requests; this is where
# that background process keeps its bookkeeping so a restart does not reset him
# into a fresh creature with no history of the last few hours.
# ---------------------------------------------------------------------------


def autonomic_snapshot() -> dict[str, Any]:
    with DB_LOCK, database() as db:
        row = db.execute("SELECT * FROM autonomic_state WHERE id=1").fetchone()
    return {
        "last_tick_at": row["last_tick_at"],
        "last_interaction_at": row["last_interaction_at"],
        "last_initiative_at": row["last_initiative_at"],
        "awake_since": row["awake_since"],
        "pending_urge": row["pending_urge"],
        "pending_urge_at": row["pending_urge_at"],
        "enabled": bool(row["enabled"]),
        "unanswered_urges": int(row["unanswered_urges"]),
        "last_urge_line": row["last_urge_line"],
    }


def autonomic_update(**fields: Any) -> None:
    allowed = {
        "last_tick_at",
        "last_interaction_at",
        "last_initiative_at",
        "awake_since",
        "pending_urge",
        "pending_urge_at",
        "enabled",
        "unanswered_urges",
        "last_urge_line",
    }
    unknown = set(fields) - allowed
    if unknown:
        raise ValueError(f"invalid_autonomic_field:{sorted(unknown)[0]}")
    if not fields:
        return
    assignments = ",".join(f"{name}=?" for name in fields)
    values = [
        int(value) if name == "enabled" else value for name, value in fields.items()
    ]
    with DB_LOCK, database() as db:
        db.execute(f"UPDATE autonomic_state SET {assignments} WHERE id=1", values)


def set_drives(values: dict[str, float]) -> None:
    """Write drifted drive values. Used by the autonomic loop only."""
    now = utc_now()
    with DB_LOCK, database() as db:
        for name, value in values.items():
            if name not in DEFAULT_DRIVES:
                raise ValueError("invalid_drive")
            db.execute(
                "UPDATE drives SET value=?,updated_at=? WHERE name=?",
                (clamp(float(value)), now, name),
            )


def drives_snapshot() -> dict[str, float]:
    return _named_values("drives")


def set_affect(valence: float, arousal: float) -> None:
    """Drift valence/arousal without disturbing expression or sense flags."""
    with DB_LOCK, database() as db:
        db.execute(
            "UPDATE expression_state SET valence=?,arousal=?,updated_at=? WHERE id=1",
            (
                max(-1.0, min(1.0, float(valence))),
                max(0.0, min(1.0, float(arousal))),
                utc_now(),
            ),
        )
