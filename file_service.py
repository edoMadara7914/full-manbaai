from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from telegram import File

from config import SETTINGS
from services.openai_service import AI


@dataclass
class ParsedUpload:
    text: str
    page_count: int
    preview_text: str
    source_kind: str
    file_name: str
    mime_type: str | None
    file_size: int
    telegram_file_id: str | None
    telegram_file_unique_id: str | None
    content_hash: str


def chunk_text(text: str) -> list[dict[str, Any]]:
    clean = " ".join(text.split())
    if not clean:
        return []
    chunks = []
    start = 0
    index = 0
    while start < len(clean):
        end = min(len(clean), start + SETTINGS.max_chunk_chars)
        part = clean[start:end]
        chunks.append({
            "chunk_index": index,
            "chunk_text": part,
            "source_page": None,
            "source_section": f"chunk-{index + 1}",
        })
        index += 1
        if end == len(clean):
            break
        start = max(0, end - SETTINGS.chunk_overlap)
    return chunks


async def download_telegram_file(tg_file: File, destination: Path) -> Path:
    await tg_file.download_to_drive(custom_path=str(destination))
    return destination


def classify_message(update) -> tuple[str | None, Any | None]:
    msg = update.message
    if msg.document:
        return "document", msg.document
    if msg.photo:
        return "photo", msg.photo[-1]
    if msg.voice:
        return "voice", msg.voice
    if msg.text and not msg.text.startswith("/"):
        return "text", msg.text
    return None, None


async def parse_upload(update, context) -> ParsedUpload | None:
    kind, payload = classify_message(update)
    if not kind:
        return None

    if kind == "text":
        text = str(payload)
        return ParsedUpload(
            text=text,
            page_count=1,
            preview_text=text[: SETTINGS.max_preview_chars],
            source_kind="text",
            file_name="inline_text.txt",
            mime_type="text/plain",
            file_size=len(text.encode()),
            telegram_file_id=None,
            telegram_file_unique_id=None,
            content_hash=AI.content_hash(text),
        )

    tg_file = await payload.get_file()
    suffix = ".bin"
    file_name = getattr(payload, "file_name", None) or f"telegram_{payload.file_unique_id}"
    if kind == "photo":
        suffix = ".jpg"
        file_name = file_name + suffix if not file_name.endswith(suffix) else file_name
    elif kind == "voice":
        suffix = ".ogg"
        file_name = file_name + suffix if not file_name.endswith(suffix) else file_name
    else:
        suffix = Path(file_name).suffix or suffix

    local_path = SETTINGS.files_tmp_dir / f"{payload.file_unique_id}{suffix}"
    await download_telegram_file(tg_file, local_path)

    if kind == "voice":
        text = AI.transcribe_audio(local_path)
        page_count = 1
        mime_type = getattr(payload, "mime_type", "audio/ogg")
    else:
        text, page_count = AI.parse_document(local_path, getattr(payload, "mime_type", None))
        mime_type = getattr(payload, "mime_type", None)

    return ParsedUpload(
        text=text,
        page_count=page_count,
        preview_text=text[: SETTINGS.max_preview_chars],
        source_kind=kind,
        file_name=file_name,
        mime_type=mime_type,
        file_size=getattr(payload, "file_size", 0) or 0,
        telegram_file_id=getattr(payload, "file_id", None),
        telegram_file_unique_id=getattr(payload, "file_unique_id", None),
        content_hash=AI.content_hash(text),
    )
