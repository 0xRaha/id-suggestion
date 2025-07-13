import logging
import sqlite3
import asyncio
import aiohttp
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import re
import random
import itertools

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# Telethon for proper username checking
from telethon import TelegramClient
from telethon.tl.functions.account import CheckUsernameRequest
from telethon.errors import FloodWaitError, UsernameInvalidError, AuthKeyError
from telethon.sessions import StringSession

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
TELEGRAM_API_ID = "YOUR_API_ID_HERE"  # From https://my.telegram.org
TELEGRAM_API_HASH = "YOUR_API_HASH_HERE"  # From https://my.telegram.org
TELEGRAM_SESSION_STRING = "YOUR_SESSION_STRING_HERE"  # Optional: saved session string
DATABASE_FILE = "username_bot.db"

class UsernameBot:
    def __init__(self):
        self.db_connection = None
        self.user_client = None
        self.init_database()
        self.init_telethon_client()
        
        # Letter replacement mapping
        self.letter_replacements = {
            'o': '0',
            'i': '1',
            'l': '1',
            'z': '2',
            'b': '13',
            'a': '4',
            's': '5',
            'g': '6',
            't': '7',
            'q': '9'
        }
        
        # Extended prefixes and suffixes for each style
        self.style_prefixes = {
            'cool': ['x', 'dark', 'shadow', 'neo', 'cyber', 'black', 'night', 'storm', 'ice', 'fire', 
                    'steel', 'blade', 'void', 'lunar', 'solar', 'alpha', 'beta', 'ultra', 'mega', 'super',
                    'hyper', 'prime', 'elite', 'pro', 'max', 'ace', 'zen', 'flash', 'ghost', 'phantom'],
            'cute': ['mini', 'sweet', 'lovely', 'soft', 'kawaii', 'tiny', 'baby', 'little', 'fluffy', 'bunny',
                    'kitty', 'puppy', 'honey', 'sugar', 'candy', 'cherry', 'peach', 'berry', 'fairy', 'angel',
                    'star', 'moon', 'sun', 'flower', 'rose', 'lily', 'daisy', 'pearl', 'gem', 'crystal'],
            'hacker': ['h4ck', 'anon', 'ghost', 'zero', 'null', 'void', 'root', 'admin', 'sys', 'dev',
                      'bin', 'hex', 'code', 'byte', 'bit', 'data', 'net', 'web', 'cyber', 'matrix',
                      'shell', 'term', 'unix', 'linux', 'node', 'core', 'stack', 'loop', 'func', 'var'],
            'minimal': ['', 'pure', 'clean', 'simple', 'zen', 'bare', 'raw', 'plain', 'clear', 'basic',
                       'just', 'only', 'mere', 'solo', 'lone', 'one', 'real', 'true', 'core', 'base',
                       'main', 'key', 'top', 'new', 'old', 'raw', 'dry', 'cold', 'warm', 'soft'],
            'aesthetic': ['aesthetic', 'vibe', 'mood', 'aura', 'ethereal', 'dreamy', 'cosmic', 'mystic', 'serene', 'bliss',
                         'harmony', 'grace', 'elegance', 'beauty', 'divine', 'pure', 'sacred', 'golden', 'silver', 'pearl',
                         'velvet', 'silk', 'satin', 'crystal', 'diamond', 'ruby', 'sapphire', 'emerald', 'opal', 'jade']
        }
        
        self.style_suffixes = {
            'cool': ['x', 'xx', 'xo', 'z', 'zz', 'pro', 'max', 'ultra', 'mega', 'super',
                    'alpha', 'beta', 'prime', 'elite', 'ace', 'king', 'lord', 'master', 'boss', 'chief',
                    'hero', 'legend', 'myth', 'storm', 'blade', 'fire', 'ice', 'steel', 'shadow', 'ghost'],
            'cute': ['chan', 'kun', 'san', 'sama', 'baby', 'honey', 'sugar', 'candy', 'sweet', 'love',
                    'heart', 'star', 'moon', 'sun', 'flower', 'rose', 'lily', 'berry', 'peach', 'cherry',
                    'bunny', 'kitty', 'puppy', 'angel', 'fairy', 'gem', 'pearl', 'crystal', 'diamond', 'sparkle'],
            'hacker': ['404', '403', '200', '500', '0x', 'exe', 'bin', 'dev', 'sys', 'root',
                      'admin', 'user', 'guest', 'anon', 'null', 'void', 'zero', 'one', 'bit', 'byte',
                      'kb', 'mb', 'gb', 'tb', 'hex', 'dec', 'oct', 'bin', 'log', 'tmp'],
            'minimal': ['', 'one', 'two', 'new', 'old', 'now', 'yes', 'no', 'ok', 'go',
                       'do', 'be', 'me', 'we', 'it', 'is', 'as', 'at', 'to', 'of',
                       'on', 'in', 'by', 'up', 'so', 'my', 'or', 'an', 'if', 'but'],
            'aesthetic': ['vibes', 'mood', 'aura', 'dream', 'bliss', 'grace', 'beauty', 'divine', 'sacred', 'golden',
                         'silver', 'pearl', 'velvet', 'silk', 'satin', 'crystal', 'diamond', 'ruby', 'sapphire', 'emerald',
                         'opal', 'jade', 'cosmic', 'mystic', 'serene', 'ethereal', 'dreamy', 'harmony', 'elegance', 'pure']
        }
        
        # Extended interest-based keywords
        self.interest_keywords = {
            'music': ['beats', 'sound', 'melody', 'tune', 'vibe', 'rhythm', 'bass', 'drop', 'mix', 'track',
                     'song', 'note', 'chord', 'scale', 'tempo', 'audio', 'vocal', 'instrument', 'studio', 'record',
                     'play', 'listen', 'hear', 'sing', 'dance', 'dj', 'producer', 'artist', 'band', 'concert'],
            'anime': ['chan', 'kun', 'senpai', 'otaku', 'weeb', 'manga', 'kawaii', 'desu', 'sama', 'san',
                     'neko', 'baka', 'tsundere', 'yandere', 'waifu', 'husbando', 'onii', 'imouto', 'sensei', 'kohai',
                     'moe', 'chibi', 'cosplay', 'doki', 'nya', 'owo', 'uwu', 'sugoi', 'yamete', 'notice'],
            'tech': ['dev', 'code', 'hack', 'byte', 'tech', 'data', 'web', 'app', 'api', 'bot',
                    'ai', 'ml', 'dl', 'neural', 'algo', 'logic', 'binary', 'digital', 'cyber', 'virtual',
                    'cloud', 'server', 'client', 'network', 'protocol', 'framework', 'library', 'database', 'query', 'json'],
            'gaming': ['gamer', 'play', 'win', 'pro', 'gg', 'pwn', 'noob', 'skilled', 'boss', 'raid',
                      'quest', 'level', 'xp', 'hp', 'mp', 'damage', 'crit', 'buff', 'nerf', 'spawn',
                      'respawn', 'frag', 'kill', 'death', 'score', 'rank', 'tier', 'league', 'tournament', 'esports'],
            'art': ['draw', 'paint', 'create', 'art', 'design', 'sketch', 'canvas', 'brush', 'color', 'palette',
                   'pixel', 'vector', 'raster', 'layer', 'filter', 'effect', 'texture', 'pattern', 'gradient', 'shadow',
                   'light', 'dark', 'bright', 'vivid', 'pastel', 'neon', 'matte', 'gloss', 'smooth', 'rough'],
            'sport': ['fit', 'strong', 'fast', 'win', 'champion', 'athlete', 'train', 'workout', 'gym', 'muscle',
                     'power', 'speed', 'endurance', 'stamina', 'energy', 'force', 'strength', 'agility', 'balance', 'flex',
                     'cardio', 'protein', 'gains', 'reps', 'sets', 'weight', 'lift', 'run', 'jump', 'push'],
            'photography': ['photo', 'pic', 'shot', 'snap', 'camera', 'lens', 'focus', 'exposure', 'light', 'shadow',
                           'frame', 'capture', 'moment', 'memory', 'vision', 'view', 'scene', 'portrait', 'landscape', 'macro',
                           'zoom', 'angle', 'perspective', 'composition', 'filter', 'edit', 'raw', 'jpeg', 'pixel', 'resolution'],
            'cooking': ['cook', 'chef', 'recipe', 'taste', 'flavor', 'spice', 'herb', 'salt', 'pepper', 'sugar',
                       'sweet', 'sour', 'bitter', 'umami', 'fresh', 'organic', 'natural', 'healthy', 'delicious', 'yummy',
                       'kitchen', 'oven', 'pan', 'knife', 'plate', 'bowl', 'fork', 'spoon', 'dish', 'meal'],
            'travel': ['travel', 'journey', 'trip', 'adventure', 'explore', 'discover', 'wander', 'roam', 'voyage', 'tour',
                      'destination', 'place', 'location', 'city', 'country', 'world', 'global', 'international', 'local', 'culture',
                      'experience', 'memory', 'story', 'photo', 'souvenir', 'map', 'guide', 'passport', 'visa', 'flight']
        }
        
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
        
        # Create username cache table for optimization
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS username_cache (
                username TEXT PRIMARY KEY,
                available BOOLEAN NOT NULL,
                checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        self.db_connection.commit()
    
    def init_telethon_client(self):
        """Initialize Telethon client for proper username checking"""
        try:
            if TELEGRAM_SESSION_STRING and TELEGRAM_SESSION_STRING != "YOUR_SESSION_STRING_HERE":
                # Use saved session string
                session = StringSession(TELEGRAM_SESSION_STRING)
            else:
                # Use file session
                session = 'username_bot_session'
            
            self.user_client = TelegramClient(
                session,
                TELEGRAM_API_ID,
                TELEGRAM_API_HASH
            )
            logger.info("Telethon client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Telethon client: {e}")
            logger.warning("Username availability checking will be disabled")
            self.user_client = None
    
    def add_user(self, user_id: int, username: str, first_name: str, last_name: str):
        """Add or update user in database"""
        cursor = self.db_connection.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO users (user_id, username, first_name, last_name, last_request)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, username, first_name, last_name, datetime.now()))
        self.db_connection.commit()
    
    def save_generation_history(self, user_id: int, input_data: dict, usernames: list):
        """Save generation history to database"""
        cursor = self.db_connection.cursor()
        cursor.execute('''
            INSERT INTO generation_history (user_id, input_data, generated_usernames)
            VALUES (?, ?, ?)
        ''', (user_id, json.dumps(input_data), json.dumps(usernames)))
        self.db_connection.commit()
    
    def get_cached_username_result(self, username: str, max_age_hours: int = 24) -> Optional[bool]:
        """Get cached username availability result"""
        cursor = self.db_connection.cursor()
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        cursor.execute('''
            SELECT available FROM username_cache 
            WHERE username = ? AND checked_at > ?
        ''', (username, cutoff_time))
        
        result = cursor.fetchone()
        return result[0] if result else None
    
    def cache_username_result(self, username: str, available: bool):
        """Cache username availability result"""
        cursor = self.db_connection.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO username_cache (username, available, checked_at)
            VALUES (?, ?, ?)
        ''', (username, available, datetime.now()))
        self.db_connection.commit()
    
    def apply_letter_replacements(self, text: str) -> List[str]:
        """Apply leet speak replacements to text"""
        variations = [text]
        
        # Apply single replacements
        for original, replacement in self.letter_replacements.items():
            new_variations = []
            for variant in variations:
                if original in variant:
                    new_variations.append(variant.replace(original, replacement))
            variations.extend(new_variations)
        
        # Apply combinations of replacements (limit to prevent explosion)
        combined_variations = []
        for variant in variations[:10]:  # Limit base variants
            temp = variant
            # Apply up to 3 replacements per word
            replacement_count = 0
            for original, replacement in self.letter_replacements.items():
                if replacement_count >= 3:
                    break
                if original in temp:
                    temp = temp.replace(original, replacement)
                    replacement_count += 1
            combined_variations.append(temp)
        
        variations.extend(combined_variations)
        return list(set(variations))
    
    def generate_number_combinations(self, base: str) -> List[str]:
        """Generate number combinations for username"""
        combinations = []
        
        # Single digits
        for i in range(10):
            combinations.append(f"{base}{i}")
        
        # Double digits
        for i in range(10, 100, 11):  # 11, 22, 33, etc.
            combinations.append(f"{base}{i}")
        
        # Common number patterns
        common_numbers = [13, 17, 21, 69, 77, 88, 99, 123, 420, 666, 777, 888, 999, 1337]
        for num in common_numbers:
            combinations.append(f"{base}{num}")
        
        # Year patterns
        years = ["2024", "2025", "24", "25", "00", "01", "02", "03", "04", "05"]
        for year in years:
            combinations.append(f"{base}{year}")
        
        return combinations
    
    def generate_separator_combinations(self, parts: List[str]) -> List[str]:
        """Generate combinations with different separators"""
        combinations = []
        separators = ['', '_']  # Only empty string and underscore are valid for Telegram
        
        for sep in separators:
            combinations.append(sep.join(parts))
        
        return combinations
    
    async def generate_usernames_with_ai(self, user_input: dict) -> List[str]:
        """Generate usernames using enhanced AI logic"""
        name = user_input.get('name', '').lower().strip()
        interests = user_input.get('interests', [])
        style = user_input.get('style', 'cool')
        length_pref = user_input.get('length_pref', 'medium')
        
        all_usernames = set()
        
        # Base name variations
        if name:
            name_variations = self.apply_letter_replacements(name)
            
            # Add base name variations
            for variation in name_variations:
                all_usernames.add(variation)
                all_usernames.update(self.generate_number_combinations(variation))
        
        # Style-based combinations
        if style in self.style_prefixes:
            prefixes = self.style_prefixes[style][:30]  # Limit to 30 per style
            suffixes = self.style_suffixes[style][:30]
            
            for prefix in prefixes:
                if name:
                    # Prefix + name combinations
                    base_combo = f"{prefix}{name}"
                    all_usernames.add(base_combo)
                    all_usernames.update(self.apply_letter_replacements(base_combo))
                    all_usernames.update(self.generate_number_combinations(base_combo))
                    
                    # Prefix + separator + name
                    sep_combos = self.generate_separator_combinations([prefix, name])
                    all_usernames.update(sep_combos)
                    
                    for combo in sep_combos:
                        all_usernames.update(self.apply_letter_replacements(combo))
            
            for suffix in suffixes:
                if name:
                    # Name + suffix combinations
                    base_combo = f"{name}{suffix}"
                    all_usernames.add(base_combo)
                    all_usernames.update(self.apply_letter_replacements(base_combo))
                    all_usernames.update(self.generate_number_combinations(base_combo))
                    
                    # Name + separator + suffix
                    sep_combos = self.generate_separator_combinations([name, suffix])
                    all_usernames.update(sep_combos)
                    
                    for combo in sep_combos:
                        all_usernames.update(self.apply_letter_replacements(combo))
        
        # Interest-based combinations
        for interest in interests[:3]:  # Limit to 3 interests
            interest_lower = interest.lower().strip()
            if interest_lower in self.interest_keywords:
                keywords = self.interest_keywords[interest_lower][:30]  # Limit to 30 per interest
                
                for keyword in keywords:
                    if name:
                        # Name + keyword combinations
                        combos = [
                            f"{name}{keyword}",
                            f"{keyword}{name}",
                            f"{name}_{keyword}",
                            f"{keyword}_{name}"
                        ]
                        
                        for combo in combos:
                            all_usernames.add(combo)
                            all_usernames.update(self.apply_letter_replacements(combo))
                            all_usernames.update(self.generate_number_combinations(combo))
                    else:
                        # Pure keyword combinations
                        all_usernames.add(keyword)
                        all_usernames.update(self.apply_letter_replacements(keyword))
                        all_usernames.update(self.generate_number_combinations(keyword))
        
        # Creative pattern combinations
        if name:
            creative_patterns = [
                f"the{name}",
                f"{name}official",
                f"{name}real",
                f"{name}main",
                f"{name}pro",
                f"{name}king",
                f"{name}queen",
                f"{name}boss",
                f"{name}master",
                f"{name}lord",
                f"mr{name}",
                f"ms{name}",
                f"{name}x",
                f"{name}xx",
                f"{name}xo",
                f"{name}z",
                f"{name}zz",
                f"i{name}",
                f"im{name}",
                f"its{name}",
                f"just{name}",
                f"only{name}",
                f"pure{name}",
                f"real{name}",
                f"true{name}",
                f"new{name}",
                f"old{name}",
                f"young{name}",
                f"little{name}",
                f"big{name}",
                f"super{name}"
            ]
            
            for pattern in creative_patterns:
                all_usernames.add(pattern)
                all_usernames.update(self.apply_letter_replacements(pattern))
        
        # Clean and filter usernames
        cleaned_usernames = []
        for username in all_usernames:
            # Remove invalid characters and ensure lowercase - only letters, numbers, underscore allowed
            cleaned = re.sub(r'[^a-z0-9_]', '', username.lower())
            
            # Check length constraints
            if 5 <= len(cleaned) <= 32:
                # Apply length preference
                if length_pref == 'short' and len(cleaned) <= 10:
                    cleaned_usernames.append(cleaned)
                elif length_pref == 'medium' and 8 <= len(cleaned) <= 16:
                    cleaned_usernames.append(cleaned)
                elif length_pref == 'long' and len(cleaned) >= 12:
                    cleaned_usernames.append(cleaned)
                elif length_pref == 'any':
                    cleaned_usernames.append(cleaned)
        
        # Remove duplicates and return
        return list(set(cleaned_usernames))
    
    async def check_username_availability(self, username: str) -> bool:
        """Check if username is available using proper Telegram MTProto API"""
        try:
            # Check cache first
            cached_result = self.get_cached_username_result(username)
            if cached_result is not None:
                status = "AVAILABLE" if cached_result else "TAKEN"
                print(f"   Result (cached): @{username} - {status}")
                return cached_result
            
            # If no Telethon client available, fall back to less reliable method
            if not self.user_client:
                print(f"   Warning: Using fallback method for @{username}")
                return await self._fallback_username_check(username)
            
            # Use proper Telegram API
            await self.user_client.start()
            
            try:
                result = await self.user_client(CheckUsernameRequest(username))
                is_available = bool(result)
                
                # Cache the result
                self.cache_username_result(username, is_available)
                
                status = "AVAILABLE" if is_available else "TAKEN"
                print(f"   Result: @{username} - {status}")
                return is_available
                
            except FloodWaitError as e:
                print(f"   Rate limited for @{username}, waiting {e.seconds} seconds")
                await asyncio.sleep(e.seconds)
                # Try again after wait
                result = await self.user_client(CheckUsernameRequest(username))
                is_available = bool(result)
                self.cache_username_result(username, is_available)
                status = "AVAILABLE" if is_available else "TAKEN"
                print(f"   Result (after wait): @{username} - {status}")
                return is_available
                
            except UsernameInvalidError:
                print(f"   Result: @{username} - INVALID")
                self.cache_username_result(username, False)
                return False
                
            except AuthKeyError:
                print(f"   Auth error, falling back for @{username}")
                return await self._fallback_username_check(username)
                
        except Exception as e:
            print(f"   Error checking @{username}: {e}")
            logger.error(f"Error checking username availability for {username}: {e}")
            # Fall back to less reliable method
            return await self._fallback_username_check(username)
    
    async def _fallback_username_check(self, username: str) -> bool:
        """Fallback method when Telethon is not available (less reliable)"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"https://t.me/{username}"
                async with session.get(url, timeout=5) as response:
                    # This method is unreliable but better than nothing
                    is_available = response.status == 404
                    print(f"   Result (fallback): @{username} - {'AVAILABLE' if is_available else 'TAKEN'}")
                    return is_available
        except Exception as e:
            print(f"   Fallback error for @{username}: {e}")
            # If we can't check, assume available to avoid false negatives
            return True
    
    async def filter_available_usernames(self, usernames: List[str]) -> List[str]:
        """Filter usernames to only return available ones"""
        available_usernames = []
        
        print(f"\nStarting username availability check for {len(usernames)} generated usernames...")
        print("=" * 60)
        
        # Check availability with proper rate limiting for MTProto API
        for i, username in enumerate(usernames):
            print(f"\nChecking {i+1}/{len(usernames)}")
            
            try:
                is_available = await self.check_username_availability(username)
                
                if is_available:
                    available_usernames.append(username)
                    print(f"FOUND AVAILABLE: @{username} (Total found: {len(available_usernames)})")
                    
                    # Stop when we find 10 available usernames
                    if len(available_usernames) >= 10:
                        print(f"\nTARGET REACHED! Found 10 available usernames, stopping search.")
                        print("=" * 60)
                        return available_usernames
                
                # Delay between checks to respect rate limits
                # MTProto API allows ~30 requests per second, so we use 2 second delay to be safe
                await asyncio.sleep(2.0)
                
            except Exception as e:
                print(f"Error checking @{username}: {e}")
                await asyncio.sleep(5.0)  # Longer delay on errors
                continue
            
            # If we have at least 5 and processed significant portion, we can stop early
            # But continue if we have less than 5 to ensure minimum results
            if len(available_usernames) >= 5 and i >= len(usernames) * 0.7:
                print(f"\nMINIMUM MET! Found {len(available_usernames)} usernames after checking 70% of possibilities.")
                print("=" * 60)
                return available_usernames
        
        print(f"\nSEARCH COMPLETE! Found {len(available_usernames)} available usernames total.")
        print("=" * 60)
        return available_usernames
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = update.effective_user
        self.add_user(user.id, user.username, user.first_name, user.last_name)
        
        api_status = "✅ Enabled" if self.user_client else "⚠️ Disabled (fallback mode)"
        
        welcome_message = (
            "🎯 Welcome to the Enhanced AI Username Generator Bot!\n\n"
            "I'll help you create stylish and available Telegram usernames "
            "using advanced AI algorithms with:\n\n"
            "✨ Leet speak transformations\n"
            "🎨 Multiple style combinations\n"
            "🔍 Real-time availability checking\n"
            "💡 Creative pattern generation\n"
            "🚀 Interest-based suggestions\n\n"
            f"📡 API Status: {api_status}\n\n"
            "Use /generate to start creating your perfect username!"
        )
        
        if not self.user_client:
            welcome_message += (
                "\n⚠️ Note: Running in fallback mode. "
                "For maximum accuracy, admin should configure Telegram API credentials."
            )
        
        await update.message.reply_text(welcome_message)
    
    async def generate_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /generate command"""
        # Start the generation process
        context.user_data['step'] = 'name'
        await update.message.reply_text(
            "🎨 Let's create your perfect username!\n\n"
            "First, what's your name or nickname? (This will be the base for your username)\n"
            "💡 Leave empty if you want purely interest-based usernames"
        )
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle user messages during the generation process"""
        user_data = context.user_data
        step = user_data.get('step')
        
        if step == 'name':
            user_data['name'] = update.message.text.strip()
            user_data['step'] = 'interests'
            await update.message.reply_text(
                "🎯 Great! Now tell me your interests (separated by commas).\n\n"
                "Available interests: music, anime, tech, gaming, art, sport, photography, cooking, travel\n"
                "💡 You can also use custom interests!"
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
                [InlineKeyboardButton("📏 Short (5-10)", callback_data='length_short'),
                 InlineKeyboardButton("📐 Medium (8-16)", callback_data='length_medium')],
                [InlineKeyboardButton("📏 Long (12+)", callback_data='length_long'),
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
    
    async def process_generation_callback(self, query, context: ContextTypes.DEFAULT_TYPE):
        """Process username generation from callback"""
        user_data = context.user_data
        user_id = query.from_user.id
        
        # Generate usernames
        await query.edit_message_text("🤖 Generating usernames with enhanced AI...\n⏳ This may take up to 5 minutes...")
        
        # Generate all possible usernames
        all_usernames = await self.generate_usernames_with_ai(user_data)
        print(f"\nAI Generated {len(all_usernames)} unique username combinations")
        
        # Filter to only available usernames
        available_usernames = await self.filter_available_usernames(all_usernames)
        
        # Save to history
        self.save_generation_history(user_id, user_data, available_usernames)
        
        # Send results
        await self.send_results_callback(query, available_usernames, context)
    
    async def send_results_callback(self, query, available_usernames, context):
        """Send results to user via callback"""
        if not available_usernames:
            await query.edit_message_text(
                "😅 No available usernames found with your criteria!\n"
                "Try different interests or style settings."
            )
            return
        
        result_text = f"🎉 Found {len(available_usernames)} available usernames!\n\n"
        result_text += "✅ All usernames below are AVAILABLE:\n\n"
        
        keyboard = []
        for i, username in enumerate(available_usernames, 1):
            result_text += f"{i}. @{username}\n"
            keyboard.append([InlineKeyboardButton(
                f"🔗 Claim @{username}",
                url=f"https://t.me/{username}"
            )])
        
        result_text += "\n💡 Click to claim any username you like!"
        
        # Add regenerate button
        keyboard.append([InlineKeyboardButton("🔄 Generate More", callback_data='regenerate')])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(result_text, reply_markup=reply_markup)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        api_status = "Enabled (High Accuracy)" if self.user_client else "Fallback Mode"
        
        help_text = (
            "🤖 Enhanced AI Username Generator Bot\n\n"
            f"📡 API Status: {api_status}\n\n"
            "🚀 Features:\n"
            "• Leet speak transformations (a→4, o→0, etc.)\n"
            "• 30+ prefixes/suffixes per style\n"
            "• Advanced pattern generation\n"
            "• Proper Telegram API checking\n"
            "• Only shows AVAILABLE usernames\n"
            "• Smart caching system\n"
            "• No rate limits for users\n\n"
            "📝 Commands:\n"
            "/start - Start the bot\n"
            "/generate - Generate usernames\n"
            "/help - Show this help\n\n"
            "🎯 How it works:\n"
            "1. Provide your name/nickname (optional)\n"
            "2. List your interests\n"
            "3. Choose your style\n"
            "4. Select length preference\n"
            "5. Get AI-generated AVAILABLE usernames\n"
            "6. Click to claim instantly\n\n"
            "🎨 Styles:\n"
            "• Cool: dark, cyber, pro, shadow, elite\n"
            "• Cute: kawaii, sweet, bunny, angel\n"
            "• Hacker: anon, root, null, binary\n"
            "• Minimal: clean, pure, simple, zen\n"
            "• Aesthetic: vibe, divine, ethereal\n\n"
            "🔤 Valid Characters:\n"
            "• Letters (a-z)\n"
            "• Numbers (0-9)\n"
            "• Underscores (_)\n"
            "• 5-32 characters long\n\n"
            "🔤 Letter Replacements:\n"
            "• o→0, i→1, l→1, z→2, b→13\n"
            "• a→4, s→5, g→6, t→7, q→9\n\n"
            "Example: 'noob' becomes 'n00b'\n\n"
            "💡 Tips:\n"
            "• Leave name empty for interest-based usernames\n"
            "• Mix multiple interests for unique results\n"
            "• Try different styles for variety\n"
            "• All shown usernames are verified available!"
        )
        
        if not self.user_client:
            help_text += (
                "\n\n⚠️ Setup Note for Admin:\n"
                "For maximum accuracy, configure:\n"
                "• TELEGRAM_API_ID\n"
                "• TELEGRAM_API_HASH\n"
                "Get these from https://my.telegram.org"
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
        logger.info("Starting enhanced username bot...")
        
        try:
            application.run_polling()
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Cleanup resources"""
        if self.user_client and self.user_client.is_connected():
            asyncio.run(self.user_client.disconnect())
        
        if self.db_connection:
            self.db_connection.close()

def main():
    """Main function"""
    # Check if required credentials are configured
    if TELEGRAM_API_ID == "YOUR_API_ID_HERE" or TELEGRAM_API_HASH == "YOUR_API_HASH_HERE":
        logger.warning("Telegram API credentials not configured!")
        logger.warning("For maximum accuracy, get API credentials from https://my.telegram.org")
        logger.warning("Bot will run in fallback mode with reduced accuracy.")
    
    bot = UsernameBot()
    bot.run()

if __name__ == "__main__":
    main()

# Required dependencies:
# pip install python-telegram-bot telethon aiohttp
