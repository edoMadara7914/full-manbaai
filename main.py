from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any

from telegram import InlineKeyboardMarkup, Update
from telegram.constants import ChatMemberStatus
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import SETTINGS
from db import DB
from keyboards import admin_menu, back_menu, help_menu, history_menu, language_keyboard, main_menu, moderation_keyboard, my_files_menu, save_scope_keyboard, subscription_keyboard
from services.file_service import chunk_text, parse_upload
from services.openai_service import AI
from services.search_service import search_scope
from texts import t

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SELF_QA_TRIGGERS = [
    "seni kim yaratgan",
    "who created you",
    "кто тебя создал",
    "sen kimsan",
    "what can you do",
    "что ты умеешь",
    "o'zing haqida",
    "ozing haqida",
    "about yourself",
]


async def ensure_user(update: Update) -> int:
    user = update.effective_user
    DB.upsert_user(user.id, user.username, user.full_name, user.language_code)
    return user.id


async def is_subscribed(user_id: int, bot) -> bool:
    channels = DB.list_required_channels()
    if not channels:
        return True
    for channel in channels:
        try:
            member = await bot.get_chat_member(chat_id=channel["telegram_chat_id"], user_id=user_id)
            if member.status in {ChatMemberStatus.LEFT, ChatMemberStatus.KICKED}:
                return False
        except Exception:
            return False
    return True


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = await ensure_user(update)
    lang = DB.get_interface_language(user_id)
    if not await is_subscribed(user_id, context.bot):
        await update.message.reply_text(
            t(lang, "must_subscribe"),
            reply_markup=subscription_keyboard(lang, [row["url"] for row in DB.list_required_channels()]),
        )
        return
    await update.message.reply_text(t(lang, "choose_lang"), reply_markup=language_keyboard())


async def lang_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    lang = query.data.split(":", 1)[1]
    DB.set_interface_language(query.from_user.id, lang)
    is_admin = query.from_user.id in SETTINGS.admin_user_ids or DB.get_role(query.from_user.id) == "admin"
    await query.message.reply_text(t(lang, "main_menu"), reply_markup=main_menu(lang, is_admin))


async def check_sub_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    lang = DB.get_interface_language(query.from_user.id)
    if await is_subscribed(query.from_user.id, context.bot):
        await query.message.reply_text(t(lang, "choose_lang"), reply_markup=language_keyboard())
    else:
        await query.message.reply_text(t(lang, "must_subscribe"), reply_markup=subscription_keyboard(lang, [row["url"] for row in DB.list_required_channels()]))


