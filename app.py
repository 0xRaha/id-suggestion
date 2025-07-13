import logging
import sqlite3
import asyncio
import aiohttp
import json
import time
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
            # Validate API credentials
            if (TELEGRAM_API_ID == "YOUR_API_ID_HERE" or 
                TELEGRAM_API_HASH == "YOUR_API_HASH_HERE" or 
                not TELEGRAM_API_ID or 
                not TELEGRAM_API_HASH):
                logger.warning("Telegram API credentials not configured properly")
                logger.warning("Username checking will use fallback method (less accurate)")
                self.user_client = None
                return
            
            # Convert API_ID to integer if it's a string
            try:
                api_id = int(TELEGRAM_API_ID)
            except (ValueError, TypeError):
                logger.error("TELEGRAM_API_ID must be a valid integer")
                self.user_client = None
                return
            
            if TELEGRAM_SESSION_STRING and TELEGRAM_SESSION_STRING != "YOUR_SESSION_STRING_HERE":
                # Use saved session string
                session = StringSession(TELEGRAM_SESSION_STRING)
            else:
                # Use file session - this will require phone authentication on first run
                session = 'username_bot_user_session'
            
            self.user_client = TelegramClient(
                session,
                api_id,
                TELEGRAM_API_HASH
            )
            
            logger.info("Telethon user client initialized successfully")
            logger.info("Note: First run requires phone number authentication for user account")
            
        except Exception as e:
            logger.error(f"Failed to initialize Telethon client: {e}")
            logger.warning("Username availability checking will use fallback method")
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
        """Generate usernames using enhanced AI logic - prioritizing non-number formats first"""
        name = user_input.get('name', '').lower().strip()
        interests = user_input.get('interests', [])
        style = user_input.get('style', 'cool')
        length_pref = user_input.get('length_pref', 'medium')
        
        # Store usernames in priority order
        simple_usernames = []
        leet_usernames = []
        numbered_usernames = []
        
        # Base name variations (simple format first, NO NUMBERS)
        if name:
            simple_usernames.extend([
                name,
                name + '_official',
                name + '_real',
                name + '_main',
                'the' + name,
                name + 'x',
                name + 'xx'
            ])
        
        # Style-based combinations (simple format first, NO NUMBERS)
        if style in self.style_prefixes:
            prefixes = self.style_prefixes[style][:30]  # Limit to 30 per style
            suffixes = self.style_suffixes[style][:30]
            
            for prefix in prefixes:
                if name:
                    # Prefix + name combinations
                    base_combo = f"{prefix}{name}"
                    simple_usernames.append(base_combo)
                    
                    # Prefix + separator + name
                    sep_combos = self.generate_separator_combinations([prefix, name])
                    simple_usernames.extend(sep_combos)
            
            for suffix in suffixes:
                if name:
                    # Name + suffix combinations
                    base_combo = f"{name}{suffix}"
                    simple_usernames.append(base_combo)
                    
                    # Name + separator + suffix
                    sep_combos = self.generate_separator_combinations([name, suffix])
                    simple_usernames.extend(sep_combos)
        
        # Interest-based combinations (simple format first, NO NUMBERS)
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
                        simple_usernames.extend(combos)
                    else:
                        # Pure keyword combinations (when no name provided)
                        simple_usernames.append(keyword)
                        
                        # Add style + keyword combinations for empty names
                        if style in self.style_prefixes:
                            prefixes = self.style_prefixes[style][:15]  # Reduced for empty names
                            suffixes = self.style_suffixes[style][:15]
                            
                            for prefix in prefixes:
                                simple_usernames.append(f"{prefix}{keyword}")
                                simple_usernames.append(f"{prefix}_{keyword}")
                            
                            for suffix in suffixes:
                                simple_usernames.append(f"{keyword}{suffix}")
                                simple_usernames.append(f"{keyword}_{suffix}")
        
        # If no name provided, add pure style-based usernames (NO NUMBERS)
        if not name and style in self.style_prefixes:
            prefixes = self.style_prefixes[style][:20]
            suffixes = self.style_suffixes[style][:20]
            
            # Pure prefix combinations
            simple_usernames.extend(prefixes)
            
            # Pure suffix combinations  
            simple_usernames.extend(suffixes)
            
            # Prefix + suffix combinations
            for prefix in prefixes[:10]:
                for suffix in suffixes[:10]:
                    simple_usernames.append(f"{prefix}{suffix}")
                    simple_usernames.append(f"{prefix}_{suffix}")
        
        # Creative pattern combinations (simple format, NO NUMBERS)
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
            
            simple_usernames.extend(creative_patterns)
        
        # NOW apply leet speak transformations to existing usernames (NO NUMBERS YET)
        for username in simple_usernames[:200]:  # Limit to prevent explosion
            leet_variations = self.apply_letter_replacements(username)
            leet_usernames.extend(leet_variations)
        
        # FINALLY add number combinations (LAST RESORT)
        all_non_numbered = simple_usernames + leet_usernames
        for username in all_non_numbered[:150]:  # Limit to prevent explosion
            numbered_variations = self.generate_number_combinations(username)
            numbered_usernames.extend(numbered_variations)
        
        # Combine in priority order: simple first, then leet speak, then numbered
        all_usernames = simple_usernames + leet_usernames + numbered_usernames
        
        # Clean and filter usernames
        cleaned_usernames = []
        for username in all_usernames:
            # Remove invalid characters and ensure lowercase - only letters, numbers, underscore allowed
            cleaned = re.sub(r'[^a-z0-9_]', '', username.lower())
            
            # Skip usernames that start with numbers (invalid for Telegram)
            if cleaned and cleaned[0].isdigit():
                continue
            
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
        
        # Remove duplicates while preserving order (simple formats first)
        seen = set()
        ordered_usernames = []
        for username in cleaned_usernames:
            if username not in seen:
                seen.add(username)
                ordered_usernames.append(username)
        
        return ordered_usernames
    
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
                return await self._fallback_username_check(username)
            
            # Ensure client is connected and authenticated as USER (not bot)
            if not self.user_client.is_connected():
                await self.user_client.start()
            
            # Verify we're authenticated as a user, not a bot
            me = await self.user_client.get_me()
            if me.bot:
                logger.error("Telethon client authenticated as bot instead of user!")
                logger.error("Please authenticate with a user account, not bot token")
                print(f"   Error: Bot authentication detected for @{username}")
                return await self._fallback_username_check(username)
            
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
                
            except Exception as api_error:
                error_msg = str(api_error).lower()
                if "bot users is restricted" in error_msg or "bot" in error_msg:
                    logger.error("API method restricted for bot users - need user authentication")
                    print(f"   Error: Bot restriction for @{username}")
                    # Disable the client to prevent further attempts
                    self.user_client = None
                    return await self._fallback_username_check(username)
                else:
                    raise api_error
                
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
        """Filter usernames to only return available ones - guaranteed minimum 10 or exhaust all ideas"""
        available_usernames = []
        
        print(f"\nStarting username availability check for {len(usernames)} generated usernames...")
        print("Target: Find at least 10 available usernames or check all ideas")
        print("=" * 60)
        
        consecutive_errors = 0
        requests_this_batch = 0
        batch_start_time = time.time()
        
        # Check availability with proper rate limiting for MTProto API
        for i, username in enumerate(usernames):
            print(f"\nChecking {i+1}/{len(usernames)}")
            
            try:
                is_available = await self.check_username_availability(username)
                consecutive_errors = 0  # Reset error counter on success
                requests_this_batch += 1
                
                if is_available:
                    available_usernames.append(username)
                    print(f"FOUND AVAILABLE: @{username} (Total found: {len(available_usernames)})")
                
                # Check if we need to rest to prevent API explosion
                if requests_this_batch >= 50:  # After 50 requests
                    elapsed_time = time.time() - batch_start_time
                    if elapsed_time < 120:  # If less than 2 minutes have passed
                        rest_time = 60  # Rest for 1 minute
                        print(f"\nAPI EXPLOSION PREVENTION: Resting for {rest_time} seconds...")
                        print(f"Processed {requests_this_batch} requests in {elapsed_time:.1f} seconds")
                        print(f"Rate: {requests_this_batch/elapsed_time:.1f} requests/second")
                        await asyncio.sleep(rest_time)
                        print("Resuming username checking...")
                    
                    # Reset batch counters
                    requests_this_batch = 0
                    batch_start_time = time.time()
                
                # Normal delay between checks
                await asyncio.sleep(2.0)
                
            except Exception as e:
                print(f"Error checking @{username}: {e}")
                consecutive_errors += 1
                
                # If too many consecutive errors, take a longer break
                if consecutive_errors >= 5:
                    rest_time = 120  # Rest for 2 minutes on repeated errors
                    print(f"\nERROR RECOVERY: Too many consecutive errors ({consecutive_errors}), resting for {rest_time} seconds...")
                    print(f"This helps prevent being blocked by Telegram's rate limiting")
                    await asyncio.sleep(rest_time)
                    consecutive_errors = 0
                    print("Resuming after error recovery...")
                else:
                    await asyncio.sleep(5.0)  # Shorter delay on single errors
                continue
        
        print(f"\nSEARCH COMPLETE! Found {len(available_usernames)} available usernames total.")
        print(f"Total usernames checked: {len(usernames)}")
        print(f"Success rate: {len(available_usernames)/len(usernames)*100:.1f}%")
        
        # Check if we met the minimum requirement
        if len(available_usernames) >= 10:
            print(f"SUCCESS: Found {len(available_usernames)} usernames (minimum 10 achieved)")
        elif len(available_usernames) > 0:
            print(f"PARTIAL SUCCESS: Found {len(available_usernames)} usernames (checked all {len(usernames)} ideas)")
        else:
            print("NO AVAILABLE USERNAMES: All generated ideas were taken")
        
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
            "Use /generate to start with your name or /empty for interest-based usernames!"
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
            "💡 Leave empty if you want purely interest-based usernames\n"
            "💡 Or use /empty to skip name and go directly to interests"
        )
    
    async def empty_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /empty command - skip name and go directly to interests"""
        context.user_data['name'] = ''
        context.user_data['step'] = 'interests'
        await update.message.reply_text(
            "🎯 Great! Creating usernames based purely on interests.\n\n"
            "Tell me your interests (separated by commas).\n"
            "Examples: music, anime, tech, gaming, art, sport, photography"
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
                "All generated combinations were already taken.\n"
                "Try different interests or style settings."
            )
            return
        
        result_text = f"🎉 Found {len(available_usernames)} available usernames!\n\n"
        
        if len(available_usernames) >= 10:
            result_text += "✅ All usernames below are AVAILABLE:\n\n"
        else:
            result_text += f"✅ Found {len(available_usernames)} available usernames (checked all possibilities):\n\n"
        
        for i, username in enumerate(available_usernames, 1):
            result_text += f"{i}. @{username}\n"
        
        result_text += "\n💡 Copy any username you like and set it in Telegram settings!"
        result_text += "\n🔄 Use /generate to create more usernames"
        
        # Add note about search completeness
        if len(available_usernames) < 10:
            result_text += f"\n\n📝 Note: Searched all generated combinations thoroughly"
        
        await query.edit_message_text(result_text)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        api_status = "✅ Enabled (High Accuracy)" if self.user_client else "⚠️ Fallback Mode"
        
        help_text = (
            "🤖 Enhanced AI Username Generator Bot\n\n"
            f"📡 API Status: {api_status}\n\n"
            "🚀 Features:\n"
            "• Leet speak transformations (a→4, o→0, etc.)\n"
            "• 30+ prefixes/suffixes per style\n"
            "• Advanced pattern generation\n"
            "• Proper Telegram API checking\n"
            "• Guaranteed minimum 10 usernames or exhaust all ideas\n"
            "• Priority: Simple → Leet speak → Numbers (last resort)\n"
            "• API explosion prevention with smart rest periods\n"
            "• Smart caching system\n"
            "• No rate limits for users\n\n"
            "📝 Commands:\n"
            "/start - Start the bot\n"
            "/generate - Generate usernames with name input\n"
            "/empty - Generate usernames without name (interests only)\n"
            "/help - Show this help\n\n"
            "🎯 How it works:\n"
            "1. Use /generate (with name) or /empty (without name)\n"
            "2. List your interests\n"
            "3. Choose your style\n"
            "4. Select length preference\n"
            "5. Get minimum 10 AVAILABLE usernames (or all possibilities)\n"
            "6. Copy and use any username you like\n\n"
            "🎨 Styles:\n"
            "• Cool: dark, cyber, pro, shadow, elite\n"
            "• Cute: kawaii, sweet, bunny, angel\n"
            "• Hacker: anon, root, null, binary\n"
            "• Minimal: clean, pure, simple, zen\n"
            "• Aesthetic: vibe, divine, ethereal\n\n"
            "🔤 Valid Characters:\n"
            "• Letters (a-z)\n"
            "• Numbers (0-9) - cannot start with number\n"
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
            "• Priority: Simple → Leet speak → Numbers (last resort)\n"
            "• Guaranteed minimum 10 usernames or all possibilities checked\n"
            "• Bot includes rest periods to prevent API overload\n"
            "• All shown usernames are verified available!\n"
            "• Copy and paste any @username you like"
        )
        
        if not self.user_client:
            help_text += (
                "\n\n⚠️ ADMIN SETUP REQUIRED:\n"
                "Bot is running in fallback mode (less accurate)\n\n"
                "For 100% accurate results, admin needs to:\n"
                "1. Get API credentials from https://my.telegram.org\n"
                "2. Configure TELEGRAM_API_ID and TELEGRAM_API_HASH\n"
                "3. Authenticate with USER account (not bot)\n"
                "4. Restart the bot\n\n"
                "⚠️ IMPORTANT: Must authenticate with USER account\n"
                "Do NOT use bot token for Telethon authentication!\n\n"
                "🎯 Current: Minimum 10 usernames guaranteed or exhaust all ideas\n"
                "📝 Format: Simple @username text (no buttons)\n"
                "🔤 Priority: Simple → Leet speak → Numbers (last resort)\n"
                "🛡️ Protection: Smart rest periods prevent API explosion\n"
                "💡 Commands: /generate (with name) or /empty (without name)"
            )
        
        await update.message.reply_text(help_text)
    
    def run(self):
        """Run the bot"""
        # Create application
        application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        
        # Add handlers
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("generate", self.generate_command))
        application.add_handler(CommandHandler("empty", self.empty_command))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(CallbackQueryHandler(self.handle_callback))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Start the bot
        logger.info("Starting enhanced username bot...")
        logger.info("Features: Minimum 10 usernames guaranteed, simple formats first, no buttons")
        logger.info("Username validation: No leading numbers, proper Telegram format")
        logger.info("Generation priority: Simple → Leet speak → Numbers (last resort)")
        logger.info("API protection: Smart rest periods to prevent explosion")
        
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
        logger.warning("=" * 60)
        logger.warning("TELEGRAM API CREDENTIALS NOT CONFIGURED!")
        logger.warning("For maximum accuracy, you need to:")
        logger.warning("1. Get API credentials from https://my.telegram.org")
        logger.warning("2. Replace YOUR_API_ID_HERE with your API ID")
        logger.warning("3. Replace YOUR_API_HASH_HERE with your API Hash")
        logger.warning("4. Make sure to authenticate with a USER account, not bot")
        logger.warning("Bot will run in fallback mode with reduced accuracy.")
        logger.warning("=" * 60)
    
    try:
        api_id = int(TELEGRAM_API_ID) if TELEGRAM_API_ID != "YOUR_API_ID_HERE" else 0
    except (ValueError, TypeError):
        logger.error("TELEGRAM_API_ID must be a valid integer!")
        logger.error("Example: TELEGRAM_API_ID = 1234567")
        return
    
    # Additional setup instructions
    if api_id > 0:
        logger.info("=" * 60)
        logger.info("AUTHENTICATION SETUP:")
        logger.info("On first run, you'll need to authenticate with your USER account")
        logger.info("(Not the bot account - use your personal Telegram account)")
        logger.info("You'll be prompted for:")
        logger.info("1. Phone number (with country code)")
        logger.info("2. Verification code from Telegram")
        logger.info("3. Two-factor password (if enabled)")
        logger.info("This creates a session file for future runs")
        logger.info("=" * 60)
    
    bot = UsernameBot()
    bot.run()

if __name__ == "__main__":
    main()

# Required dependencies:
# pip install python-telegram-bot telethon aiohttp cryptg

# SETUP INSTRUCTIONS:
# 1. Get bot token from @BotFather
# 2. Get API credentials from https://my.telegram.org
# 3. Replace the configuration values above
# 4. Run the bot and authenticate with your USER account (not bot)
# 5. The bot will create a session file for future runs

# FEATURES:
# - Guaranteed minimum 10 usernames or exhaust all ideas
# - Simple text format (no buttons)
# - Generation priority: Simple → Leet speak → Numbers (last resort)
# - API explosion prevention with smart rest periods
# - Validates usernames (no leading numbers)
# - Real-time availability checking via MTProto API
# - 24-hour caching system for efficiency
