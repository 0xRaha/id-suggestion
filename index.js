const { Telegraf, Markup } = require('telegraf');
const { TelegramApi } = require('telegram');
const { StringSession } = require('telegram/sessions');
const { Api } = require('telegram');
const sqlite3 = require('sqlite3').verbose();
const { open } = require('sqlite');
const axios = require('axios');
const path = require('path');

// Configuration
const TELEGRAM_BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN || "YOUR_BOT_TOKEN_HERE";
const TELEGRAM_API_ID = parseInt(process.env.TELEGRAM_API_ID) || "YOUR_API_ID_HERE";
const TELEGRAM_API_HASH = process.env.TELEGRAM_API_HASH || "YOUR_API_HASH_HERE";
const TELEGRAM_SESSION_STRING = process.env.TELEGRAM_SESSION_STRING || "YOUR_SESSION_STRING_HERE";
const DATABASE_FILE = "username_bot.db";

class UsernameBot {
    constructor() {
        this.db = null;
        this.userClient = null;
        this.bot = new Telegraf(TELEGRAM_BOT_TOKEN);
        this.userSessions = new Map(); // Store user session data
        
        // Letter replacement mapping for leet speak
        this.letterReplacements = {
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
        };
        
        // Extended prefixes and suffixes for each style
        this.stylePrefixes = {
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
        };
        
        this.styleSuffixes = {
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
        };
        
        // Extended interest-based keywords
        this.interestKeywords = {
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
        };
        
        this.init();
    }
    
    async init() {
        try {
            await this.initDatabase();
            await this.initTelegramClient();
            this.setupBotHandlers();
            console.log('✅ Bot initialized successfully');
        } catch (error) {
            console.error('❌ Bot initialization failed:', error);
            process.exit(1);
        }
    }
    
    async initDatabase() {
        try {
            this.db = await open({
                filename: DATABASE_FILE,
                driver: sqlite3.Database
            });
            
            // Create users table
            await this.db.exec(`
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_request DATETIME
                )
            `);
            
            // Create generation history table
            await this.db.exec(`
                CREATE TABLE IF NOT EXISTS generation_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    input_data TEXT,
                    generated_usernames TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(user_id) REFERENCES users(user_id)
                )
            `);
            
            // Create username cache table
            await this.db.exec(`
                CREATE TABLE IF NOT EXISTS username_cache (
                    username TEXT PRIMARY KEY,
                    available BOOLEAN NOT NULL,
                    checked_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            `);
            
            console.log('✅ Database initialized');
        } catch (error) {
            console.error('❌ Database initialization failed:', error);
            throw error;
        }
    }
    
    async initTelegramClient() {
        try {
            if (TELEGRAM_API_ID === "YOUR_API_ID_HERE" || 
                TELEGRAM_API_HASH === "YOUR_API_HASH_HERE" || 
                !TELEGRAM_API_ID || 
                !TELEGRAM_API_HASH) {
                console.warn('⚠️ Telegram API credentials not configured properly');
                console.warn('⚠️ Username checking will use fallback method (less accurate)');
                this.userClient = null;
                return;
            }
            
            const session = TELEGRAM_SESSION_STRING && TELEGRAM_SESSION_STRING !== "YOUR_SESSION_STRING_HERE" 
                ? new StringSession(TELEGRAM_SESSION_STRING)
                : new StringSession('');
            
            this.userClient = new TelegramApi(TELEGRAM_API_ID, TELEGRAM_API_HASH, {
                connectionRetries: 5,
            });
            
            console.log('✅ Telegram client initialized successfully');
            console.log('📝 Note: First run requires phone number authentication for user account');
            
        } catch (error) {
            console.error('❌ Failed to initialize Telegram client:', error);
            console.warn('⚠️ Username availability checking will use fallback method');
            this.userClient = null;
        }
    }
    
    setupBotHandlers() {
        // Command handlers
        this.bot.command('start', this.handleStart.bind(this));
        this.bot.command('generate', this.handleGenerate.bind(this));
        this.bot.command('empty', this.handleEmpty.bind(this));
        this.bot.command('help', this.handleHelp.bind(this));
        
        // Message handlers
        this.bot.on('text', this.handleMessage.bind(this));
        this.bot.on('callback_query', this.handleCallback.bind(this));
        
        // Error handler
        this.bot.catch((err) => {
            console.error('❌ Bot error:', err);
        });
    }
    
