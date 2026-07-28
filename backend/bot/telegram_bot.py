"""Telegram bot entrypoint for civilian-facing reports.

Runs as a separate process alongside the FastAPI backend (they talk over
HTTP, not shared memory — see ``API_BASE_URL`` in ``core.config``). Every
incoming text message is tried, in order, against:

  1. The "I'm alive" pulse parser   -> POST /api/v1/pulses
  2. The need-broadcast parser      -> POST /api/v1/needs

Safety signals are checked first on purpose: if a message could plausibly be
read either way, "I'm alive" should win so families aren't left worrying
about someone who actually confirmed they're okay.

If neither matches, the bot replies with a short bilingual usage hint.

Run:

    cd backend
    python -m bot.telegram_bot
"""

from __future__ import annotations

import logging

import httpx
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from core.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
)
log = logging.getLogger("deadzone.bot")

WELCOME_TEXT = (
    "স্বাগতম! DeadZone বট আপনার নিরাপত্তা সংকেত ও প্রয়োজনীয় সাহায্যের অনুরোধ "
    "রেকর্ড করে।\n\n"
    "নিরাপদ থাকলে লিখুন: 'আমি ঠিক আছি, ঢাকা'\n"
    "কিছু দরকার হলে লিখুন: 'পানি দরকার, মিরপুর ১০'\n\n"
    "Welcome! DeadZone records your safety signal or aid request.\n"
    "Safe: 'আমি ঠিক আছি, ঢাকা'\n"
    "Need help: 'পানি দরকার, মিরপুর ১০'"
)

HELP_TEXT = (
    "বুঝতে পারিনি। এভাবে লিখুন:\n"
    "নিরাপদ থাকলে: 'আমি ঠিক আছি, ঢাকা'\n"
    "কিছু দরকার হলে: 'পানি দরকার, মিরপুর ১০'\n\n"
    "I didn't understand that. Try:\n"
    "Safe: 'আমি ঠিক আছি, ঢাকা'\n"
    "Need help: 'পানি দরকার, মিরপুর ১০'"
)

CATEGORY_LABEL_BN = {
    "water": "পানি",
    "food": "খাবার",
    "medical": "চিকিৎসা",
    "shelter": "আশ্রয়",
    "other": "অন্যান্য",
}


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message:
        await update.effective_message.reply_text(WELCOME_TEXT)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None or not message.text:
        return

    settings = get_settings()
    telegram_id = update.effective_user.id if update.effective_user else None
    text = message.text.strip()

    async with httpx.AsyncClient(base_url=settings.api_base_url, timeout=10.0) as client:
        try:
            # 1. Try the "I'm alive" pulse first — safety signals take
            # priority over aid requests.
            pulse_resp = await client.post(
                "/api/v1/pulses",
                json={"raw_text": text, "telegram_id": telegram_id, "source": "bot"},
            )
        except httpx.HTTPError:
            log.exception("failed to reach DeadZone API at %s", settings.api_base_url)
            await message.reply_text(
                "দুঃখিত, সার্ভারের সাথে সংযোগ করা যাচ্ছে না। একটু পরে আবার চেষ্টা করুন।"
            )
            return

        if pulse_resp.status_code == 201:
            data = pulse_resp.json()
            place = data.get("place_text") or "অজানা স্থান"
            await message.reply_text(
                f"✅ আপনার নিরাপত্তা সংকেত রেকর্ড হয়েছে — {place}।\nআপনি নিরাপদ, ধন্যবাদ।"
            )
            return

        # 2. Not an alive pulse — try the need-broadcast parser.
        need_resp = await client.post(
            "/api/v1/needs",
            json={"raw_text": text, "telegram_id": telegram_id, "source": "bot"},
        )
        if need_resp.status_code == 201:
            data = need_resp.json()
            category_bn = CATEGORY_LABEL_BN.get(data["category"], data["category"])
            place = data.get("place_text") or "অজানা স্থান"
            urgency_note = " (জরুরি হিসেবে চিহ্নিত)" if data.get("urgent") else ""
            await message.reply_text(
                f"📣 অনুরোধ রেকর্ড হয়েছে: {category_bn} — {place}{urgency_note}।\n"
                "সমন্বয়কারী দল শীঘ্রই দেখবে।"
            )
            return

    log.info("unmatched message from telegram_id=%s: %r", telegram_id, text)
    await message.reply_text(HELP_TEXT)


def build_application() -> Application:
    settings = get_settings()
    if not settings.has_telegram:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is not set. Copy backend/.env.example to .env "
            "and fill in a token from @BotFather."
        )
    application = Application.builder().token(settings.telegram_bot_token).build()
    application.add_handler(CommandHandler("start", handle_start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    return application


def main() -> None:
    application = build_application()
    log.info("DeadZone bot starting (polling mode, API_BASE_URL=%s)", get_settings().api_base_url)
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
