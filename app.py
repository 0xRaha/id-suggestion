import sqlite3
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from transformers import pipeline
import requests
import logging
import time

# Configure logging to show on console
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[logging.StreamHandler()]  # Output to console
)
logger = logging.getLogger(__name__)

# Conversation states
NAME, INTERESTS, STYLE, LENGTH = range(4)

# Initialize AI model for username generation (using a lightweight model)
try:
    generator = pipeline("text-generation", model="distilgpt2")
    logger.info("AI model (distilgpt2) loaded successfully")
except Exception as e:
    logger.error(f"Failed to load AI model: {e}")
    generator = None

# Leet code substitutions
LEET_SUBS = {
    'leet': '1337',
    'a': '4',
    'e': '3',
    'i': '1',
    'o': '0',
    's': '5',
}

# SQLite database setup
def init_db():
    logger.info("Initializing SQLite database")
    conn = sqlite3.connect("user_data.db")
    c = conn.cursor()
    c.execute(
        """CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            name TEXT,
            interests TEXT,
            style TEXT,
            length TEXT,
            last_request TIMESTAMP
        )"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS history (
            user_id INTEGER,
            username TEXT,
            available INTEGER,
            timestamp TIMESTAMP
        )"""
    )
    conn.commit()
    conn.close()
    logger.info("Database initialized")

# Check username availability via Telegram API
def check_username_availability(username):
    logger.info(f"Checking availability of username: @{username}")
    try:
        response = requests.get(
            f"https://api.telegram.org/bot{YOUR_BOT_TOKEN}/getChat",
            params={"chat_id": f"@{username}"}
        )
        data = response.json()
        is_available = not data["ok"]  # If request fails, username is likely available
        logger.info(f"Username @{username} is {'available' if is_available else 'taken'}")
        return is_available
    except Exception as e:
        logger.error(f"Error checking username @{username}: {e}")
        return False

# Apply leet substitutions to a username
def apply_leet_substitutions(username):
    logger.info(f"Applying leet substitutions to: {username}")
    modified = username.lower()
    for key, value in LEET_SUBS.items():
        modified = modified.replace(key, value)
    logger.info(f"Leet substituted username: {modified}")
    return modified

# Generate usernames using AI or fallback
def generate_usernames(name, interests, style, length=None, use_leet=False):
    logger.info(f"Generating usernames for name: {name}, interests: {interests}, style: {style}, length: {length}, leet: {use_leet}")
    prompt = f"Generate creative Telegram usernames for a user named {name} who likes {interests}. The style should be {style}."
    if length:
        prompt += f" The username should be {length} characters long."
    
    max_attempts = 20  # Limit total attempts to avoid infinite loops
    min_available = 5  # Minimum number of available usernames to return
    usernames = []
    attempts = 0

    while len([u for u, avail in usernames if avail]) < min_available and attempts < max_attempts:
        try:
            if generator:
                results = generator(prompt, max_length=50, num_return_sequences=10, truncation=True)
                for result in results:
                    text = result["generated_text"].strip()
                    match = re.search(r"[a-zA-Z0-9_]{5,32}", text)
                    if match:
                        username = match.group(0)
                        if len(username) >= 5:
                            if use_leet:
                                username = apply_leet_substitutions(username)
                            is_available = check_username_availability(username)
                            if is_available:  # Only add available usernames
                                usernames.append((username, is_available))
            else:
                # Fallback if AI model is unavailable
                username = f"{name}{style}{attempts}"
                if use_leet:
                    username = apply_leet_substitutions(username)
                is_available = check_username_availability(username)
                if is_available:
                    usernames.append((username, is_available))
        except Exception as e:
            logger.error(f"Error generating usernames: {e}")
        attempts += 1
        time.sleep(0.5)  # Avoid hitting API rate limits

    # If still not enough available usernames, try leet substitutions
    if len([u for u, avail in usernames if avail]) < min_available and not use_leet:
        logger.info("Not enough available usernames, retrying with leet substitutions")
        return generate_usernames(name, interests, style, length, use_leet=True)
    
    # Filter only available usernames
    available_usernames = [(u, a) for u, a in usernames if a]
    logger.info(f"Generated {len(available_usernames)} available usernames")
    return available_usernames[:10]  # Limit to 10 usernames

# Store user data in SQLite
def store_user_data(user_id, name, interests, style, length):
    logger.info(f"Storing user data for user_id: {user_id}")
    conn = sqlite3.connect("user_data.db")
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO users (user_id, name, interests, style, length, last_request) VALUES (?, ?, ?, ?, ?, datetime('now'))",
        (user_id, name, interests, style, length)
    )
    conn.commit()
    conn.close()
    logger.info("User data stored")

# Store generated usernames in history
def store_username_history(user_id, usernames):
    logger.info(f"Storing username history for user_id: {user_id}")
    conn = sqlite3.connect("user_data.db")
    c = conn.cursor()
    for username, available in usernames:
        c.execute(
            "INSERT INTO history (user_id, username, available, timestamp) VALUES (?, ?, ?, datetime('now'))",
            (user_id, username, 1 if available else 0)
        )
    conn.commit()
    conn.close()
    logger.info("Username history stored")