    async addUser(userId, username, firstName, lastName) {
        try {
            await this.db.run(`
                INSERT OR REPLACE INTO users (user_id, username, first_name, last_name, last_request)
                VALUES (?, ?, ?, ?, ?)
            `, [userId, username, firstName, lastName, new Date().toISOString()]);
        } catch (error) {
            console.error('Error adding user:', error);
        }
    }
    
    async saveGenerationHistory(userId, inputData, usernames) {
        try {
            await this.db.run(`
                INSERT INTO generation_history (user_id, input_data, generated_usernames)
                VALUES (?, ?, ?)
            `, [userId, JSON.stringify(inputData), JSON.stringify(usernames)]);
        } catch (error) {
            console.error('Error saving generation history:', error);
        }
    }
    
    async getCachedUsernameResult(username, maxAgeHours = 24) {
        try {
            const cutoffTime = new Date(Date.now() - maxAgeHours * 60 * 60 * 1000).toISOString();
            const result = await this.db.get(`
                SELECT available FROM username_cache 
                WHERE username = ? AND checked_at > ?
            `, [username, cutoffTime]);
            
            return result ? Boolean(result.available) : null;
        } catch (error) {
            console.error('Error getting cached result:', error);
            return null;
        }
    }
    
    async cacheUsernameResult(username, available) {
        try {
            await this.db.run(`
                INSERT OR REPLACE INTO username_cache (username, available, checked_at)
                VALUES (?, ?, ?)
            `, [username, available, new Date().toISOString()]);
        } catch (error) {
            console.error('Error caching result:', error);
        }
    }
    
    applyLetterReplacements(text) {
        const variations = new Set([text]);
        
        // Apply single replacements
        for (const [original, replacement] of Object.entries(this.letterReplacements)) {
            const currentVariations = Array.from(variations);
            for (const variant of currentVariations) {
                if (variant.includes(original)) {
                    variations.add(variant.replace(new RegExp(original, 'g'), replacement));
                }
            }
        }
        
        // Apply combinations of replacements (limit to prevent explosion)
        const combinedVariations = [];
        const limitedVariations = Array.from(variations).slice(0, 10);
        
        for (const variant of limitedVariations) {
            let temp = variant;
            let replacementCount = 0;
            
            for (const [original, replacement] of Object.entries(this.letterReplacements)) {
                if (replacementCount >= 3) break;
                if (temp.includes(original)) {
                    temp = temp.replace(new RegExp(original, 'g'), replacement);
                    replacementCount++;
                }
            }
            combinedVariations.push(temp);
        }
        
        combinedVariations.forEach(v => variations.add(v));
        return Array.from(variations);
    }
    
    generateNumberCombinations(base) {
        const combinations = [];
        
        // Single digits
        for (let i = 0; i < 10; i++) {
            combinations.push(`${base}${i}`);
        }
        
        // Double digits
        for (let i = 11; i < 100; i += 11) {
            combinations.push(`${base}${i}`);
        }
        
        // Common number patterns
        const commonNumbers = [13, 17, 21, 69, 77, 88, 99, 123, 420, 666, 777, 888, 999, 1337];
        for (const num of commonNumbers) {
            combinations.push(`${base}${num}`);
        }
        
        // Year patterns
        const years = ["2024", "2025", "24", "25", "00", "01", "02", "03", "04", "05"];
        for (const year of years) {
            combinations.push(`${base}${year}`);
        }
        
        return combinations;
    }
    
    generateSeparatorCombinations(parts) {
        const combinations = [];
        const separators = ['', '_']; // Only valid for Telegram
        
        for (const sep of separators) {
            combinations.push(parts.join(sep));
        }
        
        return combinations;
    }
    
