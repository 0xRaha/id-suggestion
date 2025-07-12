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

# Enable logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Conversation states
NAME, INTERESTS, STYLE, LENGTH = range(4)

# Initialize AI model for username generation (using a lightweight model)
generator = pipeline("text-generation", model="distilgpt2")

# SQLite database setup
def init_db():
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

# Check username availability via Telegram API
def check_username_availability(username):
    try:
        # Telegram doesn't have a direct API for checking username availability,
        # so we attempt to resolve the username via a chat info request
        response = requests.get(
            f"https://api.telegram.org/bot{YOUR_BOT_TOKEN}/getChat",
            params={"chat_id": f"@{username}"}
        )
        data = response.json()
        return not data["ok"]  # If request fails, username is likely available
    except Exception as e:
        logger.error(f"Error checking username {username}: {e}")
        return False

# Generate usernames using AI
def generate_usernames(name, interests, style, length=None):
    prompt = f"Generate creative Telegram usernames for a user named {name} who likes {interests}. The style should be {style}."
    if length:
        prompt += f" The username should be {length} characters long."
    
    try:
        # Generate text using the AI model
        results = generator(prompt, max_length=50, num_return_sequences=10, truncation=True)
        usernames = []
        for result in results:
            # Extract and clean generated text
            text = result["generated_text"].strip()
            # Simple regex to extract potential usernames
            match = re.search(r"[a-zA-Z0-9_]{5,32}", text)
            if match:
                username = match.group(0)
                if len(username) >= 5:  # Telegram username minimum length
                    usernames.append(username)
        
        # Filter and check availability
        available_usernames = []
        for username in usernames[:10]:  # Limit to 10 usernames
            is_available = check_username_availability(username)
            available_usernames.append((username, is_available))
        
        return available_usernames
    except Exception as e:
        logger.error(f"Error generating usernames: {e}")
        return []

# Store user data in SQLite
def store_user_data(user_id, name, interests, style, length):
    conn = sqlite3.connect("user_data.db")
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO users (user_id, name, interests, style, length, last_request) VALUES (?, ?, ?, ?, ?, datetime('now'))",
        (user_id, name, interests, style, length)
    )
    conn.commit()
    conn.close()

# Store generated usernames in history
def store_username_history(user_id, usernames):
    conn = sqlite3.connect("user_data.db")
    c = conn.cursor()
    for username, available in usernames:
        c.execute(
            "INSERT INTO history (user_id, username, available, timestamp) VALUES (?, ?, ?, datetime('now'))",
            (user_id, username, 1 if available else 0)
        )
    conn.commit()
    conn.close()

# Check rate limit (e.g., 5 requests per hour)
def check_rate_limit(user_id):
    conn = sqlite3.connect("user_data.db")
    c = conn.cursor()
    c.execute(
        "SELECT last_request FROM users WHERE user_id = ? AND last_request > datetime('now', '-1 hour')",
        (user_id,)
    )
    result = c.fetchone()
    conn.close()
    return result is None

# Bot handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hi! I'm a username generator bot. Let's create a cool Telegram username for you!\n"
        "What's your name or nickname?"
    )
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text
    await update.message.reply_text("Great! What are your interests (e.g., music, anime, tech)?")
    return INTERESTS

async def get_interests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["interests"] = update.message.text
    await update.message.reply_text(
        "Nice! What style do you prefer for your username (e.g., cool, cute, hacker, minimal, aesthetic)?"
    )
    return STYLE

async def get_style(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["style"] = update.message.text
    await update.message.reply_text(
        "Got it! Any preference for username length or initials? (e.g., short, medium, long, or include initials). Reply 'skip' if no preference."
    )
    return LENGTH

async def get_length(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not check_rate_limit(user_id):
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
    response = "Here are your generated usernames:\n\n"
    for username, available in usernames:
        status = "✅ Available" if available else "❌ Taken"
        link = f"https://t.me/{username}" if available else ""
        response += f"@{username} - {status} {link}\n"

    # Add regenerate button
    keyboard = [
        [InlineKeyboardButton("Regenerate with same preferences", callback_data="regenerate_same")],
        [InlineKeyboardButton("Regenerate with new preferences", callback_data="regenerate_new")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(response, reply_markup=reply_markup, disable_web_page_preview=True)
    return ConversationHandler.END

async def regenerate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    if not check_rate_limit(user_id):
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

        response = "Regenerated usernames:\n\n"
        for username, available in usernames:
            status = "✅ Available" if available else "❌ Taken"
            link = f"https://t.me/{username}" if available else ""
            response += f"@{username} - {status} {link}\n"

        keyboard = [
            [InlineKeyboardButton("Regenerate with same preferences", callback_data="regenerate_same")],
            [InlineKeyboardButton("Regenerate with new preferences", callback_data="regenerate_new")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.message.reply_text(response, reply_markup=reply_markup, disable_web_page_preview=True)

    elif query.data == "regenerate_new":
        await query.message.reply_text("Let's start over! What's your name or nickname?")
        return NAME

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Username generation cancelled. Use /start to try again!")
    return ConversationHandler.END

def main():
    # Initialize database
    init_db()

    # Replace YOUR_BOT_TOKEN with your actual bot token
    YOUR_BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
    application = Application.builder().token(YOUR_BOT_TOKEN).build()

    # Conversation handler
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

    # Add handlers
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(regenerate))

    # Start the bot
    application.run_polling()

if __name__ == "__main__":
    main()
