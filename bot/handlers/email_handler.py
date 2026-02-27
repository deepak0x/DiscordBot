"""
Telegram bot — email outreach handler.
Implements a ConversationHandler for the /email → preview → confirm/cancel/edit flow.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

import config
from services import email_service, llm_service
from utils.email_composer import build_email_context
from utils.role_inference import get_resume_path

logger = logging.getLogger(__name__)

# ── Conversation states ────────────────────────────────────────────────────────
WAITING_FOR_MESSAGE = 0
WAITING_FOR_EMAIL   = 1
WAITING_FOR_EDIT    = 2

# ── Inline-button callback data ───────────────────────────────────────────────
CB_CONFIRM = "confirm"
CB_CANCEL  = "cancel"
CB_EDIT    = "edit"


# ── /start & /help ─────────────────────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "👋 Hi! I'm *DeepakReachesBot* — I craft personalised outreach emails "
        "and send them with your resume attached.\n\n"
        "📜 *Available Commands:*\n"
        "• `/email` — compose & send an outreach email\n"
        "• `/batch_email` — upload a CSV to send emails in bulk\n"
        "• `/provider` — switch between Gemini, OpenAI, and OpenRouter\n"
        "• `/setkey <provider> <key>` — set your own API key\n"
        "• `/health` — check if the bot is online\n"
        "• `/cancel` — cancel your current action\n"
        "• `/commands` or `/help` — show this list",
        parse_mode="Markdown",
    )

async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await start(update, ctx)

# ── /health ────────────────────────────────────────────────────────────────────
async def health_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("✅ Bot is online and running smoothly.")



# ── /email — step 1: ask for the outreach message ─────────────────────────────
async def email_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "📋 *Step 1 of 2* — Simply paste the job description, recruiter info, or what you want the email to be about.\n\n"
        "*(I will automatically extract the email address and write a subject for you!)*",
        parse_mode="Markdown",
    )
    return WAITING_FOR_MESSAGE


# ── /email — step 2: handle the pasted message ───────────────────────────────
async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()

    if len(text) > 4000:
        await update.message.reply_text("⚠️ Message too long (max 4 000 chars). Please shorten it.")
        return ConversationHandler.END

    # Auto-extract any email address from the pasted text
    email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", text)

    if not email_match:
        ctx.user_data["pending_message"] = text
        await update.message.reply_text(
            "📧 I couldn't find an email address in your message. Please reply with the recipient's email "
            "(e.g. `recruiter@company.com`):",
            parse_mode="Markdown",
        )
        return WAITING_FOR_EMAIL

    # Pass the ENTIRE text to the LLM to process
    return await _process_and_preview(
        update, ctx,
        to_email=email_match.group(0),
        subject=None,
        body_text=text,
    )


# ── Step 2b: collect missing email address ───────────────────────────────────
async def handle_email_input(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", text)

    if not email_match:
        await update.message.reply_text("❌ Invalid email format. Try again (e.g. `recruiter@company.com`):")
        return WAITING_FOR_EMAIL

    original_text = ctx.user_data.get("pending_message", "")

    return await _process_and_preview(
        update, ctx,
        to_email=email_match.group(0),
        subject=None,
        body_text=original_text,
    )


# ── Step 3: Handle updated email body from Edit button ─────────────────────────
async def handle_edited_email(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    new_body = update.message.text.strip()
    pending = ctx.user_data.get("pending_email")
    if not pending:
        await update.message.reply_text("❌ Session expired. Please start over with /email.")
        return ConversationHandler.END

    pending["body"] = new_body

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Send",   callback_data=CB_CONFIRM),
            InlineKeyboardButton("✏️ Edit",   callback_data=CB_EDIT),
            InlineKeyboardButton("❌ Cancel", callback_data=CB_CANCEL),
        ]
    ])

    preview = (
        f"📧 *Email Preview (Manually Edited)*\n"
        f"*From:* {config.SMTP_EMAIL}\n"
        f"*To:* {pending['to_email']}\n"
        f"*Subject:* {pending['subject']}\n"
        f"*Resume:* {os.path.basename(pending['resume_path'])}\n\n"
        f"*Body:*\n{new_body}"
    )

    if "message_ids" in pending:
        for m_id in pending["message_ids"]:
            try:
                await ctx.bot.delete_message(chat_id=update.message.chat_id, message_id=m_id)
            except Exception:
                pass

    if len(preview) > 4000:
        msg1 = await update.message.reply_text(
            f"📧 *Email Preview (Manually Edited)*\n*From:* {config.SMTP_EMAIL}\n"
            f"*To:* {pending['to_email']}\n*Subject:* {pending['subject']}\n"
            f"*Resume:* {os.path.basename(pending['resume_path'])}",
            parse_mode="Markdown",
        )
        msg2 = await update.message.reply_text(f"*Body:*\n{new_body}", parse_mode="Markdown")
        msg3 = await update.message.reply_text("Done editing! What would you like to do?", reply_markup=keyboard)
        pending["message_ids"] = [msg1.message_id, msg2.message_id, msg3.message_id]
    else:
        msg1 = await update.message.reply_text(preview, parse_mode="Markdown", reply_markup=keyboard)
        pending["message_ids"] = [msg1.message_id]

    return ConversationHandler.END


# ── Core: generate email and show preview with inline buttons ─────────────────
async def _process_and_preview(
    update: Update,
    ctx: ContextTypes.DEFAULT_TYPE,
    to_email: str,
    subject: str | None,
    body_text: str,
) -> int:
    user_id = str(update.effective_user.id)
    
    # Get active provider name for the UI message
    from bot.db import get_user_settings
    provider = get_user_settings(user_id)["active_provider"]
    provider_names = {"gemini": "Gemini AI", "openai": "OpenAI", "openrouter": "OpenRouter"}
    display_name = provider_names.get(provider, "AI")
    
    await update.message.reply_text(f"⏳ Generating your email with {display_name}…")

    sw_skills, sw_projects, ml_skills, ml_projects = build_email_context()

    try:
        role, generated_subject, generated_body = await llm_service.generate_email(
            user_id, to_email, body_text, sw_skills, sw_projects, ml_skills, ml_projects
        )
    except Exception as exc:
        logger.exception("LLM generation error")
        error_msg = str(exc)
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⚙️ Change Provider", callback_data="error_provider")],
            [InlineKeyboardButton("❌ Cancel", callback_data=CB_CANCEL)]
        ])
        
        await update.message.reply_text(
            f"❌ *Failed to generate email:* API limit reached or invalid key.\n\n"
            f"`{error_msg}`\n\n"
            f"💡 *Tip:* Use `/provider` to switch models, or `/setkey` to add your own API key to bypass limits.",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
        return ConversationHandler.END

    resume_path = get_resume_path(role)
    if not resume_path or not os.path.exists(resume_path):
        await update.message.reply_text(
            f"❌ I determined this was a '{role}' role, but could not find a matching resume. "
            "Please start over."
        )
        return ConversationHandler.END

    final_subject = subject or generated_subject

    # Stash for confirm step
    ctx.user_data["pending_email"] = {
        "to_email":    to_email,
        "subject":     final_subject,
        "body":        generated_body,
        "resume_path": resume_path,
        "role":        role,
        "from_email":  config.SMTP_EMAIL,
    }

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Send",   callback_data=CB_CONFIRM),
            InlineKeyboardButton("✏️ Edit",   callback_data=CB_EDIT),
            InlineKeyboardButton("❌ Cancel", callback_data=CB_CANCEL),
        ]
    ])

    preview = (
        f"📧 *Email Preview*\n"
        f"*From:* {config.SMTP_EMAIL}\n"
        f"*To:* {to_email}\n"
        f"*Subject:* {final_subject}\n"
        f"*Resume:* {os.path.basename(resume_path)}\n\n"
        f"*Body:*\n{generated_body}"
    )

    # Telegram message limit is 4096 chars
    if len(preview) > 4000:
        msg1 = await update.message.reply_text(
            f"📧 *Email Preview*\n*From:* {config.SMTP_EMAIL}\n"
            f"*To:* {to_email}\n*Subject:* {final_subject}\n"
            f"*Resume:* {os.path.basename(resume_path)}",
            parse_mode="Markdown",
        )
        msg2 = await update.message.reply_text(f"*Body:*\n{generated_body}", parse_mode="Markdown")
        msg3 = await update.message.reply_text("What would you like to do?", reply_markup=keyboard)
        ctx.user_data["pending_email"]["message_ids"] = [msg1.message_id, msg2.message_id, msg3.message_id]
    else:
        msg1 = await update.message.reply_text(preview, parse_mode="Markdown", reply_markup=keyboard)
        ctx.user_data["pending_email"]["message_ids"] = [msg1.message_id]

    return ConversationHandler.END   # Inline buttons handle the rest


# ── Inline-button callbacks ───────────────────────────────────────────────────
async def button_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    data    = query.data
    pending = ctx.user_data.get("pending_email")

    if data == "error_provider":
        from bot.handlers.settings_handler import provider_start
        await query.message.delete()
        await provider_start(update, ctx)
        return

    if data == CB_CANCEL:
        pending = ctx.user_data.pop("pending_email", None)
        if pending and "message_ids" in pending:
            for m_id in pending["message_ids"]:
                try:
                    await ctx.bot.delete_message(chat_id=query.message.chat_id, message_id=m_id)
                except Exception:
                    pass
        else:
            try:
                await query.message.delete()
            except Exception:
                pass
        await query.message.reply_text("❌ Email cancelled.")
        return

    if data == CB_EDIT:
        if not pending:
            await query.message.reply_text("No pending email. Use /email to start over.")
            return

        if "message_ids" in pending:
            for m_id in pending["message_ids"]:
                try:
                    await ctx.bot.delete_message(chat_id=query.message.chat_id, message_id=m_id)
                except Exception:
                    pass
        else:
            try:
                await query.message.delete()
            except Exception:
                pass

        msg1 = await query.message.reply_text(
            "✏️ Please send me the new, corrected email body below:",
            parse_mode="Markdown",
        )
        pending["message_ids"] = [msg1.message_id]
        return WAITING_FOR_EDIT

    if data == CB_CONFIRM:
        if not pending:
            await query.message.reply_text("No pending email. Use /email to start over.")
            return

        if "message_ids" in pending:
            for m_id in pending["message_ids"]:
                try:
                    await ctx.bot.delete_message(chat_id=query.message.chat_id, message_id=m_id)
                except Exception:
                    pass
        else:
            try:
                await query.message.delete()
            except Exception:
                pass

        processing_msg = await query.message.reply_text("⏳ Sending email…")

        try:
            await asyncio.to_thread(
                email_service.send_email,
                pending["to_email"],
                pending["subject"],
                pending["body"],
                pending["resume_path"],
                pending["from_email"],
            )
        except Exception as exc:
            logger.exception("Email send failed")
            await processing_msg.edit_text(f"❌ Failed to send: {exc}")
            return

        # Update MongoDB counter
        try:
            from bot.db import increment_sent
            count = increment_sent(str(query.from_user.id))
            await processing_msg.edit_text(
                f"✅ Email sent to *{pending['to_email']}* ({pending['role']})!\n"
                f"Total emails sent: *{count}*",
                parse_mode="Markdown",
            )
        except Exception:
            await processing_msg.edit_text(
                f"✅ Email sent to *{pending['to_email']}* ({pending['role']})!",
                parse_mode="Markdown",
            )

        ctx.user_data.pop("pending_email", None)


# ── /cancel (conversation fallback) ──────────────────────────────────────────
async def cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data.pop("pending_email", None)
    ctx.user_data.pop("pending_message", None)
    await update.message.reply_text("❌ Cancelled.")
    return ConversationHandler.END


# ── ConversationHandler factory ───────────────────────────────────────────────
def build_email_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("email", email_start)],
        states={
            WAITING_FOR_MESSAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
            ],
            WAITING_FOR_EMAIL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_email_input)
            ],
            WAITING_FOR_EDIT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edited_email)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )


# ── Standalone handlers (registered separately in main.py) ───────────────────
STANDALONE_HANDLERS = [
    CommandHandler("start",  start),
    CommandHandler("help",   help_cmd),
    CommandHandler("commands", help_cmd),
    CommandHandler("health", health_cmd),
    CommandHandler("cancel", cancel),
    CallbackQueryHandler(button_callback, pattern="^(confirm|cancel|edit|error_provider)$"),
]