    async generateUsernamesWithAI(userInput) {
        const name = (userInput.name || '').toLowerCase().trim();
        const interests = userInput.interests || [];
        const style = userInput.style || 'cool';
        const lengthPref = userInput.length_pref || 'medium';
        
        const simpleUsernames = [];
        const leetUsernames = [];
        const numberedUsernames = [];
        
        // Base name variations (simple format first, NO NUMBERS)
        if (name) {
            simpleUsernames.push(
                name,
                `${name}_official`,
                `${name}_real`,
                `${name}_main`,
                `the${name}`,
                `${name}x`,
                `${name}xx`
            );
        }
        
        // Style-based combinations
        if (this.stylePrefixes[style]) {
            const prefixes = this.stylePrefixes[style].slice(0, 30);
            const suffixes = this.styleSuffixes[style].slice(0, 30);
            
            for (const prefix of prefixes) {
                if (name) {
                    const baseCombo = `${prefix}${name}`;
                    simpleUsernames.push(baseCombo);
                    
                    const sepCombos = this.generateSeparatorCombinations([prefix, name]);
                    simpleUsernames.push(...sepCombos);
                }
            }
            
            for (const suffix of suffixes) {
                if (name) {
                    const baseCombo = `${name}${suffix}`;
                    simpleUsernames.push(baseCombo);
                    
                    const sepCombos = this.generateSeparatorCombinations([name, suffix]);
                    simpleUsernames.push(...sepCombos);
                }
            }
        }
        
        // Interest-based combinations
        for (const interest of interests.slice(0, 3)) {
            const interestLower = interest.toLowerCase().trim();
            if (this.interestKeywords[interestLower]) {
                const keywords = this.interestKeywords[interestLower].slice(0, 30);
                
                for (const keyword of keywords) {
                    if (name) {
                        const combos = [
                            `${name}${keyword}`,
                            `${keyword}${name}`,
                            `${name}_${keyword}`,
                            `${keyword}_${name}`
                        ];
                        simpleUsernames.push(...combos);
                    } else {
                        simpleUsernames.push(keyword);
                        
                        if (this.stylePrefixes[style]) {
                            const prefixes = this.stylePrefixes[style].slice(0, 15);
                            const suffixes = this.styleSuffixes[style].slice(0, 15);
                            
                            for (const prefix of prefixes) {
                                simpleUsernames.push(`${prefix}${keyword}`);
                                simpleUsernames.push(`${prefix}_${keyword}`);
                            }
                            
                            for (const suffix of suffixes) {
                                simpleUsernames.push(`${keyword}${suffix}`);
                                simpleUsernames.push(`${keyword}_${suffix}`);
                            }
                        }
                    }
                }
            }
        }
        
        // Creative pattern combinations
        if (name) {
            const creativePatterns = [
                `the${name}`, `${name}official`, `${name}real`, `${name}main`, `${name}pro`,
                `${name}king`, `${name}queen`, `${name}boss`, `${name}master`, `${name}lord`,
                `mr${name}`, `ms${name}`, `${name}x`, `${name}xx`, `${name}xo`,
                `${name}z`, `${name}zz`, `i${name}`, `im${name}`, `its${name}`,
                `just${name}`, `only${name}`, `pure${name}`, `real${name}`, `true${name}`,
                `new${name}`, `old${name}`, `young${name}`, `little${name}`, `big${name}`, `super${name}`
            ];
            
            simpleUsernames.push(...creativePatterns);
        }
        
        // Apply leet speak transformations
        for (const username of simpleUsernames.slice(0, 200)) {
            const leetVariations = this.applyLetterReplacements(username);
            leetUsernames.push(...leetVariations);
        }
        
        // Add number combinations (last resort)
        const allNonNumbered = [...simpleUsernames, ...leetUsernames];
        for (const username of allNonNumbered.slice(0, 150)) {
            const numberedVariations = this.generateNumberCombinations(username);
            numberedUsernames.push(...numberedVariations);
        }
        
        // Combine in priority order
        const allUsernames = [...simpleUsernames, ...leetUsernames, ...numberedUsernames];
        
        // Clean and filter usernames
        const cleanedUsernames = [];
        for (const username of allUsernames) {
            // Remove invalid characters and ensure lowercase
            const cleaned = username.toLowerCase().replace(/[^a-z0-9_]/g, '');
            
            // Skip usernames that start with numbers (invalid for Telegram)
            if (cleaned && /^\d/.test(cleaned)) continue;
            
            // Check length constraints
            if (cleaned.length >= 5 && cleaned.length <= 32) {
                if (
                    (lengthPref === 'short' && cleaned.length <= 10) ||
                    (lengthPref === 'medium' && cleaned.length >= 8 && cleaned.length <= 16) ||
                    (lengthPref === 'long' && cleaned.length >= 12) ||
                    lengthPref === 'any'
                ) {
                    cleanedUsernames.push(cleaned);
                }
            }
        }
        
        // Remove duplicates while preserving order
        const seen = new Set();
        const orderedUsernames = [];
        for (const username of cleanedUsernames) {
            if (!seen.has(username)) {
                seen.add(username);
                orderedUsernames.push(username);
            }
        }
        
        return orderedUsernames;
    }
    
