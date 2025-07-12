import logging
import asyncio
import re
import time
from datetime import datetime, timedelta

import aiosqlite
from telegram import (
    Update, InlineKeyboardMarkup, InlineKeyboardButton, ParseMode,
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters,
    ContextTypes, ConversationHandler, CallbackQueryHandler,
)
import openai
import os

# Config
TELEGRAM_TOKEN = os.getenv("7818234710:AAEm5lvMUextGN4cfReFjpFB4URYGglB-0U")
OPENAI_API_KEY = os.getenv("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")

# Constants
NAME, INTERESTS, STYLE, LENGTH = range(4)
RATE_LIMIT_SECONDS = 10  # Minimum seconds between requests per user
USERNAME_MIN_LEN = 5
USERNAME_MAX_LEN = 32
MAX_ATTEMPTS = 20
TARGET_USERNAMES_COUNT = 5
LEET_SUBSTITUTIONS = {
    'leet': '1337',
    'a': '4',
    'e': '3',
    'i': '1',
    'o': '0',
    's': '5',
}

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# OpenAI Setup
openai.api_key = OPENAI_API_KEY


# === DATABASE FUNCTIONS ===

async def init_db():
    logger.info("Initializing database...")
    async with aiosqlite.connect("usernames.db") as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS user_preferences (
            user_id INTEGER PRIMARY KEY,
            name TEXT,
            interests TEXT,
            style TEXT,
            length TEXT,
            last_request INTEGER
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS generation_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            available INTEGER,
            timestamp INTEGER
        )
        """)
        await db.commit()
    logger.info("Database initialized.")


async def save_user_preferences(user_id, name, interests, style, length):
    timestamp = int(time.time())
    async with aiosqlite.connect("usernames.db") as db:
        await db.execute("""
        INSERT INTO user_preferences (user_id, name, interests, style, length, last_request)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            name=excluded.name,
            interests=excluded.interests,
            style=excluded.style,
            length=excluded.length,
            last_request=excluded.last_request
        """, (user_id, name, interests, style, length, timestamp))
        await db.commit()
    logger.info(f"Saved preferences for user {user_id}")


async def update_last_request(user_id):
    timestamp = int(time.time())
    async with aiosqlite.connect("usernames.db") as db:
        await db.execute("UPDATE user_preferences SET last_request = ? WHERE user_id = ?", (timestamp, user_id))
        await db.commit()
    logger.info(f"Updated last request time for user {user_id}")


async def get_last_request(user_id):
    async with aiosqlite.connect("usernames.db") as db:
        async with db.execute("SELECT last_request FROM user_preferences WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return row[0]
    return None


async def save_generation_history(user_id, username, available):
    timestamp = int(time.time())
    async with aiosqlite.connect("usernames.db") as db:
        await db.execute("""
        INSERT INTO generation_history (user_id, username, available, timestamp)
        VALUES (?, ?, ?, ?)
        """, (user_id, username, int(available), timestamp))
        await db.commit()
    logger.info(f"Saved generation history for user {user_id} - {username} available: {available}")


# === USERNAME GENERATION & CHECKING ===

def clean_username(username: str) -> str:
    """Cleans and ensures username matches Telegram username rules."""
    username = username.lower()
    username = re.sub(r'[^a-z0-9_]', '', username)
    if len(username) < USERNAME_MIN_LEN:
        username += "123"  # pad short usernames
    return username[:USERNAME_MAX_LEN]


async def check_username_availability(bot, username: str) -> bool:
    """Check username availability via Telegram API getChat."""
    logger.info(f"Checking availability for username: {username}")
    try:
        await asyncio.sleep(0.5)  # delay to avoid rate limits
        await bot.get_chat(f"@{username}")
        logger.info(f"Username @{username} is taken.")
        return False
    except Exception as e:
        # If getChat fails, assume username is available
        logger.info(f"Username @{username} seems available (API error or not found): {e}")
        return True


def apply_leet_substitutions(username: str) -> str:
    """Apply leet substitutions."""
    for k, v in LEET_SUBSTITUTIONS.items():
        username = re.sub(k, v, username, flags=re.IGNORECASE)
    return username


async def generate_usernames_ai(name, interests, style, length_pref, count=TARGET_USERNAMES_COUNT):
    prompt = (
        f"Generate a list of {count*2} creative, stylish Telegram usernames based on the following preferences:\n"
        f"Name or nickname: {name}\n"
        f"Interests: {interests}\n"
        f"Style: {style}\n"
        f"Length preference: {length_pref if length_pref.lower() != 'skip' else 'none'}\n"
        f"Usernames must be 5-32 characters long, only letters, numbers, and underscores.\n"
        f"Return usernames as a comma-separated list without @."
    )
    try:
        logger.info("Calling OpenAI API for username generation...")
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role":"user", "content": prompt}],
            temperature=0.8,
            max_tokens=100,
        )
        text = response.choices[0].message.content
        logger.info(f"OpenAI response: {text}")
        # Extract usernames - assume comma separated
        usernames = re.split(r'[,\n]+', text)
        usernames = [clean_username(u.strip()) for u in usernames if u.strip()]
        return usernames
    except Exception as e:
        logger.error(f"OpenAI API failed: {e}")
        return []


def fallback_username_generator(name, style, length_pref, count=TARGET_USERNAMES_COUNT*2):
    logger.info("Using fallback username generator")
    base = (name + style).lower()
    base = re.sub(r'[^a-z0-9]', '', base)
    usernames = []
    for i in range(count):
        suffix = str(100 + i)
        candidate = base
        if length_pref.lower() == 'short':
            candidate = candidate[:6]
        elif length_pref.lower() == 'medium':
            candidate = candidate[:10]
        elif length_pref.lower() == 'long':
            candidate = candidate[:15]
        username = candidate + suffix
        username = clean_username(username)
        usernames.append(username)
    return usernames


async def generate_available_usernames(bot, user_id, name, interests, style, length_pref):
    # Rate limit check
    last_request = await get_last_request(user_id)
    now = int(time.time())
    if last_request and now - last_request < RATE_LIMIT_SECONDS:
        wait_time = RATE_LIMIT_SECONDS - (now - last_request)
        logger.warning(f"User {user_id} is rate limited. Must wait {wait_time} seconds.")
        return None, f"You're doing that too frequently. Please wait {wait_time} seconds before trying again."

    usernames_found = []
    attempts = 0
    use_leet = False

    while attempts < MAX_ATTEMPTS and len(usernames_found) < TARGET_USERNAMES_COUNT:
        if attempts == 0 or not use_leet:
            # AI generation
            generated = await generate_usernames_ai(name, interests, style, length_pref)
            if not generated:
                # fallback
                generated = fallback_username_generator(name, style, length_pref)
        else:
            # Apply leet substitution to previous list to retry
            generated = [apply_leet_substitutions(u) for u in generated]

        for username in generated:
            if username in usernames_found:
                continue
            if len(usernames_found) >= TARGET_USERNAMES_COUNT:
                break
            if len(username) < USERNAME_MIN_LEN or len(username) > USERNAME_MAX_LEN:
                continue
            available = await check_username_availability(bot, username)
            await save_generation_history(user_id, username, available)
            if available:
                usernames_found.append(username)
            attempts += 1
            if attempts >= MAX_ATTEMPTS:
                break

        if not usernames_found and not use_leet:
            logger.info("No usernames found, applying leet substitutions and retrying...")
            use_leet = True
            attempts = 0  # reset attempts for leet retry
        elif not usernames_found and use_leet:
            logger.info("No usernames found even after leet substitutions.")
            break

    await update_last_request(user_id)

    if usernames_found:
        return usernames_found, None
    else:
        return [], "Sorry, I couldn't find any available usernames. Try different preferences or try again later!"


# === BOT HANDLERS ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f"User {user.id} started the bot.")
    await update.message.reply_text(
        "Welcome! I'll help you generate unique and stylish Telegram usernames.\n"
        "Please tell me your *name or nickname*.",
        parse_mode=ParseMode.MARKDOWN
    )
    context.user_data.clear()
    return NAME


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f"User {user.id} canceled the conversation.")
    await update.message.reply_text("Process canceled. You can start again anytime with /start.")
    return ConversationHandler.END


async def collect_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    name = update.message.text.strip()
    logger.info(f"User {user.id} provided name: {name}")
    context.user_data['name'] = name
    await update.message.reply_text("Great! Now, what are your interests? (e.g., music, anime, tech)")
    return INTERESTS


async def collect_interests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    interests = update.message.text.strip()
    logger.info(f"User {user.id} provided interests: {interests}")
    context.user_data['interests'] = interests
    await update.message.reply_text(
        "Nice! What style do you want for your username? (e.g., cool, cute, hacker, minimal, aesthetic)"
    )
    return STYLE


async def collect_style(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    style = update.message.text.strip()
    logger.info(f"User {user.id} provided style: {style}")
    context.user_data['style'] = style
    await update.message.reply_text(
        "Optional: What's your preferred username length or initials? (short, medium, long or 'skip')"
    )
    return LENGTH


async def collect_length(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    length = update.message.text.strip()
    if length.lower() not in ['short', 'medium', 'long', 'skip']:
        await update.message.reply_text(
            "Please reply with 'short', 'medium', 'long', or 'skip'."
        )
        return LENGTH
    logger.info(f"User {user.id} provided length: {length}")
    context.user_data['length'] = length
    # Save preferences
    await save_user_preferences(user.id,
                                context.user_data['name'],
                                context.user_data['interests'],
                                context.user_data['style'],
                                context.user_data['length'])

    await update.message.reply_text("Thanks! Generating usernames for you now...")

    usernames, error_msg = await generate_available_usernames(
        context.bot,
        user.id,
        context.user_data['name'],
        context.user_data['interests'],
        context.user_data['style'],
        context.user_data['length'],
    )
    if error_msg:
        await update.message.reply_text(error_msg)
        return ConversationHandler.END

    # Format output with clickable usernames
    result_text = "Here are some available usernames:\n\n"
    for u in usernames:
        result_text += f"[@{u}](https://t.me/{u})\n"

    # Inline buttons
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Regenerate (same prefs)", callback_data="regen_same"),
            InlineKeyboardButton("Regenerate (new prefs)", callback_data="regen_new"),
        ]
    ])

    await update.message.reply_text(result_text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)

    return ConversationHandler.END


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "regen_same":
        # Retrieve last prefs
        async with aiosqlite.connect("usernames.db") as db:
            async with db.execute("SELECT name, interests, style, length FROM user_preferences WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
        if not row:
            await query.edit_message_text("No saved preferences found. Please /start again.")
            return

        name, interests, style, length_pref = row
        logger.info(f"User {user_id} requested regeneration with same preferences.")
        await query.edit_message_text("Regenerating usernames with the same preferences...")

        usernames, error_msg = await generate_available_usernames(
            context.bot, user_id, name, interests, style, length_pref
        )
        if error_msg:
            await query.edit_message_text(error_msg)
            return

        result_text = "Here are some available usernames:\n\n"
        for u in usernames:
            result_text += f"[@{u}](https://t.me/{u})\n"

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Regenerate (same prefs)", callback_data="regen_same"),
                InlineKeyboardButton("Regenerate (new prefs)", callback_data="regen_new"),
            ]
        ])

        await query.edit_message_text(result_text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)

    elif query.data == "regen_new":
        logger.info(f"User {user_id} requested regeneration with new preferences.")
        await query.edit_message_text("Let's start over. Please tell me your *name or nickname*.", parse_mode=ParseMode.MARKDOWN)
        context.user_data.clear()
        return NAME


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(msg="Exception while handling an update:", exc_info=context.error)


def main():
    logger.info("Starting bot...")

    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_name)],
            INTERESTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_interests)],
            STYLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_style)],
            LENGTH: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_length)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True,
    )

    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(CommandHandler('cancel', cancel))
    application.add_error_handler(error_handler)

    # Init DB before running
    asyncio.get_event_loop().run_until_complete(init_db())

    logger.info("Bot started.")
    application.run_polling()


if __name__ == '__main__':
    main()
