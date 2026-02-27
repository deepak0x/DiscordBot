"""
Batch email handler — /batch_email command (admin only).
Upload a CSV with 'Email' and 'Generated Email Text' columns.
"""
from __future__ import annotations

import asyncio
import io
import logging
import os

import pandas as pd
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes, MessageHandler, filters

import config
from bot.db import increment_sent
from services import email_service, llm_service
from utils.email_composer import build_email_context
from utils.role_inference import get_resume_path

logger = logging.getLogger(__name__)

# Replace with your Telegram numeric user ID to restrict access
ADMIN_IDS: set[int] = set()  # e.g. {123456789}


async def batch_email_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if ADMIN_IDS and update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ You are not authorised to use this command.")
        return
    await update.message.reply_text(
        "📎 Send me a CSV file with columns *Email* and *Generated Email Text*.",
        parse_mode="Markdown",
    )
    ctx.user_data["awaiting_batch_csv"] = True


async def handle_batch_csv(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not ctx.user_data.get("awaiting_batch_csv"):
        return
    ctx.user_data.pop("awaiting_batch_csv", None)

    doc = update.message.document
    if not doc or not doc.file_name.endswith(".csv"):
        await update.message.reply_text("❌ Please upload a valid `.csv` file.")
        return

    file      = await doc.get_file()
    raw_bytes = await file.download_as_bytearray()

    try:
        df = pd.read_csv(io.BytesIO(bytes(raw_bytes)))
    except Exception as exc:
        await update.message.reply_text(f"❌ Failed to read CSV: {exc}")
        return

    if "Email" not in df.columns or "Generated Email Text" not in df.columns:
        await update.message.reply_text("❌ CSV must have 'Email' and 'Generated Email Text' columns.")
        return

    total      = len(df)
    sent_count = 0
    user_id    = str(update.effective_user.id)

    await update.message.reply_text(f"🚀 Starting batch send for *{total}* contacts…", parse_mode="Markdown")

    for idx, row in df.iterrows():
        to_email = str(row["Email"]).strip()
        prompt   = str(row["Generated Email Text"]).strip()
        num      = idx + 1

        sw_skills, sw_projects, ml_skills, ml_projects = build_email_context()

        # LLM with exponential back-off on 429
        role, subject, body = None, None, None
        for attempt in range(5):
            try:
                role, subject, body = await llm_service.generate_email(
                    user_id, to_email, prompt, sw_skills, sw_projects, ml_skills, ml_projects
                )
                break
            except Exception as exc:
                if "429" in str(exc):
                    wait = 6 * (attempt + 1)
                    await update.message.reply_text(
                        f"⏳ [{num}/{total}] Rate limited. Waiting {wait}s… (attempt {attempt+1}/5)"
                    )
                    await asyncio.sleep(wait)
                else:
                    await update.message.reply_text(
                        f"❌ [{num}/{total}] LLM error for {to_email}: {exc}\n\n"
                        f"💡 *Tip:* Use `/provider` to switch models or `/setkey` to add your own API key to bypass limits.",
                        parse_mode="Markdown"
                    )
                    break

        if not body:
            await update.message.reply_text(f"❌ [{num}/{total}] Giving up on {to_email}.")
            continue

        resume_path = get_resume_path(role)
        if not resume_path or not os.path.exists(resume_path):
            await update.message.reply_text(f"⚠️ [{num}/{total}] No resume for {to_email} (inferred role: {role}). Skipping.")
            continue

        try:
            await asyncio.to_thread(
                email_service.send_email,
                to_email, subject, body, resume_path, config.SMTP_EMAIL,
            )
            sent_count += 1
            increment_sent(user_id)
            await update.message.reply_text(f"✅ [{num}/{total}] Sent to {to_email} ({role})")
        except Exception as exc:
            await update.message.reply_text(f"❌ [{num}/{total}] Failed for {to_email}: {exc}")

        await asyncio.sleep(2)   # polite delay between sends

    await update.message.reply_text(
        f"🏁 Done! *{sent_count}/{total}* emails sent.", parse_mode="Markdown"
    )


BATCH_HANDLERS = [
    CommandHandler("batch_email", batch_email_start),
    MessageHandler(filters.Document.MimeType("text/csv"), handle_batch_csv),
]