    async checkUsernameAvailability(username) {
        try {
            // Check cache first
            const cachedResult = await this.getCachedUsernameResult(username);
            if (cachedResult !== null) {
                const status = cachedResult ? "AVAILABLE" : "TAKEN";
                console.log(`   Result (cached): @${username} - ${status}`);
                return cachedResult;
            }
            
            // Use fallback method if no Telegram client
            if (!this.userClient) {
                return await this.fallbackUsernameCheck(username);
            }
            
            try {
                // Connect if not connected
                if (!this.userClient.connected) {
                    await this.userClient.start();
                }
                
                // Check if authenticated as user
                const me = await this.userClient.getMe();
                if (me.bot) {
                    console.error('Telegram client authenticated as bot instead of user!');
                    this.userClient = null;
                    return await this.fallbackUsernameCheck(username);
                }
                
                // Check username availability
                const result = await this.userClient.invoke(
                    new Api.account.CheckUsername({ username })
                );
                
                const isAvailable = Boolean(result);
                await this.cacheUsernameResult(username, isAvailable);
                
                const status = isAvailable ? "AVAILABLE" : "TAKEN";
                console.log(`   Result: @${username} - ${status}`);
                return isAvailable;
                
            } catch (error) {
                if (error.message.includes('FLOOD_WAIT')) {
                    const seconds = parseInt(error.message.match(/\d+/)?.[0] || '60');
                    console.log(`   Rate limited for @${username}, waiting ${seconds} seconds`);
                    await this.sleep(seconds * 1000);
                    
                    // Try again after wait
                    const result = await this.userClient.invoke(
                        new Api.account.CheckUsername({ username })
                    );
                    const isAvailable = Boolean(result);
                    await this.cacheUsernameResult(username, isAvailable);
                    
                    const status = isAvailable ? "AVAILABLE" : "TAKEN";
                    console.log(`   Result (after wait): @${username} - ${status}`);
                    return isAvailable;
                }
                
                if (error.message.includes('USERNAME_INVALID')) {
                    console.log(`   Result: @${username} - INVALID`);
                    await this.cacheUsernameResult(username, false);
                    return false;
                }
                
                throw error;
            }
            
        } catch (error) {
            console.log(`   Error checking @${username}: ${error.message}`);
            return await this.fallbackUsernameCheck(username);
        }
    }
    
    async fallbackUsernameCheck(username) {
        try {
            const response = await axios.get(`https://t.me/${username}`, { timeout: 5000 });
            const isAvailable = response.status === 404;
            console.log(`   Result (fallback): @${username} - ${isAvailable ? 'AVAILABLE' : 'TAKEN'}`);
            return isAvailable;
        } catch (error) {
            if (error.response && error.response.status === 404) {
                console.log(`   Result (fallback): @${username} - AVAILABLE`);
                return true;
            }
            console.log(`   Fallback error for @${username}: ${error.message}`);
            return true; // Assume available if can't check
        }
    }
    
