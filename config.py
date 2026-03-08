from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List

from dotenv import load_dotenv

load_dotenv()


def _split_csv(value: str | None) -> List[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    openai_api_key: str
    bot_username: str
    bot_name: str
    admin_user_ids: List[int]
    required_channel_ids: List[str]
    required_channel_urls: List[str]
    database_path: Path
    files_tmp_dir: Path
    default_language: str
    openai_chat_model: str
    openai_embed_model: str
    openai_transcribe_model: str
    max_chunk_chars: int
    chunk_overlap: int
    max_preview_chars: int


def get_settings() -> Settings:
    base_dir = Path(__file__).resolve().parent
    db_path = base_dir / os.getenv("DATABASE_PATH", "data/manbaai.db")
    tmp_dir = base_dir / os.getenv("FILES_TMP_DIR", "tmp")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_dir.mkdir(parents=True, exist_ok=True)

    return Settings(
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        bot_username=os.getenv("BOT_USERNAME", "@ManbaAI_bot"),
        bot_name=os.getenv("BOT_NAME", "ManbaAI"),
        admin_user_ids=[int(x) for x in _split_csv(os.getenv("ADMIN_USER_IDS"))],
        required_channel_ids=_split_csv(os.getenv("REQUIRED_CHANNEL_IDS")),
        required_channel_urls=_split_csv(os.getenv("REQUIRED_CHANNEL_URLS")),
        database_path=db_path,
        files_tmp_dir=tmp_dir,
        default_language=os.getenv("DEFAULT_LANGUAGE", "uz"),
        openai_chat_model=os.getenv("OPENAI_CHAT_MODEL", "gpt-4.1-mini"),
        openai_embed_model=os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small"),
        openai_transcribe_model=os.getenv("OPENAI_TRANSCRIBE_MODEL", "gpt-4o-mini-transcribe"),
        max_chunk_chars=int(os.getenv("MAX_CHUNK_CHARS", "1400")),
        chunk_overlap=int(os.getenv("CHUNK_OVERLAP", "200")),
        max_preview_chars=int(os.getenv("MAX_PREVIEW_CHARS", "400")),
    )


SETTINGS = get_settings()
