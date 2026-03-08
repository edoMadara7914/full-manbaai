from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from texts import t


def language_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("O‘zbekcha", callback_data="lang:uz")],
            [InlineKeyboardButton("Русский", callback_data="lang:ru")],
            [InlineKeyboardButton("English", callback_data="lang:en")],
        ]
    )


def subscription_keyboard(lang: str, urls: list[str]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(f"{t(lang, 'open_channel')} {i+1}", url=url)] for i, url in enumerate(urls)]
    rows.append([InlineKeyboardButton(t(lang, "check_sub"), callback_data="check_sub")])
    return InlineKeyboardMarkup(rows)


def main_menu(lang: str, is_admin: bool) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(t(lang, "ask")), KeyboardButton(t(lang, "upload"))],
        [KeyboardButton(t(lang, "my_files")), KeyboardButton(t(lang, "history"))],
        [KeyboardButton(t(lang, "help"))],
    ]
    if is_admin:
        rows.append([KeyboardButton(t(lang, "admin"))])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def back_menu(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([[KeyboardButton(t(lang, "back"))]], resize_keyboard=True)


def save_scope_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[
            InlineKeyboardButton(t(lang, "save_private"), callback_data="save_scope:private"),
            InlineKeyboardButton(t(lang, "save_public"), callback_data="save_scope:public"),
        ]]
    )


def my_files_menu(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(t(lang, "my_private_files")), KeyboardButton(t(lang, "my_public_files"))],
            [KeyboardButton(t(lang, "delete_file"))],
            [KeyboardButton(t(lang, "back"))],
        ],
        resize_keyboard=True,
    )


def history_menu(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton(t(lang, "recent_questions"))], [KeyboardButton(t(lang, "clear_history"))], [KeyboardButton(t(lang, "back"))]],
        resize_keyboard=True,
    )


def help_menu(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton(t(lang, "how_it_works"))], [KeyboardButton(t(lang, "what_can_upload"))], [KeyboardButton(t(lang, "ask_rules"))], [KeyboardButton(t(lang, "back"))]],
        resize_keyboard=True,
    )


def admin_menu(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(t(lang, "admin_dashboard")), KeyboardButton(t(lang, "admin_files"))],
            [KeyboardButton(t(lang, "admin_moderation")), KeyboardButton(t(lang, "admin_exports"))],
            [KeyboardButton(t(lang, "admin_logs")), KeyboardButton(t(lang, "admin_channels"))],
            [KeyboardButton(t(lang, "back"))],
        ],
        resize_keyboard=True,
    )


def moderation_keyboard(doc_id: int, lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[
            InlineKeyboardButton(t(lang, "approved"), callback_data=f"mod:approve:{doc_id}"),
            InlineKeyboardButton(t(lang, "reject"), callback_data=f"mod:reject:{doc_id}"),
        ]]
    )