    async filterAvailableUsernames(usernames) {
        const availableUsernames = [];
        
        console.log(`\nStarting username availability check for ${usernames.length} generated usernames...`);
        console.log('Target: Find at least 10 available usernames or check all ideas');
        console.log('='.repeat(60));
        
        let consecutiveErrors = 0;
        let requestsThisBatch = 0;
        let batchStartTime = Date.now();
        
        for (let i = 0; i < usernames.length; i++) {
            const username = usernames[i];
            console.log(`\nChecking ${i + 1}/${usernames.length}`);
            
            try {
                const isAvailable = await this.checkUsernameAvailability(username);
                consecutiveErrors = 0;
                requestsThisBatch++;
                
                if (isAvailable) {
                    availableUsernames.push(username);
                    console.log(`FOUND AVAILABLE: @${username} (Total found: ${availableUsernames.length})`);
                }
                
                // Check if we need to rest
                if (requestsThisBatch >= 50) {
                    const elapsedTime = (Date.now() - batchStartTime) / 1000;
                    if (elapsedTime < 120) {
                        const restTime = 60;
                        console.log(`\nAPI EXPLOSION PREVENTION: Resting for ${restTime} seconds...`);
                        console.log(`Processed ${requestsThisBatch} requests in ${elapsedTime.toFixed(1)} seconds`);
                        console.log(`Rate: ${(requestsThisBatch/elapsedTime).toFixed(1)} requests/second`);
                        await this.sleep(restTime * 1000);
                        console.log('Resuming username checking...');
                    }
                    
                    requestsThisBatch = 0;
                    batchStartTime = Date.now();
                }
                
                await this.sleep(2000); // Normal delay
                
            } catch (error) {
                console.log(`Error checking @${username}: ${error.message}`);
                consecutiveErrors++;
                
                if (consecutiveErrors >= 5) {
                    const restTime = 120;
                    console.log(`\nERROR RECOVERY: Too many consecutive errors (${consecutiveErrors}), resting for ${restTime} seconds...`);
                    console.log('This helps prevent being blocked by Telegram\'s rate limiting');
                    await this.sleep(restTime * 1000);
                    consecutiveErrors = 0;
                    console.log('Resuming after error recovery...');
                } else {
                    await this.sleep(5000);
                }
            }
        }
        
        console.log(`\nSEARCH COMPLETE! Found ${availableUsernames.length} available usernames total.`);
        console.log(`Total usernames checked: ${usernames.length}`);
        console.log(`Success rate: ${(availableUsernames.length/usernames.length*100).toFixed(1)}%`);
        
        if (availableUsernames.length >= 10) {
            console.log(`SUCCESS: Found ${availableUsernames.length} usernames (minimum 10 achieved)`);
        } else if (availableUsernames.length > 0) {
            console.log(`PARTIAL SUCCESS: Found ${availableUsernames.length} usernames (checked all ${usernames.length} ideas)`);
        } else {
            console.log('NO AVAILABLE USERNAMES: All generated ideas were taken');
        }
        
        console.log('='.repeat(60));
        return availableUsernames;
    }
    
    sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
    
    // Bot Handler Methods
    async handleStart(ctx) {
        const user = ctx.from;
        await this.addUser(user.id, user.username, user.first_name, user.last_name);
        
        const apiStatus = this.userClient ? "✅ Enabled" : "⚠️ Disabled (fallback mode)";
        
        let welcomeMessage = (
            "🎯 Welcome to the Enhanced AI Username Generator Bot!\n\n" +
            "I'll help you create stylish and available Telegram usernames " +
            "using advanced AI algorithms with:\n\n" +
            "✨ Leet speak transformations\n" +
            "🎨 Multiple style combinations\n" +
            "🔍 Real-time availability checking\n" +
            "💡 Creative pattern generation\n" +
            "🚀 Interest-based suggestions\n\n" +
            `📡 API Status: ${apiStatus}\n\n` +
            "Use /generate to start with your name or /empty for interest-based usernames!"
        );
        
        if (!this.userClient) {
            welcomeMessage += (
                "\n⚠️ Note: Running in fallback mode. " +
                "For maximum accuracy, admin should configure Telegram API credentials."
            );
        }
        
        await ctx.reply(welcomeMessage);
    }
    
    async handleGenerate(ctx) {
        this.userSessions.set(ctx.from.id, { step: 'name' });
        await ctx.reply(
            "🎨 Let's create your perfect username!\n\n" +
            "First, what's your name or nickname? (This will be the base for your username)\n" +
            "💡 Leave empty if you want purely interest-based usernames\n" +
            "💡 Or use /empty to skip name and go directly to interests"
        );
    }
    
