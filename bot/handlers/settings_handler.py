"""
Settings handler for DeepakReachesBot.
Allows users to switch active LLM provider and set their own API keys.
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CommandHandler, CallbackQueryHandler, ContextTypes

from bot.db import get_user_settings, set_active_provider, set_custom_key

# Callbacks for provider switching
CB_PROV_GEMINI     = "prov_gemini"
CB_PROV_OPENAI     = "prov_openai"
CB_PROV_OPENROUTER = "prov_openrouter"

async def provider_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Entry point for /provider command."""
    user_id = str(update.effective_user.id)
    settings = get_user_settings(user_id)
    active = settings["active_provider"]

    msg = f"⚙️ *LLM Provider Settings*\n\nCurrent active provider: *{active.upper()}*\n\nSelect a provider below to switch:"
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Gemini 🔹", callback_data=CB_PROV_GEMINI),
            InlineKeyboardButton("OpenAI 🟢", callback_data=CB_PROV_OPENAI),
            InlineKeyboardButton("OpenRouter 🟣", callback_data=CB_PROV_OPENROUTER),
        ]
    ])

    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=keyboard)


async def provider_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle callback from provider inline keyboard."""
    query = update.callback_query
    await query.answer()

    user_id = str(query.from_user.id)
    data = query.data

    if data == CB_PROV_GEMINI:
        set_active_provider(user_id, "gemini")
        name = "Gemini"
    elif data == CB_PROV_OPENAI:
        set_active_provider(user_id, "openai")
        name = "OpenAI"
    elif data == CB_PROV_OPENROUTER:
        set_active_provider(user_id, "openrouter")
        name = "OpenRouter"
    else:
        return

    await query.edit_message_text(
        f"✅ Active provider changed to *{name}*.\n\n"
        f"Make sure you have an API key configured for it. "
        f"You can set your own API key using `/setkey {name.lower()} <your_key>`.",
        parse_mode="Markdown"
    )


async def setkey_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /setkey command to store user API keys."""
    args = ctx.args
    if len(args) != 2:
        await update.message.reply_text(
            "❌ Usage: `/setkey <provider> <key>`\n\n"
            "Valid providers: `gemini`, `openai`, `openrouter`.",
            parse_mode="Markdown"
        )
        return

    provider, key = args[0].lower(), args[1]
    
    if provider not in ["gemini", "openai", "openrouter"]:
        await update.message.reply_text("❌ Unknown provider. Use one of: `gemini`, `openai`, `openrouter`.")
        return

    user_id = str(update.effective_user.id)
    set_custom_key(user_id, provider, key)
    
    # Redact key in confirmation
    redacted = f"{key[:4]}...{key[-4:]}" if len(key) > 8 else "***"
    
    await update.message.reply_text(
        f"✅ Saved custom API key for *{provider.upper()}*.\n"
        f"Key: `{redacted}`\n\n"
        f"Note: This key is stored securely and only used for your requests. "
        f"If you want to use it now, make sure to set your active provider using `/provider`.",
        parse_mode="Markdown"
    )

SETTINGS_HANDLERS = [
    CommandHandler("provider", provider_start),
    CommandHandler("setkey", setkey_command),
    CallbackQueryHandler(provider_callback, pattern="^prov_"),
]
