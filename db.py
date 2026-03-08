from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from config import SETTINGS


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, path: Path):
        self.path = path
        self._init_db()

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    telegram_user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    full_name TEXT,
                    language_code TEXT DEFAULT 'uz',
                    role TEXT DEFAULT 'user',
                    interface_language TEXT,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT,
                    updated_at TEXT
                );

                CREATE TABLE IF NOT EXISTS user_blocks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_user_id INTEGER NOT NULL,
                    block_type TEXT NOT NULL,
                    reason TEXT,
                    expires_at TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS user_limits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_user_id INTEGER,
                    scope TEXT NOT NULL,
                    limit_type TEXT NOT NULL,
                    limit_value INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS channels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_chat_id TEXT,
                    title TEXT,
                    url TEXT,
                    is_required INTEGER DEFAULT 1,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    owner_user_id INTEGER NOT NULL,
                    telegram_file_id TEXT,
                    telegram_file_unique_id TEXT,
                    file_name TEXT,
                    mime_type TEXT,
                    source_kind TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    moderation_status TEXT DEFAULT 'approved',
                    preview_text TEXT,
                    page_count INTEGER DEFAULT 0,
                    section_hint TEXT,
                    content_hash TEXT,
                    file_size INTEGER DEFAULT 0,
                    is_deleted INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS document_chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id INTEGER NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    chunk_text TEXT NOT NULL,
                    source_page TEXT,
                    source_section TEXT,
                    embedding_json TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(document_id) REFERENCES documents(id)
                );

                CREATE TABLE IF NOT EXISTS question_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_user_id INTEGER NOT NULL,
                    question_text TEXT NOT NULL,
                    question_language TEXT,
                    private_answer TEXT,
                    public_answer TEXT,
                    private_source TEXT,
                    public_source TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS exports_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    admin_user_id INTEGER NOT NULL,
                    export_type TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS app_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    level TEXT NOT NULL,
                    category TEXT NOT NULL,
                    message TEXT NOT NULL,
                    payload_json TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    history_id INTEGER NOT NULL,
                    telegram_user_id INTEGER NOT NULL,
                    value TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def upsert_user(self, telegram_user_id: int, username: str | None, full_name: str, language_code: str | None) -> None:
        now = utcnow()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO users (telegram_user_id, username, full_name, language_code, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(telegram_user_id) DO UPDATE SET
                    username=excluded.username,
                    full_name=excluded.full_name,
                    language_code=excluded.language_code,
                    updated_at=excluded.updated_at
                """,
                (telegram_user_id, username, full_name, language_code, now, now),
            )

    def set_interface_language(self, telegram_user_id: int, language: str) -> None:
        with self.connect() as conn:
            conn.execute("UPDATE users SET interface_language=?, updated_at=? WHERE telegram_user_id=?", (language, utcnow(), telegram_user_id))

    def get_interface_language(self, telegram_user_id: int) -> str:
        with self.connect() as conn:
            row = conn.execute("SELECT interface_language FROM users WHERE telegram_user_id=?", (telegram_user_id,)).fetchone()
            return row["interface_language"] if row and row["interface_language"] else SETTINGS.default_language

    def get_role(self, telegram_user_id: int) -> str:
        with self.connect() as conn:
            row = conn.execute("SELECT role FROM users WHERE telegram_user_id=?", (telegram_user_id,)).fetchone()
            return row["role"] if row else "user"

    def list_required_channels(self) -> list[sqlite3.Row]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM channels WHERE is_required=1 AND is_active=1 ORDER BY id ASC").fetchall()
            return rows

    def seed_channels_from_env(self) -> None:
        with self.connect() as conn:
            existing = conn.execute("SELECT COUNT(*) AS cnt FROM channels").fetchone()["cnt"]
            if existing:
                return
            for chat_id, url in zip(SETTINGS.required_channel_ids, SETTINGS.required_channel_urls):
                conn.execute(
                    "INSERT INTO channels (telegram_chat_id, title, url, is_required, is_active, created_at) VALUES (?, ?, ?, 1, 1, ?)",
                    (chat_id, url.rsplit("/", 1)[-1], url, utcnow()),
                )

    def add_document(self, **kwargs: Any) -> int:
        now = utcnow()
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO documents (
                    owner_user_id, telegram_file_id, telegram_file_unique_id, file_name, mime_type,
                    source_kind, scope, moderation_status, preview_text, page_count, section_hint,
                    content_hash, file_size, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    kwargs["owner_user_id"],
                    kwargs.get("telegram_file_id"),
                    kwargs.get("telegram_file_unique_id"),
                    kwargs.get("file_name"),
                    kwargs.get("mime_type"),
                    kwargs["source_kind"],
                    kwargs["scope"],
                    kwargs.get("moderation_status", "approved"),
                    kwargs.get("preview_text"),
                    kwargs.get("page_count", 0),
                    kwargs.get("section_hint"),
                    kwargs.get("content_hash"),
                    kwargs.get("file_size", 0),
                    now,
                    now,
                ),
            )
            return int(cur.lastrowid)

    def find_duplicate_by_hash(self, content_hash: str) -> sqlite3.Row | None:
        with self.connect() as conn:
            return conn.execute(
                "SELECT * FROM documents WHERE content_hash=? AND is_deleted=0 ORDER BY id DESC LIMIT 1",
                (content_hash,),
            ).fetchone()

    def add_chunks(self, document_id: int, chunks: Iterable[dict[str, Any]]) -> None:
        now = utcnow()
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT INTO document_chunks (document_id, chunk_index, chunk_text, source_page, source_section, embedding_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        document_id,
                        chunk["chunk_index"],
                        chunk["chunk_text"],
                        chunk.get("source_page"),
                        chunk.get("source_section"),
                        json.dumps(chunk.get("embedding", []), ensure_ascii=False),
                        now,
                    )
                    for chunk in chunks
                ],
            )

    def list_user_documents(self, telegram_user_id: int, scope: str | None = None) -> list[sqlite3.Row]:
        sql = "SELECT * FROM documents WHERE owner_user_id=? AND is_deleted=0"
        params: list[Any] = [telegram_user_id]
        if scope:
            sql += " AND scope=?"
            params.append(scope)
        sql += " ORDER BY id DESC"
        with self.connect() as conn:
            return conn.execute(sql, params).fetchall()

    def soft_delete_document(self, doc_id: int) -> None:
        with self.connect() as conn:
            conn.execute("UPDATE documents SET is_deleted=1, updated_at=? WHERE id=?", (utcnow(), doc_id))

    def list_documents_for_search(self, telegram_user_id: int, scope: str) -> list[sqlite3.Row]:
        with self.connect() as conn:
            if scope == "private":
                return conn.execute(
                    "SELECT * FROM documents WHERE owner_user_id=? AND scope='private' AND is_deleted=0 ORDER BY id DESC",
                    (telegram_user_id,),
                ).fetchall()
            return conn.execute(
                "SELECT * FROM documents WHERE scope='public' AND moderation_status='approved' AND is_deleted=0 ORDER BY id DESC"
            ).fetchall()

    def list_chunks_for_document_ids(self, doc_ids: list[int]) -> list[sqlite3.Row]:
        if not doc_ids:
            return []
        placeholders = ",".join("?" for _ in doc_ids)
        with self.connect() as conn:
            return conn.execute(
                f"SELECT c.*, d.file_name FROM document_chunks c JOIN documents d ON d.id=c.document_id WHERE c.document_id IN ({placeholders})",
                doc_ids,
            ).fetchall()

    def add_history(self, telegram_user_id: int, question_text: str, question_language: str, private_answer: str, public_answer: str, private_source: str, public_source: str) -> int:
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO question_history (
                    telegram_user_id, question_text, question_language, private_answer,
                    public_answer, private_source, public_source, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (telegram_user_id, question_text, question_language, private_answer, public_answer, private_source, public_source, utcnow()),
            )
            return int(cur.lastrowid)

    def list_recent_history(self, telegram_user_id: int, limit: int = 10) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(
                "SELECT * FROM question_history WHERE telegram_user_id=? ORDER BY id DESC LIMIT ?",
                (telegram_user_id, limit),
            ).fetchall()

    def clear_history(self, telegram_user_id: int) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM question_history WHERE telegram_user_id=?", (telegram_user_id,))

    def add_log(self, level: str, category: str, message: str, payload: dict[str, Any] | None = None) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO app_logs (level, category, message, payload_json, created_at) VALUES (?, ?, ?, ?, ?)",
                (level, category, message, json.dumps(payload or {}, ensure_ascii=False), utcnow()),
            )

    def list_logs(self, category: str | None = None, limit: int = 50) -> list[sqlite3.Row]:
        with self.connect() as conn:
            if category:
                return conn.execute("SELECT * FROM app_logs WHERE category=? ORDER BY id DESC LIMIT ?", (category, limit)).fetchall()
            return conn.execute("SELECT * FROM app_logs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()

    def add_export_log(self, admin_user_id: int, export_type: str, file_path: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO exports_log (admin_user_id, export_type, file_path, created_at) VALUES (?, ?, ?, ?)",
                (admin_user_id, export_type, file_path, utcnow()),
            )

    def list_public_documents(self) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(
                "SELECT * FROM documents WHERE scope='public' AND is_deleted=0 ORDER BY id DESC"
            ).fetchall()

    def set_document_moderation_status(self, doc_id: int, status: str) -> None:
        with self.connect() as conn:
            conn.execute("UPDATE documents SET moderation_status=?, updated_at=? WHERE id=?", (status, utcnow(), doc_id))

    def dashboard_stats(self) -> dict[str, Any]:
        with self.connect() as conn:
            counts = {}
            counts["users"] = conn.execute("SELECT COUNT(*) AS cnt FROM users").fetchone()["cnt"]
            counts["documents"] = conn.execute("SELECT COUNT(*) AS cnt FROM documents WHERE is_deleted=0").fetchone()["cnt"]
            counts["public_documents"] = conn.execute("SELECT COUNT(*) AS cnt FROM documents WHERE is_deleted=0 AND scope='public'").fetchone()["cnt"]
            counts["private_documents"] = conn.execute("SELECT COUNT(*) AS cnt FROM documents WHERE is_deleted=0 AND scope='private'").fetchone()["cnt"]
            counts["pending_public"] = conn.execute("SELECT COUNT(*) AS cnt FROM documents WHERE is_deleted=0 AND scope='public' AND moderation_status='pending'").fetchone()["cnt"]
            counts["questions_today"] = conn.execute(
                "SELECT COUNT(*) AS cnt FROM question_history WHERE date(created_at)=date('now')"
            ).fetchone()["cnt"]
            counts["uploads_today"] = conn.execute(
                "SELECT COUNT(*) AS cnt FROM documents WHERE date(created_at)=date('now')"
            ).fetchone()["cnt"]
            return counts


DB = Database(SETTINGS.database_path)
DB.seed_channels_from_env()