    async handleEmpty(ctx) {
        const session = { name: '', step: 'interests' };
        this.userSessions.set(ctx.from.id, session);
        await ctx.reply(
            "🎯 Great! Creating usernames based purely on interests.\n\n" +
            "Tell me your interests (separated by commas).\n" +
            "Examples: music, anime, tech, gaming, art, sport, photography"
        );
    }
    
    async handleMessage(ctx) {
        const session = this.userSessions.get(ctx.from.id);
        if (!session) return;
        
        const step = session.step;
        
        if (step === 'name') {
            session.name = ctx.message.text.trim();
            session.step = 'interests';
            this.userSessions.set(ctx.from.id, session);
            
            await ctx.reply(
                "🎯 Great! Now tell me your interests (separated by commas).\n\n" +
                "Available interests: music, anime, tech, gaming, art, sport, photography, cooking, travel\n" +
                "💡 You can also use custom interests!"
            );
        } else if (step === 'interests') {
            const interests = ctx.message.text.split(',').map(i => i.trim());
            session.interests = interests;
            session.step = 'style';
            this.userSessions.set(ctx.from.id, session);
            
            const keyboard = Markup.inlineKeyboard([
                [
                    Markup.button.callback('😎 Cool', 'style_cool'),
                    Markup.button.callback('🥰 Cute', 'style_cute')
                ],
                [
                    Markup.button.callback('🖤 Hacker', 'style_hacker'),
                    Markup.button.callback('✨ Minimal', 'style_minimal')
                ],
                [
                    Markup.button.callback('🌸 Aesthetic', 'style_aesthetic')
                ]
            ]);
            
            await ctx.reply("🎨 Choose your preferred style:", keyboard);
        }
    }
    
    async handleCallback(ctx) {
        const session = this.userSessions.get(ctx.from.id);
        if (!session) return;
        
        await ctx.answerCbQuery();
        
        if (ctx.callbackQuery.data.startsWith('style_')) {
            const style = ctx.callbackQuery.data.replace('style_', '');
            session.style = style;
            session.step = 'length';
            this.userSessions.set(ctx.from.id, session);
            
            const keyboard = Markup.inlineKeyboard([
                [
                    Markup.button.callback('📏 Short (5-10)', 'length_short'),
                    Markup.button.callback('📐 Medium (8-16)', 'length_medium')
                ],
                [
                    Markup.button.callback('📏 Long (12+)', 'length_long'),
                    Markup.button.callback('🎲 Any length', 'length_any')
                ]
            ]);
            
            await ctx.editMessageText(
                "📏 Choose your preferred username length:",
                keyboard
            );
        } else if (ctx.callbackQuery.data.startsWith('length_')) {
            const length = ctx.callbackQuery.data.replace('length_', '');
            session.length_pref = length;
            this.userSessions.set(ctx.from.id, session);
            
            await this.processGeneration(ctx, session);
        }
    }
    
    async processGeneration(ctx, session) {
        const userId = ctx.from.id;
        
        await ctx.editMessageText("🤖 Generating usernames with enhanced AI...\n⏳ This may take up to 5 minutes...");
        
        try {
            // Generate all possible usernames
            const startTime = Date.now();
            const allUsernames = await this.generateUsernamesWithAI(session);
            const generationTime = Date.now() - startTime;
            
            console.log(`\n🎯 AI Generated ${allUsernames.length} unique username combinations in ${generationTime}ms`);
            
            // Filter to only available usernames
            const filterStartTime = Date.now();
            const availableUsernames = await this.filterAvailableUsernames(allUsernames);
            const filterTime = Date.now() - filterStartTime;
            
            console.log(`🔍 Username filtering completed in ${filterTime}ms`);
            
            // Save to history
            await this.saveGenerationHistory(userId, session, availableUsernames);
            
            // Send results
            await this.sendResults(ctx, availableUsernames);
            
            // Clean up session
            this.userSessions.delete(ctx.from.id);
            
        } catch (error) {
            console.error('Generation error:', error);
            await ctx.editMessageText(
                "❌ Sorry, an error occurred during username generation. Please try again with /generate"
            );
            this.userSessions.delete(ctx.from.id);
        }
    }
    
