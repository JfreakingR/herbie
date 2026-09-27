"""Local autobiographical memory and slowly evolving self-state for Herbie."""

from __future__ import annotations

import json
import os
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
        _ensure_expression_columns(db)


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
    result = remember(request)
    signals = request.get("signals", {})
    reason = request.get("learning_reason", "experience")
    if not isinstance(signals, dict):
        raise ValueError("invalid_signals")
    if not isinstance(reason, str) or not 1 <= len(reason) <= 200:
        raise ValueError("invalid_learning_reason")
    changes: dict[str, dict[str, float]] = {}
    with DB_LOCK, database() as db:
        now = utc_now()
        for trait, signal in signals.items():
            if trait not in DEFAULT_TRAITS:
                raise ValueError("invalid_trait")
            if not isinstance(signal, (int, float)) or not -1 <= float(signal) <= 1:
                raise ValueError("invalid_signal")
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


def recent(limit: int = 20, query: str = "") -> list[dict[str, Any]]:
    limit = max(1, min(100, limit))
    with DB_LOCK, database() as db:
        if query:
            rows = db.execute(
                """SELECT id,created_at,kind,content,importance,source,tags_json
                   FROM memories WHERE active=1 AND content LIKE ?
                   ORDER BY importance DESC,id DESC LIMIT ?""",
                (f"%{query}%", limit),
            ).fetchall()
        else:
            rows = db.execute(
                """SELECT id,created_at,kind,content,importance,source,tags_json
                   FROM memories WHERE active=1 ORDER BY id DESC LIMIT ?""",
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