# Check rate limit (5 requests per hour)
def check_rate_limit(user_id):
    logger.info(f"Checking rate limit for user_id: {user_id}")
    conn = sqlite3.connect("user_data.db")
    c = conn.cursor()
    c.execute(
        "SELECT last_request FROM users WHERE user_id = ? AND last_request > datetime('now', '-1 hour')",
        (user_id,)
    )
    result = c.fetchone()
    conn.close()
    is_allowed = result is None
    logger.info(f"Rate limit check: {'Allowed' if is_allowed else 'Blocked'}")
    return is_allowed

# Bot handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"User {update.effective_user.id} started conversation")
    await update.message.reply_text(
        "Hi! I'm a username generator bot. Let's create a cool Telegram username for you!\n"
        "What's your name or nickname?"
    )
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text
    logger.info(f"User {update.effective_user.id} provided name: {context.user_data['name']}")
    await update.message.reply_text("Great! What are your interests (e.g., music, anime, tech)?")
    return INTERESTS

async def get_interests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["interests"] = update.message.text
    logger.info(f"User {update.effective_user.id} provided interests: {context.user_data['interests']}")
    await update.message.reply_text(
        "Nice! What style do you prefer for your username (e.g., cool, cute, hacker, minimal, aesthetic)?"
    )
    return STYLE

async def get_style(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["style"] = update.message.text
    logger.info(f"User {update.effective_user.id} provided style: {context.user_data['style']}")
    await update.message.reply_text(
        "Got it! Any preference for username length or initials? (e.g., short, medium, long, or include initials). Reply 'skip' if no preference."
    )
    return LENGTH

async def get_length(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f"User {user_id} provided length: {update.message.text}")
    if not check_rate_limit(user_id):
        logger.info(f"User {user_id} hit rate limit")
        await update.message.reply_text("You've hit the rate limit. Try again in an hour!")
        return ConversationHandler.END

    length = update.message.text if update.message.text.lower() != "skip" else None
    context.user_data["length"] = length

    # Store user data
    store_user_data(
        user_id,
        context.user_data["name"],
        context.user_data["interests"],
        context.user_data["style"],
        length
    )

    # Generate usernames
    usernames = generate_usernames(
        context.user_data["name"],
        context.user_data["interests"],
        context.user_data["style"],
        length
    )

    # Store history
    store_username_history(user_id, usernames)

    # Prepare response
    if not usernames:
        logger.info(f"No available usernames found for user {user_id}")
        response = "Sorry, I couldn't find any available usernames. Try different preferences or try again later!"
    else:
        response = "Here are your available usernames:\n\n"
        for username, _ in usernames:
            response += f"[@{username}](https://t.me/{username})\n"

    # Add regenerate button
    keyboard = [
        [InlineKeyboardButton("Regenerate with same preferences", callback_data="regenerate_same")],
        [InlineKeyboardButton("Regenerate with new preferences", callback_data="regenerate_new")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(response, reply_markup=reply_markup, parse_mode="Markdown", disable_web_page_preview=True)
    logger.info(f"Sent {len(usernames)} available usernames to user {user_id}")
    return ConversationHandler.END

async def regenerate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    logger.info(f"User {user_id} requested regeneration: {query.data}")

    if not check_rate_limit(user_id):
        logger.info(f"User {user_id} hit rate limit during regeneration")
        await query.message.reply_text("You've hit the rate limit. Try again in an hour!")
        return

    if query.data == "regenerate_same":
        # Regenerate with same preferences
        usernames = generate_usernames(
            context.user_data.get("name", ""),
            context.user_data.get("interests", ""),
            context.user_data.get("style", ""),
            context.user_data.get("length", None)
        )
        store_username_history(user_id, usernames)

        if not usernames:
            logger.info(f"No available usernames found for user {user_id} during regeneration")
            response = "Sorry, I couldn't find any available usernames. Try different preferences or try again later!"
        else:
            response = "Regenerated available usernames:\n\n"
            for username, _ in usernames:
                response += f"[@{username}](https://t.me/{username})\n"

        keyboard = [
            [InlineKeyboardButton("Regenerate with same preferences", callback_data="regenerate_same")],
            [InlineKeyboardButton("Regenerate with new preferences", callback_data="regenerate_new")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.message.reply_text(response, reply_markup=reply_markup, parse_mode="Markdown", disable_web_page_preview=True)
        logger.info(f"Sent {len(usernames)} regenerated usernames to user {user_id}")

    elif query.data == "regenerate_new":
        logger.info(f"User {user_id} starting new preferences")
        await query.message.reply_text("Let's start over! What's your name or nickname?")
        return NAME

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"User {update.effective_user.id} cancelled conversation")
    await update.message.reply_text("Username generation cancelled. Use /start to try again!")
    return ConversationHandler.END

def main():
    init_db()
    YOUR_BOT_TOKEN = "7818234710:AAEm5lvMUextGN4cfReFjpFB4URYGglB-0U"
    logger.info("Starting bot...")
    application = Application.builder().token(YOUR_BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            INTERESTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_interests)],
            STYLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_style)],
            LENGTH: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_length)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(regenerate))
    logger.info("Bot handlers registered, starting polling...")
    application.run_polling()

if __name__ == "__main__":
    main()
