"""Herbie's everyday memory: learning from conversation and recalling it.

After each exchange, the cloud memory keeper (herbie_cloud.extract_memories)
decides what is worth keeping, and this module applies it to the phone's
memory store. Offline, exchanges wait in a small queue and are caught up the
next time the cloud answers; an explicit "remember that ..." is kept at once
even offline.

Conversation memories are stored with source "conversation". Voice requests to
forget or correct only touch those; the owner's setup memories are changed
through the memory API, never by a sentence Herbie overheard. Forgetting is the
recoverable soft delete.

The last few lines of conversation are also saved to disk so a brain restart
does not wipe what was just said.
"""

from __future__ import annotations

import json
import os
import re
import threading
from pathlib import Path
from typing import Any

import herbie_cloud
import herbie_memory


HERE = Path(__file__).resolve().parent
CONVERSATION_SOURCE = "conversation"
RELEVANT_MEMORIES = 6
KEY_FACTS = 8
PENDING_LIMIT = 50
DIALOGUE_LIMIT = 12
LEARN_LOCK = threading.Lock()

REMEMBER_REQUEST = re.compile(
    r"^\W*(?:(?:hey|ok|okay)\W+)?(?:herbie\W+)?remember(?:\s+that)?\s+(.{3,})$",
    re.IGNORECASE,
)


def _path(variable: str, name: str) -> Path:
    return Path(os.environ.get(variable, HERE / name))


def pending_path() -> Path:
    return _path("HERBIE_PENDING_MEMORIES", "herbie-pending-memories.json")


def dialogue_path() -> Path:
    return _path("HERBIE_RECENT_DIALOGUE", "herbie-recent-dialogue.json")


def _read_list(path: Path) -> list[Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return value if isinstance(value, list) else []


def _write_list(path: Path, value: list[Any]) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value), encoding="utf-8")
    temporary.replace(path)


# ---------------------------------------------------------------------------
# Recall
# ---------------------------------------------------------------------------


def context_memories(message: str) -> list[str]:
    """Memories for this reply: the most relevant ones, then his key facts."""
    chosen: list[dict[str, Any]] = []
    seen: set[int] = set()
    try:
        relevant = herbie_memory.recent(RELEVANT_MEMORIES, message[:500], "relevance")
    except ValueError:
        relevant = []
    for memory in relevant + herbie_memory.recent(KEY_FACTS, "", "relevance"):
        if memory["id"] not in seen:
            seen.add(memory["id"])
            chosen.append(memory)
    return [memory["content"][:300] for memory in chosen]


def load_dialogue() -> list[dict[str, str]]:
    turns = [
        turn
        for turn in _read_list(dialogue_path())
        if isinstance(turn, dict)
        and turn.get("role") in ("user", "assistant")
        and isinstance(turn.get("content"), str)
    ]
    return turns[-DIALOGUE_LIMIT:]


def save_dialogue(turns: list[dict[str, str]]) -> None:
    try:
        _write_list(dialogue_path(), list(turns)[-DIALOGUE_LIMIT:])
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Learning
# ---------------------------------------------------------------------------


def _known_for(user_text: str) -> list[dict[str, Any]]:
    known: dict[int, dict[str, Any]] = {}
    try:
        relevant = herbie_memory.recent(12, user_text[:500], "relevance")
    except ValueError:
        relevant = []
    for memory in relevant + herbie_memory.recent(20, "", "recent"):
        known.setdefault(memory["id"], memory)
    return list(known.values())


def _conversation_memory(memory_id: Any, known: list[dict[str, Any]]) -> int | None:
    for memory in known:
        if memory["id"] == memory_id and memory["source"] == CONVERSATION_SOURCE:
            return memory_id
    return None


def apply_plan(plan: dict[str, list[Any]], known: list[dict[str, Any]]) -> dict[str, int]:
    """Store what the keeper decided. Invalid items are skipped, never fatal."""
    done = {"remembered": 0, "updated": 0, "forgotten": 0}
    existing = {memory["content"].strip().lower() for memory in known}
    for item in plan.get("remember", [])[:5]:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        importance = item.get("importance", 0.5)
        if not isinstance(content, str) or content.strip().lower() in existing:
            continue
        if not isinstance(importance, (int, float)) or isinstance(importance, bool):
            importance = 0.5
        try:
            herbie_memory.remember(
                {
                    "content": content.strip()[:500],
                    "kind": "fact",
                    "source": CONVERSATION_SOURCE,
                    "importance": min(1.0, max(0.0, float(importance))),
                    "tags": ["auto"],
                }
            )
        except ValueError:
            continue
        existing.add(content.strip().lower())
        done["remembered"] += 1
    for item in plan.get("update", [])[:5]:
        if not isinstance(item, dict):
            continue
        memory_id = _conversation_memory(item.get("memory_id"), known)
        content = item.get("content")
        if memory_id is None or not isinstance(content, str):
            continue
        try:
            herbie_memory.correct({"memory_id": memory_id, "content": content.strip()[:500]})
        except ValueError:
            continue
        done["updated"] += 1
    for raw_id in plan.get("forget", [])[:5]:
        memory_id = _conversation_memory(raw_id, known)
        if memory_id is None:
            continue
        try:
            herbie_memory.forget({"memory_id": memory_id})
        except ValueError:
            continue
        done["forgotten"] += 1
    return done


def remember_offline(user_text: str) -> bool:
    """Keep an explicit "remember that ..." even when the cloud is unreachable."""
    match = REMEMBER_REQUEST.match(user_text.strip())
    if not match:
        return False
    content = match.group(1).strip().rstrip(".!?")
    try:
        herbie_memory.remember(
            {
                "content": f"The owner asked me to remember: {content}."[:500],
                "kind": "fact",
                "source": CONVERSATION_SOURCE,
                "importance": 0.8,
                "tags": ["auto", "explicit"],
            }
        )
    except ValueError:
        return False
    return True


def _queue(user_text: str, reply_text: str) -> None:
    pending = _read_list(pending_path())
    pending.append({"user": user_text[:2000], "reply": reply_text[:2000]})
    try:
        _write_list(pending_path(), pending[-PENDING_LIMIT:])
    except OSError:
        pass


def _learn_one(user_text: str, reply_text: str) -> None:
    known = _known_for(user_text)
    plan = herbie_cloud.extract_memories(user_text, reply_text, known)
    apply_plan(plan, known)


def catch_up() -> int:
    """Process exchanges queued while offline; stops at the first cloud failure."""
    pending = _read_list(pending_path())
    handled = 0
    for item in pending:
        if not isinstance(item, dict):
            handled += 1
            continue
        try:
            _learn_one(str(item.get("user", "")), str(item.get("reply", "")))
        except herbie_cloud.CloudUnavailable:
            break
        handled += 1
    if handled:
        try:
            _write_list(pending_path(), pending[handled:])
        except OSError:
            pass
    return handled


def learn(user_text: str, reply_text: str) -> None:
    """Remember what matters from one exchange. Never raises."""
    with LEARN_LOCK:
        try:
            if herbie_cloud.load_config() is None:
                remember_offline(user_text)
                return
            catch_up()
            try:
                _learn_one(user_text, reply_text)
            except herbie_cloud.CloudUnavailable:
                if not remember_offline(user_text):
                    _queue(user_text, reply_text)
        except Exception:  # memory must never take the conversation down
            pass


def learn_in_background(user_text: str, reply_text: str) -> None:
    threading.Thread(
        target=learn, args=(user_text, reply_text), name="herbie-learn", daemon=True
    ).start()