async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = await ensure_user(update)
    lang = DB.get_interface_language(user_id)
    is_admin = user_id in SETTINGS.admin_user_ids or DB.get_role(user_id) == "admin"
    text = update.message.text

    if text == t(lang, "ask"):
        context.user_data["mode"] = "ask"
        await update.message.reply_text(t(lang, "send_question"), reply_markup=back_menu(lang))
        return
    if text == t(lang, "upload"):
        context.user_data["mode"] = "upload"
        await update.message.reply_text(t(lang, "send_data"), reply_markup=back_menu(lang))
        return
    if text == t(lang, "my_files"):
        await update.message.reply_text(t(lang, "my_files"), reply_markup=my_files_menu(lang))
        return
    if text == t(lang, "history"):
        await update.message.reply_text(t(lang, "history"), reply_markup=history_menu(lang))
        return
    if text == t(lang, "help"):
        await update.message.reply_text(t(lang, "about"), reply_markup=help_menu(lang))
        return
    if text == t(lang, "back"):
        context.user_data.pop("mode", None)
        await update.message.reply_text(t(lang, "main_menu"), reply_markup=main_menu(lang, is_admin))
        return
    if text == t(lang, "my_private_files"):
        docs = DB.list_user_documents(user_id, "private")
        await update.message.reply_text(format_docs_list(docs) or "Bo'sh")
        return
    if text == t(lang, "my_public_files"):
        docs = DB.list_user_documents(user_id, "public")
        await update.message.reply_text(format_docs_list(docs) or "Bo'sh")
        return
    if text == t(lang, "delete_file"):
        await update.message.reply_text("Fayl ID sini yuboring.")
        context.user_data["mode"] = "delete_file"
        return
    if text == t(lang, "recent_questions"):
        rows = DB.list_recent_history(user_id)
        msg = "\n\n".join([f"{i+1}. {row['question_text']}" for i, row in enumerate(rows)]) or "Bo'sh"
        await update.message.reply_text(msg)
        return
    if text == t(lang, "clear_history"):
        DB.clear_history(user_id)
        await update.message.reply_text("Tozalandi.")
        return
    if text == t(lang, "how_it_works"):
        await update.message.reply_text("ManbaAI savol bo'yicha shaxsiy va ommaviy bazadan qidiradi, keyin javobni manba bilan qaytaradi.")
        return
    if text == t(lang, "what_can_upload"):
        await update.message.reply_text("PDF, DOCX, TXT, rasm, ovoz, oddiy matn.")
        return
    if text == t(lang, "ask_rules"):
        await update.message.reply_text("Savolni aniq yozing. Masalan: '3-bobdagi asosiy g'oya nima?'")
        return
    if text == t(lang, "admin") and is_admin:
        await update.message.reply_text("Admin panel", reply_markup=admin_menu(lang))
        return

    if is_admin and text == t(lang, "admin_dashboard"):
        stats = DB.dashboard_stats()
        msg = (
            f"Users: {stats['users']}\n"
            f"Documents: {stats['documents']}\n"
            f"Public: {stats['public_documents']}\n"
            f"Private: {stats['private_documents']}\n"
            f"Pending public: {stats['pending_public']}\n"
            f"Questions today: {stats['questions_today']}\n"
            f"Uploads today: {stats['uploads_today']}"
        )
        await update.message.reply_text(msg)
        return
    if is_admin and text == t(lang, "admin_files"):
        rows = DB.list_public_documents()[:20]
        await update.message.reply_text(format_docs_list(rows) or "Bo'sh")
        return
    if is_admin and text == t(lang, "admin_moderation"):
        await show_pending_moderation(update, lang)
        return
    if is_admin and text == t(lang, "admin_exports"):
        path = export_public_documents_csv(update.effective_user.id)
        await update.message.reply_document(document=path.open("rb"), filename=path.name)
        return
    if is_admin and text == t(lang, "admin_logs"):
        logs = DB.list_logs(limit=15)
        out = "\n\n".join([f"[{row['level']}] {row['category']}\n{row['message']}" for row in logs]) or "No logs"
        await update.message.reply_text(out[:4000])
        return
    if is_admin and text == t(lang, "admin_channels"):
        rows = DB.list_required_channels()
        msg = "\n".join([f"{r['title']} | {r['url']} | required={r['is_required']}" for r in rows]) or "No channels"
        await update.message.reply_text(msg)
        return

    mode = context.user_data.get("mode")
    if mode == "delete_file" and text.isdigit():
        DB.soft_delete_document(int(text))
        await update.message.reply_text("O'chirildi.")
        return

    if any(trigger in text.lower() for trigger in SELF_QA_TRIGGERS):
        await update.message.reply_text(t(lang, "about"))
        return

    if mode == "ask":
        await answer_question(update, context, text)
        return

    await update.message.reply_text(t(lang, "main_menu"), reply_markup=main_menu(lang, is_admin))


async def media_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = await ensure_user(update)
    lang = DB.get_interface_language(user_id)
    mode = context.user_data.get("mode")

    if mode == "ask":
        parsed = await parse_upload(update, context)
        if not parsed or not parsed.text.strip():
            await update.message.reply_text("Savolni o'qib bo'lmadi.")
            return
        await answer_question(update, context, parsed.text)
        return

    if mode != "upload":
        return

    parsed = await parse_upload(update, context)
    if not parsed or not parsed.text.strip():
        await update.message.reply_text("Matn ajratib bo'lmadi.")
        return

    duplicate = DB.find_duplicate_by_hash(parsed.content_hash)
    if duplicate:
        await update.message.reply_text(
            f"Bu fayl oldin yuklangan: {duplicate['file_name']} (ID: {duplicate['id']})\nBaribir saqlashingiz mumkin.",
            reply_markup=save_scope_keyboard(lang),
        )
    else:
        await update.message.reply_text(t(lang, "save_where"), reply_markup=save_scope_keyboard(lang))
    context.user_data["pending_upload"] = parsed.__dict__


async def save_scope_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    scope = query.data.split(":", 1)[1]
    lang = DB.get_interface_language(query.from_user.id)
    payload = context.user_data.get("pending_upload")
    if not payload:
        await query.message.reply_text("Pending upload topilmadi.")
        return

    moderation_status = "pending" if scope == "public" else "approved"
    doc_id = DB.add_document(
        owner_user_id=query.from_user.id,
        telegram_file_id=payload.get("telegram_file_id"),
        telegram_file_unique_id=payload.get("telegram_file_unique_id"),
        file_name=payload["file_name"],
        mime_type=payload.get("mime_type"),
        source_kind=payload["source_kind"],
        scope=scope,
        moderation_status=moderation_status,
        preview_text=payload["preview_text"],
        page_count=payload["page_count"],
        section_hint=None,
        content_hash=payload["content_hash"],
        file_size=payload["file_size"],
    )
    chunks = chunk_text(payload["text"])
    embeddings = AI.embed_texts([c["chunk_text"] for c in chunks]) if chunks else []
    for chunk, emb in zip(chunks, embeddings):
        chunk["embedding"] = emb
    DB.add_chunks(doc_id, chunks)
    DB.add_log("INFO", "upload", f"document saved #{doc_id}", {"scope": scope, "owner": query.from_user.id})
    context.user_data.pop("pending_upload", None)
    if scope == "public":
        await query.message.reply_text(t(lang, "saved_public_pending"))
    else:
        await query.message.reply_text(t(lang, "saved_private"))


