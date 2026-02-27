"""
main.py — entry point for DeepakReachesBot (Telegram).

Run:
    python main.py
"""
import logging

from telegram.ext import Application

import config
from bot.handlers.email_handler import build_email_conversation, STANDALONE_HANDLERS
from bot.handlers.batch_handler import BATCH_HANDLERS
from bot.handlers.settings_handler import SETTINGS_HANDLERS

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def post_init(application: Application) -> None:
    from telegram import BotCommand
    commands = [
        BotCommand("email", "Compose & send an outreach email"),
        BotCommand("batch_email", "Upload a CSV to send emails in bulk"),
        BotCommand("provider", "Switch between Gemini, OpenAI, and OpenRouter"),
        BotCommand("setkey", "Set your own API key (/setkey <provider> <key>)"),
        BotCommand("health", "Check if the bot is online"),
        BotCommand("cancel", "Cancel your current action"),
        BotCommand("commands", "Show the list of commands"),
        BotCommand("help", "Show help message"),
    ]
    await application.bot.set_my_commands(commands)
    logger.info("Bot commands registered to Telegram Menu.")

def main() -> None:
    logger.info("Starting DeepakReachesBot…")

    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).post_init(post_init).build()

    # Register conversation handler (must come before standalone /cancel)
    app.add_handler(build_email_conversation())

    for handler in STANDALONE_HANDLERS:
        app.add_handler(handler)

    for handler in SETTINGS_HANDLERS:
        app.add_handler(handler)

    for handler in BATCH_HANDLERS:
        app.add_handler(handler)

    logger.info("Bot is polling. Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
