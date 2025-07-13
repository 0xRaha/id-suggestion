# Enhanced Telegram Username Generator Bot

A powerful AI-driven Telegram bot that generates creative, available usernames using advanced algorithms and real-time availability checking through Telegram's official MTProto API.

## 🚀 Features

### Core Functionality
- **AI-Powered Generation**: Advanced algorithms create unique username combinations
- **Real-Time Availability**: Uses official Telegram MTProto API for 100% accurate checking
- **Leet Speak Transformations**: Converts letters to numbers (a→4, o→0, etc.)
- **Style-Based Generation**: Multiple aesthetic styles (Cool, Cute, Hacker, Minimal, Aesthetic)
- **Interest Integration**: Generates usernames based on user interests
- **Smart Caching**: 24-hour cache system to reduce API calls and improve speed

### Advanced Features
- **Rate Limit Handling**: Automatic retry with exponential backoff
- **Fallback System**: Works even without API credentials (reduced accuracy)
- **Smart Stopping**: Finds 10 available usernames or minimum 5 before stopping
- **Pattern Variations**: 30+ prefixes/suffixes per style
- **Length Preferences**: Short, Medium, Long, or Any length options
- **Console Logging**: Real-time progress tracking for administrators

## 📋 Requirements

### Dependencies
```bash
pip install python-telegram-bot telethon aiohttp
```

### Telegram Credentials
1. **Bot Token**: Get from [@BotFather](https://t.me/botfather)
2. **API Credentials**: Get from [my.telegram.org](https://my.telegram.org)
   - API ID
   - API Hash

## 🛠️ Installation

### 1. Clone Repository
```bash
git clone <repository-url>
cd id-suggestion
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Credentials
Edit the configuration section in `app.py`:

```python
# Configuration
TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
TELEGRAM_API_ID = "YOUR_API_ID_HERE"
TELEGRAM_API_HASH = "YOUR_API_HASH_HERE"
TELEGRAM_SESSION_STRING = "YOUR_SESSION_STRING_HERE"  # Optional
```

### 4. Run the Bot
```bash
python app.py
```

## ⚙️ Configuration Guide

### Getting Telegram Credentials

#### 1. Bot Token
1. Message [@BotFather](https://t.me/botfather) on Telegram
2. Use `/newbot` command
3. Follow instructions to create your bot
4. Copy the provided token

#### 2. API Credentials
1. Visit [my.telegram.org](https://my.telegram.org)
2. Log in with your phone number
3. Go to "API Development Tools"
4. Create a new application
5. Copy `api_id` and `api_hash`

#### 3. Session Setup (Optional)
- Run the bot once to generate a session file
- For deployment, you can use session strings instead of files

## 🎯 Usage

### User Commands
- `/start` - Initialize the bot and see welcome message
- `/generate` - Start username generation process
- `/help` - Show detailed help and feature list

### Generation Process
1. **Name Input**: Provide your name or nickname (optional)
2. **Interests**: List your interests (music, anime, tech, gaming, etc.)
3. **Style Selection**: Choose from 5 different styles
4. **Length Preference**: Select preferred username length
5. **Results**: Get 5-10 verified available usernames

### Available Styles
- **😎 Cool**: dark, cyber, pro, shadow, elite
- **🥰 Cute**: kawaii, sweet, bunny, angel
- **🖤 Hacker**: anon, root, null, binary
- **✨ Minimal**: clean, pure, simple, zen
- **🌸 Aesthetic**: vibe, divine, ethereal

## 🔧 Technical Details

### Username Generation Algorithm
1. **Base Variations**: Creates variations of input name
2. **Leet Speak**: Applies character replacements (o→0, a→4, etc.)
3. **Style Combinations**: Adds prefixes/suffixes based on selected style
4. **Interest Integration**: Incorporates user interests into patterns
5. **Creative Patterns**: Generates unique combination patterns
6. **Length Filtering**: Filters based on user preference
7. **Validation**: Ensures Telegram username compliance

### Character Replacements
```
o → 0    |    a → 4    |    t → 7
i → 1    |    s → 5    |    q → 9
l → 1    |    g → 6    |    b → 13
z → 2    |            |
```

### API Architecture
- **Bot API**: Handles user interactions and commands
- **MTProto API**: Performs accurate username availability checking
- **Caching Layer**: SQLite database for result caching
- **Rate Limiting**: 2-second delays between API calls

## 📊 Console Output

### Real-Time Monitoring
```
AI Generated 2847 unique username combinations

Starting username availability check for 2847 generated usernames...
============================================================

Checking 1/2847
   Result: @darkjohn123 - TAKEN

Checking 2/2847
   Result: @j0hn_shadow - AVAILABLE
FOUND AVAILABLE: @j0hn_shadow (Total found: 1)

TARGET REACHED! Found 10 available usernames, stopping search.
============================================================
```

## 🗄️ Database Schema

### Tables
- **users**: User information and activity tracking
- **generation_history**: Complete generation history
- **username_cache**: 24-hour availability cache

### Caching Strategy
- Results cached for 24 hours
- Reduces API calls by ~80%
- Automatic cache invalidation
- Database-backed persistence

## 🚨 Troubleshooting

### Common Issues

#### 1. Authentication Errors
```
Error: AuthKeyError
```
**Solution**: Re-authenticate with Telegram
- Delete session files
- Restart bot to re-authenticate

#### 2. Rate Limiting
```
Rate limited for @username, waiting 60 seconds
```
**Solution**: Automatic handling
- Bot automatically waits and retries
- No user action required

#### 3. Missing API Credentials
```
WARNING: Running in fallback mode
```
**Solution**: Configure API credentials
- Add API_ID and API_HASH
- Restart the bot

#### 4. No Available Usernames
```
No available usernames found with your criteria
```
**Solution**: Adjust criteria
- Try different interests
- Change style selection
- Use different base name

## 🔒 Security & Privacy

### Data Handling
- **User Data**: Stored locally in SQLite
- **Session Management**: Secure session handling
- **API Keys**: Keep credentials secure and private
- **No Data Sharing**: All processing done locally

## 📈 Performance

### Optimization Features
- **Smart Caching**: Reduces API calls by 80%
- **Batch Processing**: Efficient username generation
- **Early Stopping**: Stops at 10 available usernames
- **Memory Efficient**: Optimized for 2GB RAM servers

### Typical Performance
- **Generation Time**: 30 seconds - 5 minutes
- **API Efficiency**: 2 requests per second (safe rate)
- **Memory Usage**: ~50-100MB typical

### Code Style
- Follow PEP 8 guidelines
- Use type hints where appropriate
- Add docstrings for functions
- Include error handling

---

**Made with ❤️ for the Telegram community**

*Generate your perfect username today!*