async def moderation_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if query.from_user.id not in SETTINGS.admin_user_ids:
        return
    _, action, doc_id = query.data.split(":")
    DB.set_document_moderation_status(int(doc_id), "approved" if action == "approve" else "rejected")
    await query.message.reply_text(f"Document {doc_id}: {action}")


async def answer_question(update: Update, context: ContextTypes.DEFAULT_TYPE, question_text: str) -> None:
    user_id = update.effective_user.id
    private_result = search_scope(user_id, "private", question_text)
    public_result = search_scope(user_id, "public", question_text)
    answer_lang = AI.detect_language(question_text)
    result = AI.answer_from_context(question_text, private_result["context"], public_result["context"], answer_lang)

    private_block = result.get("private", {})
    public_block = result.get("public", {})

    message = format_answer_block("Shaxsiy ma'lumotlardan", private_block) + "\n\n" + format_answer_block("Ommaviy ma'lumotlardan", public_block)
    await update.message.reply_text(message[:4096])

    DB.add_history(
        telegram_user_id=user_id,
        question_text=question_text,
        question_language=answer_lang,
        private_answer=private_block.get("short_answer", ""),
        public_answer=public_block.get("short_answer", ""),
        private_source=private_block.get("source", private_result["source"]),
        public_source=public_block.get("source", public_result["source"]),
    )
    DB.add_log("INFO", "search", "question answered", {"user_id": user_id, "question": question_text[:200]})


async def show_pending_moderation(update: Update, lang: str) -> None:
    rows = [r for r in DB.list_public_documents() if r["moderation_status"] == "pending"][:10]
    if not rows:
        await update.message.reply_text("Pending yo'q.")
        return
    for row in rows:
        text = (
            f"ID: {row['id']}\n"
            f"File: {row['file_name']}\n"
            f"Owner: {row['owner_user_id']}\n"
            f"Preview: {row['preview_text'][:300]}"
        )
        await update.message.reply_text(text, reply_markup=moderation_keyboard(int(row["id"]), lang))


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Unhandled error", exc_info=context.error)
    DB.add_log("ERROR", "runtime", str(context.error))


def format_docs_list(rows) -> str:
    items = []
    for row in rows:
        items.append(f"ID {row['id']} | {row['file_name']} | {row['scope']} | {row['moderation_status']}")
    return "\n".join(items)


def format_answer_block(title: str, block: dict[str, Any]) -> str:
    return (
        f"*{title}:*\n"
        f"*Qisqa javob:* {block.get('short_answer', 'Ma\'lumot topilmadi.')}\n"
        f"*Batafsil:* {block.get('details', 'Ma\'lumot topilmadi.')}\n"
        f"*Manba:* {block.get('source', 'topilmadi')}"
    )


def export_public_documents_csv(admin_user_id: int) -> Path:
    rows = DB.list_public_documents()
    export_dir = Path(__file__).resolve().parent / "exports"
    export_dir.mkdir(exist_ok=True)
    path = export_dir / "public_documents_export.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "file_name", "mime_type", "owner_user_id", "moderation_status", "created_at", "preview_text"])
        for row in rows:
            writer.writerow([row["id"], row["file_name"], row["mime_type"], row["owner_user_id"], row["moderation_status"], row["created_at"], row["preview_text"]])
    DB.add_export_log(admin_user_id, "public_csv", str(path))
    return path


def build_app() -> Application:
    app = Application.builder().token(SETTINGS.telegram_bot_token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(lang_callback, pattern=r"^lang:"))
    app.add_handler(CallbackQueryHandler(check_sub_callback, pattern=r"^check_sub$"))
    app.add_handler(CallbackQueryHandler(save_scope_callback, pattern=r"^save_scope:"))
    app.add_handler(CallbackQueryHandler(moderation_callback, pattern=r"^mod:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))
    app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO | filters.VOICE, media_router))
    app.add_error_handler(error_handler)
    return app


if __name__ == "__main__":
    if not SETTINGS.telegram_bot_token or not SETTINGS.openai_api_key:
        raise RuntimeError("Please set TELEGRAM_BOT_TOKEN and OPENAI_API_KEY in .env")
    build_app().run_polling(allowed_updates=Update.ALL_TYPES)
