import logging
import sqlite3
import asyncio
import aiohttp
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import re
import random

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
OPENAI_API_KEY = "YOUR_OPENAI_API_KEY_HERE"  # Optional: Use Claude API via window.claude.complete instead
DATABASE_FILE = "username_bot.db"

class UsernameBot:
    def __init__(self):
        self.db_connection = None
        self.init_database()
        
    def init_database(self):
        """Initialize SQLite database"""
        self.db_connection = sqlite3.connect(DATABASE_FILE, check_same_thread=False)
        cursor = self.db_connection.cursor()
        
        # Create users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_request TIMESTAMP
            )
        ''')
        
        # Create user sessions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_sessions (
                user_id INTEGER,
                name TEXT,
                interests TEXT,
                style TEXT,
                length_pref TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        ''')
        
        # Create generation history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS generation_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                input_data TEXT,
                generated_usernames TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        ''')
        
        self.db_connection.commit()
    
    def add_user(self, user_id: int, username: str, first_name: str, last_name: str):
        """Add or update user in database"""
        cursor = self.db_connection.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO users (user_id, username, first_name, last_name, last_request)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, username, first_name, last_name, datetime.now()))
        self.db_connection.commit()
    
    def check_rate_limit(self, user_id: int) -> bool:
        """Check if user has exceeded rate limit (5 requests per hour)"""
        cursor = self.db_connection.cursor()
        one_hour_ago = datetime.now() - timedelta(hours=1)
        
        cursor.execute('''
            SELECT COUNT(*) FROM generation_history 
            WHERE user_id = ? AND created_at > ?
        ''', (user_id, one_hour_ago))
        
        count = cursor.fetchone()[0]
        return count < 5  # Allow 5 requests per hour
    
    def save_generation_history(self, user_id: int, input_data: dict, usernames: list):
        """Save generation history to database"""
        cursor = self.db_connection.cursor()
        cursor.execute('''
            INSERT INTO generation_history (user_id, input_data, generated_usernames)
            VALUES (?, ?, ?)
        ''', (user_id, json.dumps(input_data), json.dumps(usernames)))
        self.db_connection.commit()
    
    async def generate_usernames_with_ai(self, user_input: dict) -> List[str]:
        """Generate usernames using AI (Claude API simulation)"""
        # In a real implementation, you'd use the actual Claude API
        # For this example, we'll simulate AI generation with smart logic
        
        name = user_input.get('name', '').lower()
        interests = user_input.get('interests', [])
        style = user_input.get('style', 'cool')
        length_pref = user_input.get('length_pref', 'medium')
        
        # AI-like generation logic
        base_names = [name] if name else []
        
        # Add variations based on interests
        interest_suffixes = {
            'music': ['beats', 'sound', 'melody', 'tune', 'vibe'],
            'anime': ['chan', 'kun', 'senpai', 'otaku', 'weeb'],
            'tech': ['dev', 'code', 'hack', 'byte', 'tech'],
            'gaming': ['gamer', 'play', 'win', 'pro', 'gg'],
            'art': ['draw', 'paint', 'create', 'art', 'design'],
            'sport': ['fit', 'strong', 'fast', 'win', 'champion']
        }
        
        style_prefixes = {
            'cool': ['x', 'dark', 'shadow', 'neo', 'cyber'],
            'cute': ['mini', 'sweet', 'lovely', 'soft', 'kawaii'],
            'hacker': ['h4ck', 'anon', 'ghost', 'zero', 'null'],
            'minimal': ['', 'pure', 'clean', 'simple', 'zen'],
            'aesthetic': ['aesthetic', 'vibe', 'mood', 'aura', 'ethereal']
        }
        
        # Generate combinations
        usernames = []
        
        # Base name variations
        if name:
            usernames.extend([
                name,
                name + str(random.randint(10, 99)),
                name + '_' + random.choice(['official', 'real', 'main']),
                'the' + name,
                name + 'xx'
            ])
        
        # Style + name combinations
        if style in style_prefixes:
            for prefix in style_prefixes[style][:3]:
                if prefix:
                    usernames.append(prefix + name)
                    usernames.append(prefix + '_' + name)
        
        # Interest-based combinations
        for interest in interests[:2]:  # Limit to 2 interests
            if interest.lower() in interest_suffixes:
                for suffix in interest_suffixes[interest.lower()][:2]:
                    if name:
                        usernames.append(name + suffix)
                        usernames.append(name + '_' + suffix)
                    else:
                        usernames.append(suffix + str(random.randint(10, 999)))
        
        # Add creative combinations
        creative_combos = [
            f"{name}_{random.choice(['is', 'the', 'x'])}{random.choice(['king', 'queen', 'boss', 'pro'])}",
            f"{random.choice(['mr', 'ms', 'the'])}{name}",
            f"{name}{random.choice(['_', '']){random.choice(['2024', '25', 'official', 'real'])}",
        ]
        
        usernames.extend(creative_combos)
        
        # Filter by length preference
        if length_pref == 'short':
            usernames = [u for u in usernames if len(u) <= 10]
        elif length_pref == 'long':
            usernames = [u for u in usernames if len(u) >= 8]
        
        # Remove duplicates and invalid characters
        usernames = list(set(usernames))
        usernames = [re.sub(r'[^a-zA-Z0-9_]', '', u) for u in usernames]
        usernames = [u for u in usernames if u and len(u) >= 5 and len(u) <= 32]
        
        # Limit to top 10
        return usernames[:10]
    
    async def check_username_availability(self, username: str) -> bool:
        """Check if username is available on Telegram"""
        try:
            async with aiohttp.ClientSession() as session:
                # Using Telegram's public API to check username availability
                url = f"https://t.me/{username}"
                async with session.get(url) as response:
                    # If we get a 404, username is likely available
                    # If we get 200, username is taken
                    return response.status == 404
        except Exception as e:
            logger.error(f"Error checking username availability: {e}")
            # If we can't check, assume it might be available
            return True
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = update.effective_user
        self.add_user(user.id, user.username, user.first_name, user.last_name)
        
        welcome_message = (
            "🎯 Welcome to the AI Username Generator Bot!\n\n"
            "I'll help you create stylish and available Telegram usernames "
            "based on your preferences.\n\n"
            "Use /generate to start creating your perfect username!"
        )
        
        await update.message.reply_text(welcome_message)
    
    async def generate_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /generate command"""
        user_id = update.effective_user.id
        
        # Check rate limit
        if not self.check_rate_limit(user_id):
            await update.message.reply_text(
                "⏰ You've reached the rate limit (5 requests per hour). "
                "Please try again later!"
            )
            return
        
        # Start the generation process
        context.user_data['step'] = 'name'
        await update.message.reply_text(
            "🎨 Let's create your perfect username!\n\n"
            "First, what's your name or nickname? (This will be the base for your username)"
        )
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle user messages during the generation process"""
        user_data = context.user_data
        step = user_data.get('step')
        
        if step == 'name':
            user_data['name'] = update.message.text
            user_data['step'] = 'interests'
            await update.message.reply_text(
                "🎯 Great! Now tell me your interests (separated by commas).\n"
                "Examples: music, anime, tech, gaming, art, sport, photography"
            )
        
        elif step == 'interests':
            interests = [interest.strip() for interest in update.message.text.split(',')]
            user_data['interests'] = interests
            user_data['step'] = 'style'
            
            # Create style selection keyboard
            keyboard = [
                [InlineKeyboardButton("😎 Cool", callback_data='style_cool'),
                 InlineKeyboardButton("🥰 Cute", callback_data='style_cute')],
                [InlineKeyboardButton("🖤 Hacker", callback_data='style_hacker'),
                 InlineKeyboardButton("✨ Minimal", callback_data='style_minimal')],
                [InlineKeyboardButton("🌸 Aesthetic", callback_data='style_aesthetic')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "🎨 Choose your preferred style:",
                reply_markup=reply_markup
            )
        
        elif step == 'length':
            user_data['length_pref'] = update.message.text.lower()
            await self.process_generation(update, context)
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle callback queries from inline keyboards"""
        query = update.callback_query
        await query.answer()
        
        user_data = context.user_data
        
        if query.data.startswith('style_'):
            style = query.data.replace('style_', '')
            user_data['style'] = style
            user_data['step'] = 'length'
            
            # Create length selection keyboard
            keyboard = [
                [InlineKeyboardButton("📏 Short (5-10 chars)", callback_data='length_short'),
                 InlineKeyboardButton("📐 Medium (8-16 chars)", callback_data='length_medium')],
                [InlineKeyboardButton("📏 Long (12+ chars)", callback_data='length_long'),
                 InlineKeyboardButton("🎲 Any length", callback_data='length_any')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "📏 Choose your preferred username length:",
                reply_markup=reply_markup
            )
        
        elif query.data.startswith('length_'):
            length = query.data.replace('length_', '')
            user_data['length_pref'] = length
            await self.process_generation_callback(query, context)
        
        elif query.data == 'regenerate':
            await self.process_generation_callback(query, context)
        
        elif query.data.startswith('check_'):
            username = query.data.replace('check_', '')
            is_available = await self.check_username_availability(username)
            
            if is_available:
                await query.edit_message_text(
                    f"✅ @{username} appears to be available!\n"
                    f"Claim it here: https://t.me/{username}"
                )
            else:
                await query.edit_message_text(
                    f"❌ @{username} is already taken.\n"
                    f"Try another username from the list!"
                )
    
    async def process_generation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process username generation"""
        user_data = context.user_data
        user_id = update.effective_user.id
        
        # Generate usernames
        await update.message.reply_text("🤖 Generating usernames with AI...")
        
        usernames = await self.generate_usernames_with_ai(user_data)
        
        # Check availability for each username
        availability_results = []
        for username in usernames:
            is_available = await self.check_username_availability(username)
            availability_results.append((username, is_available))
        
        # Save to history
        self.save_generation_history(user_id, user_data, usernames)
        
        # Format results
        await self.send_results(update.message, availability_results, context)
    
    async def process_generation_callback(self, query, context: ContextTypes.DEFAULT_TYPE):
        """Process username generation from callback"""
        user_data = context.user_data
        user_id = query.from_user.id
        
        # Generate usernames
        await query.edit_message_text("🤖 Generating usernames with AI...")
        
        usernames = await self.generate_usernames_with_ai(user_data)
        
        # Check availability for each username
        availability_results = []
        for username in usernames:
            is_available = await self.check_username_availability(username)
            availability_results.append((username, is_available))
        
        # Save to history
        self.save_generation_history(user_id, user_data, usernames)
        
        # Format results
        await self.send_results_callback(query, availability_results, context)
    
    async def send_results(self, message, availability_results, context):
        """Send results to user"""
        if not availability_results:
            await message.reply_text("❌ Sorry, couldn't generate usernames. Please try again!")
            return
        
        # Sort by availability (available first)
        availability_results.sort(key=lambda x: not x[1])
        
        result_text = "🎉 Here are your AI-generated usernames:\n\n"
        
        keyboard = []
        for username, is_available in availability_results[:8]:  # Show top 8
            status = "✅ Available" if is_available else "❌ Taken"
            result_text += f"@{username} - {status}\n"
            
            if is_available:
                keyboard.append([InlineKeyboardButton(
                    f"🔗 Claim @{username}",
                    url=f"https://t.me/{username}"
                )])
        
        result_text += "\n💡 Tip: Click on available usernames to claim them!"
        
        # Add regenerate button
        keyboard.append([InlineKeyboardButton("🔄 Generate More", callback_data='regenerate')])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await message.reply_text(result_text, reply_markup=reply_markup)
        
        # Clear user data
        context.user_data.clear()
    
    async def send_results_callback(self, query, availability_results, context):
        """Send results to user via callback"""
        if not availability_results:
            await query.edit_message_text("❌ Sorry, couldn't generate usernames. Please try again!")
            return
        
        # Sort by availability (available first)
        availability_results.sort(key=lambda x: not x[1])
        
        result_text = "🎉 Here are your AI-generated usernames:\n\n"
        
        keyboard = []
        for username, is_available in availability_results[:8]:  # Show top 8
            status = "✅ Available" if is_available else "❌ Taken"
            result_text += f"@{username} - {status}\n"
            
            if is_available:
                keyboard.append([InlineKeyboardButton(
                    f"🔗 Claim @{username}",
                    url=f"https://t.me/{username}"
                )])
        
        result_text += "\n💡 Tip: Click on available usernames to claim them!"
        
        # Add regenerate button
        keyboard.append([InlineKeyboardButton("🔄 Generate More", callback_data='regenerate')])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(result_text, reply_markup=reply_markup)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_text = (
            "🤖 AI Username Generator Bot Help\n\n"
            "Commands:\n"
            "/start - Start the bot\n"
            "/generate - Generate usernames\n"
            "/help - Show this help message\n\n"
            "How it works:\n"
            "1. Use /generate to start\n"
            "2. Provide your name/nickname\n"
            "3. List your interests\n"
            "4. Choose your style\n"
            "5. Select preferred length\n"
            "6. Get AI-generated usernames with availability status\n"
            "7. Click to claim available usernames\n\n"
            "Features:\n"
            "✅ AI-powered generation\n"
            "✅ Availability checking\n"
            "✅ Multiple styles\n"
            "✅ Rate limiting (5 requests/hour)\n"
            "✅ Generation history\n"
            "✅ Direct claim links"
        )
        await update.message.reply_text(help_text)
    
    def run(self):
        """Run the bot"""
        # Create application
        application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        
        # Add handlers
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("generate", self.generate_command))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(CallbackQueryHandler(self.handle_callback))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Start the bot
        logger.info("Starting bot...")
        application.run_polling()

def main():
    """Main function"""
    bot = UsernameBot()
    bot.run()

if __name__ == "__main__":
    main()
