from __future__ import annotations

"""Local SQLite storage for reusable HIT proposal sets."""

import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


class HitDesignStore:
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
                CREATE TABLE IF NOT EXISTS hit_designs (
                    id TEXT PRIMARY KEY,
                    action_name TEXT NOT NULL,
                    design_name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    row_count INTEGER NOT NULL DEFAULT 0,
                    schema_version INTEGER NOT NULL DEFAULT 1,
                    payload_json TEXT NOT NULL
                )
                """
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_hit_designs_action_updated "
                "ON hit_designs(action_name COLLATE NOCASE, updated_at DESC)"
            )

    def save(
        self,
        *,
        action_name: str,
        design_name: str,
        payload: dict[str, Any],
        design_id: str | None = None,
    ) -> str:
        action = str(action_name or "").strip()
        name = str(design_name or "").strip()
        if not action:
            raise ValueError("AKCE nesmí být prázdná.")
        if not name:
            raise ValueError("Název návrhu nesmí být prázdný.")
        rows = payload.get("rows") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            raise ValueError("Ukládaný návrh nemá platný seznam řádků.")
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        now = _now()
        key = str(design_id or uuid.uuid4().hex)
        with self._connect() as con:
            existing = con.execute("SELECT created_at FROM hit_designs WHERE id=?", (key,)).fetchone()
            created = str(existing["created_at"]) if existing else now
            con.execute(
                """
                INSERT INTO hit_designs(id, action_name, design_name, created_at, updated_at, row_count, schema_version, payload_json)
                VALUES(?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                    action_name=excluded.action_name,
                    design_name=excluded.design_name,
                    updated_at=excluded.updated_at,
                    row_count=excluded.row_count,
                    schema_version=excluded.schema_version,
                    payload_json=excluded.payload_json
                """,
                (key, action, name, created, now, len(rows), SCHEMA_VERSION, encoded),
            )
        return key

    def list(self, query: str = "", limit: int = 500) -> list[dict[str, Any]]:
        text = str(query or "").strip()
        sql = (
            "SELECT id, action_name, design_name, created_at, updated_at, row_count "
            "FROM hit_designs"
        )
        params: list[Any] = []
        if text:
            sql += " WHERE action_name LIKE ? COLLATE NOCASE OR design_name LIKE ? COLLATE NOCASE"
            token = f"%{text}%"
            params.extend((token, token))
        sql += " ORDER BY updated_at DESC, action_name COLLATE NOCASE, design_name COLLATE NOCASE LIMIT ?"
        params.append(max(1, min(int(limit), 5000)))
        with self._connect() as con:
            return [dict(row) for row in con.execute(sql, params).fetchall()]

    def load(self, design_id: str) -> dict[str, Any]:
        with self._connect() as con:
            row = con.execute("SELECT * FROM hit_designs WHERE id=?", (str(design_id),)).fetchone()
        if row is None:
            raise KeyError("Uložený návrh již v databázi neexistuje.")
        try:
            payload = json.loads(str(row["payload_json"]))
        except json.JSONDecodeError as exc:
            raise ValueError("Uložený návrh má poškozená data.") from exc
        if not isinstance(payload, dict):
            raise ValueError("Uložený návrh nemá platný formát.")
        return {
            "id": str(row["id"]),
            "action_name": str(row["action_name"]),
            "design_name": str(row["design_name"]),
            "created_at": str(row["created_at"]),
            "updated_at": str(row["updated_at"]),
            "row_count": int(row["row_count"]),
            "payload": payload,
        }

    def delete(self, design_id: str) -> bool:
        with self._connect() as con:
            cur = con.execute("DELETE FROM hit_designs WHERE id=?", (str(design_id),))
            return cur.rowcount > 0
