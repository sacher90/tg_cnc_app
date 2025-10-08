"""Standalone Telegram bot for managing access to the CNC assistant."""
from __future__ import annotations

import logging
import os
import re
from typing import Iterable, Set

from telegram import Update
from telegram.ext import (Application, CommandHandler, ContextTypes,
                          MessageHandler, filters)

from api.admin import add_user


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _load_admin_ids() -> Set[str]:
    """Load admin Telegram IDs from the BOT_ADMIN_IDS environment variable."""

    raw = os.environ.get("BOT_ADMIN_IDS", "")
    ids = set()
    for chunk in re.split(r"[;,\s]+", raw):
        chunk = chunk.strip()
        if chunk.isdigit():
            ids.add(chunk)
    return ids


ADMIN_IDS = _load_admin_ids()


async def _reply_with_user_id(update: Update) -> None:
    if update.effective_user is None or update.message is None:
        return

    user_id = str(update.effective_user.id)
    await update.message.reply_text(f"Ваш Telegram ID: {user_id}")


def _extract_candidate_ids(text: str) -> Iterable[str]:
    """Return unique numeric sequences that look like Telegram IDs."""

    if not text:
        return []
    candidates = {match.group(0) for match in re.finditer(r"\b\d{4,}\b", text)}
    return sorted(candidates)


async def _handle_admin_action(update: Update, candidates: Iterable[str]) -> None:
    if update.message is None:
        return

    for candidate in candidates:
        try:
            add_user(int(candidate), "")
        except ValueError as exc:
            message = str(exc) or "уже есть в списке доступа"
            await update.message.reply_text(f"ℹ️ ID {candidate} не добавлен: {message}.")
        except Exception as exc:  # pragma: no cover - unexpected issues
            logger.exception("Failed to add user %s", candidate)
            await update.message.reply_text(f"⚠️ Ошибка при добавлении ID {candidate}: {exc}")
        else:
            await update.message.reply_text(f"✅ Пользователь с ID {candidate} добавлен в доступ.")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle plain text messages sent to the bot."""

    await _reply_with_user_id(update)

    user_id = update.effective_user.id if update.effective_user else None
    text = update.message.text if update.message else ""

    if user_id is None or str(user_id) not in ADMIN_IDS:
        return

    candidates = [cid for cid in _extract_candidate_ids(text) if cid != str(user_id)]
    if not candidates:
        return

    await _handle_admin_action(update, candidates)


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reply to /start commands by sending the user their Telegram ID."""

    await _reply_with_user_id(update)


def main() -> None:
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN environment variable is required to run the bot")

    application = Application.builder().token(token).build()

    application.add_handler(CommandHandler("start", handle_start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Bot started. Admin IDs: %s", ", ".join(sorted(ADMIN_IDS)) or "нет")
    application.run_polling()


if __name__ == "__main__":
    main()
