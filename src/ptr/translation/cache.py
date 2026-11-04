"""Caché SQLite determinista para traducciones e intentos (§6.6)."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from typing import Any, Dict, Optional


class TranslationCache:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS translations (
                    cache_key TEXT PRIMARY KEY,
                    source_text TEXT NOT NULL,
                    target_text TEXT NOT NULL,
                    backend TEXT NOT NULL,
                    model TEXT NOT NULL,
                    prompt_ver TEXT NOT NULL,
                    glossary_ver TEXT NOT NULL,
                    status TEXT NOT NULL,
                    metadata_json TEXT,
                    created_at REAL NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_backend ON translations (backend, model)")

    @staticmethod
    def compute_key(
        text_tagged: str,
        backend: str,
        model: str,
        prompt_ver: str = "1.0",
        glossary_ver: str = "1.0",
    ) -> str:
        """Calcula el hash SHA-256 de la entrada para indexación determinista (§6.6)."""
        seed = f"{text_tagged}|{backend}|{model}|{prompt_ver}|{glossary_ver}"
        return hashlib.sha256(seed.encode("utf-8")).hexdigest()

    def get(self, cache_key: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM translations WHERE cache_key = ?", (cache_key,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            return {
                "cache_key": row["cache_key"],
                "source_text": row["source_text"],
                "target_text": row["target_text"],
                "backend": row["backend"],
                "model": row["model"],
                "status": row["status"],
                "metadata": json.loads(row["metadata_json"] or "{}"),
                "created_at": row["created_at"],
            }

    def set(
        self,
        cache_key: str,
        source_text: str,
        target_text: str,
        backend: str,
        model: str,
        prompt_ver: str = "1.0",
        glossary_ver: str = "1.0",
        status: str = "success",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO translations 
                (cache_key, source_text, target_text, backend, model, prompt_ver, glossary_ver, status, metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cache_key,
                    source_text,
                    target_text,
                    backend,
                    model,
                    prompt_ver,
                    glossary_ver,
                    status,
                    json.dumps(metadata or {}),
                    time.time(),
                ),
            )