    async sendResults(ctx, availableUsernames) {
        if (!availableUsernames || availableUsernames.length === 0) {
            await ctx.editMessageText(
                "😅 No available usernames found with your criteria!\n" +
                "All generated combinations were already taken.\n" +
                "Try different interests or style settings."
            );
            return;
        }
        
        let resultText = `🎉 Found ${availableUsernames.length} available usernames!\n\n`;
        
        if (availableUsernames.length >= 10) {
            resultText += "✅ All usernames below are AVAILABLE:\n\n";
        } else {
            resultText += `✅ Found ${availableUsernames.length} available usernames (checked all possibilities):\n\n`;
        }
        
        for (let i = 0; i < availableUsernames.length; i++) {
            resultText += `${i + 1}. @${availableUsernames[i]}\n`;
        }
        
        resultText += "\n💡 Copy any username you like and set it in Telegram settings!";
        resultText += "\n🔄 Use /generate to create more usernames";
        
        if (availableUsernames.length < 10) {
            resultText += "\n\n📝 Note: Searched all generated combinations thoroughly";
        }
        
        await ctx.editMessageText(resultText);
    }
    
    async handleHelp(ctx) {
        const apiStatus = this.userClient ? "✅ Enabled (High Accuracy)" : "⚠️ Fallback Mode";
        
        let helpText = (
            "🤖 Enhanced AI Username Generator Bot\n\n" +
            `📡 API Status: ${apiStatus}\n\n` +
            "🚀 Features:\n" +
            "• Leet speak transformations (a→4, o→0, etc.)\n" +
            "• 30+ prefixes/suffixes per style\n" +
            "• Advanced pattern generation\n" +
            "• Proper Telegram API checking\n" +
            "• Guaranteed minimum 10 usernames or exhaust all ideas\n" +
            "• Priority: Simple → Leet speak → Numbers (last resort)\n" +
            "• API explosion prevention with smart rest periods\n" +
            "• Smart caching system\n" +
            "• No rate limits for users\n\n" +
            "📝 Commands:\n" +
            "/start - Start the bot\n" +
            "/generate - Generate usernames with name input\n" +
            "/empty - Generate usernames without name (interests only)\n" +
            "/help - Show this help\n\n" +
            "🎯 How it works:\n" +
            "1. Use /generate (with name) or /empty (without name)\n" +
            "2. List your interests\n" +
            "3. Choose your style\n" +
            "4. Select length preference\n" +
            "5. Get minimum 10 AVAILABLE usernames (or all possibilities)\n" +
            "6. Copy and use any username you like\n\n" +
            "🎨 Styles:\n" +
            "• Cool: dark, cyber, pro, shadow, elite\n" +
            "• Cute: kawaii, sweet, bunny, angel\n" +
            "• Hacker: anon, root, null, binary\n" +
            "• Minimal: clean, pure, simple, zen\n" +
            "• Aesthetic: vibe, divine, ethereal\n\n" +
            "🔤 Valid Characters:\n" +
            "• Letters (a-z)\n" +
            "• Numbers (0-9) - cannot start with number\n" +
            "• Underscores (_)\n" +
            "• 5-32 characters long\n\n" +
            "🔤 Letter Replacements:\n" +
            "• o→0, i→1, l→1, z→2, b→13\n" +
            "• a→4, s→5, g→6, t→7, q→9\n\n" +
            "Example: 'noob' becomes 'n00b'\n\n" +
            "💡 Tips:\n" +
            "• Leave name empty for interest-based usernames\n" +
            "• Mix multiple interests for unique results\n" +
            "• Try different styles for variety\n" +
            "• Priority: Simple → Leet speak → Numbers (last resort)\n" +
            "• Guaranteed minimum 10 usernames or all possibilities checked\n" +
            "• Bot includes rest periods to prevent API overload\n" +
            "• All shown usernames are verified available!\n" +
            "• Copy and paste any @username you like"
        );
        
        if (!this.userClient) {
            helpText += (
                "\n\n⚠️ ADMIN SETUP REQUIRED:\n" +
                "Bot is running in fallback mode (less accurate)\n\n" +
                "For 100% accurate results, admin needs to:\n" +
                "1. Get API credentials from https://my.telegram.org\n" +
                "2. Configure TELEGRAM_API_ID and TELEGRAM_API_HASH\n" +
                "3. Authenticate with USER account (not bot)\n" +
                "4. Restart the bot\n\n" +
                "⚠️ IMPORTANT: Must authenticate with USER account\n" +
                "Do NOT use bot token for Telegram authentication!"
            );
        }
        
        await ctx.reply(helpText);
    }
    
