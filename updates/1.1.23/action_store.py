from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


class ActionStore:
    """Central persistent storage for complete TURTO ISO actions."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path, timeout=10)
        con.row_factory = sqlite3.Row
        return con

    def _ensure_schema(self) -> None:
        with self._connect() as con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS actions (
                    id TEXT PRIMARY KEY,
                    action_name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    decoder_count INTEGER NOT NULL DEFAULT 0,
                    hit_count INTEGER NOT NULL DEFAULT 0,
                    schema_version INTEGER NOT NULL DEFAULT 1,
                    payload_json TEXT NOT NULL
                )
                """
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_actions_name_updated "
                "ON actions(action_name COLLATE NOCASE, updated_at DESC)"
            )

    @staticmethod
    def _counts(payload: dict[str, Any]) -> tuple[int, int]:
        project = payload.get("project") if isinstance(payload, dict) else {}
        decoder_rows = project.get("rows") if isinstance(project, dict) else []
        hit = payload.get("hit_design") if isinstance(payload, dict) else {}
        hit_rows = hit.get("rows") if isinstance(hit, dict) else []
        return (
            len(decoder_rows) if isinstance(decoder_rows, list) else 0,
            len(hit_rows) if isinstance(hit_rows, list) else 0,
        )

    def save(
        self,
        *,
        action_name: str,
        payload: dict[str, Any],
        action_id: str | None = None,
    ) -> dict[str, Any]:
        name = str(action_name or "").strip()
        if not name:
            raise ValueError("Název AKCE nesmí být prázdný.")
        if not isinstance(payload, dict):
            raise ValueError("Ukládaná AKCE nemá platná data.")
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        decoder_count, hit_count = self._counts(payload)
        key = str(action_id or uuid.uuid4().hex)
        now = _now()
        with self._connect() as con:
            existing = con.execute(
                "SELECT created_at FROM actions WHERE id=?", (key,)
            ).fetchone()
            created_at = str(existing["created_at"]) if existing else now
            con.execute(
                """
                INSERT INTO actions(
                    id, action_name, created_at, updated_at,
                    decoder_count, hit_count, schema_version, payload_json
                )
                VALUES(?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                    action_name=excluded.action_name,
                    updated_at=excluded.updated_at,
                    decoder_count=excluded.decoder_count,
                    hit_count=excluded.hit_count,
                    schema_version=excluded.schema_version,
                    payload_json=excluded.payload_json
                """,
                (
                    key,
                    name,
                    created_at,
                    now,
                    decoder_count,
                    hit_count,
                    SCHEMA_VERSION,
                    encoded,
                ),
            )
        return {
            "id": key,
            "action_name": name,
            "created_at": created_at,
            "updated_at": now,
            "decoder_count": decoder_count,
            "hit_count": hit_count,
        }

    def list(self, search: str = "") -> list[dict[str, Any]]:
        term = str(search or "").strip()
        with self._connect() as con:
            if term:
                like = f"%{term}%"
                rows = con.execute(
                    """
                    SELECT id, action_name, created_at, updated_at,
                           decoder_count, hit_count
                    FROM actions
                    WHERE action_name LIKE ? COLLATE NOCASE
                    ORDER BY updated_at DESC, action_name COLLATE NOCASE
                    """,
                    (like,),
                ).fetchall()
            else:
                rows = con.execute(
                    """
                    SELECT id, action_name, created_at, updated_at,
                           decoder_count, hit_count
                    FROM actions
                    ORDER BY updated_at DESC, action_name COLLATE NOCASE
                    """
                ).fetchall()
        return [dict(row) for row in rows]

    def load(self, action_id: str) -> dict[str, Any]:
        with self._connect() as con:
            row = con.execute(
                "SELECT * FROM actions WHERE id=?", (str(action_id),)
            ).fetchone()
        if row is None:
            raise KeyError("Uložená AKCE již v databázi neexistuje.")
        result = dict(row)
        try:
            payload = json.loads(str(result.pop("payload_json")))
        except Exception as exc:
            raise ValueError("Uložená AKCE má poškozená data.") from exc
        if not isinstance(payload, dict):
            raise ValueError("Uložená AKCE nemá platný formát.")
        result["payload"] = payload
        return result

    def delete(self, action_id: str) -> None:
        with self._connect() as con:
            con.execute("DELETE FROM actions WHERE id=?", (str(action_id),))