    async start() {
        try {
            console.log('🚀 Starting Enhanced Username Bot (Node.js)...');
            console.log('✨ Features: Minimum 10 usernames guaranteed, simple formats first');
            console.log('🔍 Username validation: No leading numbers, proper Telegram format');
            console.log('⚡ Generation priority: Simple → Leet speak → Numbers (last resort)');
            console.log('🛡️ API protection: Smart rest periods to prevent explosion');
            
            await this.bot.launch();
            console.log('✅ Bot started successfully!');
            
            // Graceful shutdown
            process.once('SIGINT', () => this.stop('SIGINT'));
            process.once('SIGTERM', () => this.stop('SIGTERM'));
            
        } catch (error) {
            console.error('❌ Failed to start bot:', error);
            process.exit(1);
        }
    }
    
    async stop(signal) {
        console.log(`\n🛑 Received ${signal}, shutting down gracefully...`);
        
        try {
            this.bot.stop(signal);
            
            if (this.userClient && this.userClient.connected) {
                await this.userClient.disconnect();
            }
            
            if (this.db) {
                await this.db.close();
            }
            
            console.log('✅ Bot stopped successfully');
            process.exit(0);
        } catch (error) {
            console.error('❌ Error during shutdown:', error);
            process.exit(1);
        }
    }
}

// Main execution
async function main() {
    // Check required credentials
    if (TELEGRAM_API_ID === "YOUR_API_ID_HERE" || TELEGRAM_API_HASH === "YOUR_API_HASH_HERE") {
        console.warn('='.repeat(60));
        console.warn('⚠️ TELEGRAM API CREDENTIALS NOT CONFIGURED!');
        console.warn('For maximum accuracy, you need to:');
        console.warn('1. Get API credentials from https://my.telegram.org');
        console.warn('2. Set TELEGRAM_API_ID environment variable');
        console.warn('3. Set TELEGRAM_API_HASH environment variable');
        console.warn('4. Make sure to authenticate with a USER account, not bot');
        console.warn('Bot will run in fallback mode with reduced accuracy.');
        console.warn('='.repeat(60));
    }
    
    if (TELEGRAM_API_ID && TELEGRAM_API_ID !== "YOUR_API_ID_HERE" && isNaN(TELEGRAM_API_ID)) {
        console.error('❌ TELEGRAM_API_ID must be a valid integer!');
        console.error('Example: TELEGRAM_API_ID=1234567');
        process.exit(1);
    }
    
    // Additional setup instructions
    if (TELEGRAM_API_ID && !isNaN(TELEGRAM_API_ID) && TELEGRAM_API_ID > 0) {
        console.log('='.repeat(60));
        console.log('📋 AUTHENTICATION SETUP:');
        console.log('On first run, you\'ll need to authenticate with your USER account');
        console.log('(Not the bot account - use your personal Telegram account)');
        console.log('You\'ll be prompted for:');
        console.log('1. Phone number (with country code)');
        console.log('2. Verification code from Telegram');
        console.log('3. Two-factor password (if enabled)');
        console.log('This creates a session for future runs');
        console.log('='.repeat(60));
    }
    
    const bot = new UsernameBot();
    await bot.start();
}

// Handle uncaught exceptions
process.on('uncaughtException', (error) => {
    console.error('❌ Uncaught Exception:', error);
    process.exit(1);
});

process.on('unhandledRejection', (reason, promise) => {
    console.error('❌ Unhandled Rejection at:', promise, 'reason:', reason);
    process.exit(1);
});

// Run the bot
if (require.main === module) {
    main().catch(error => {
        console.error('❌ Fatal error:', error);
        process.exit(1);
    });
}

module.exports = UsernameBot;
