import discord
from discord.ext import commands, tasks
import os
import json
import datetime
import asyncio
import random
import sys
import aiohttp
import gc
import threading
from aiohttp import web
import asyncpg
import re
from dotenv import load_dotenv
import zoneinfo
import shlex

load_dotenv()

print("🚀 Starting Discord Bot on Render with Supabase...")
print("=" * 50)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix='!', intents=intents)

print("✅ Bot initialized")

# ==================== CLEANUP LIMITS ====================
MAX_MOVIES_PER_SERVER = 200          # Keep only the most recent 200 movies per server
MAX_SNIPE_MESSAGES_PER_CHANNEL = 50  # Keep only the last 50 deleted messages per channel
MAX_GLOBAL_SNIPES = 500              # Total snipes across all channels (safety)

# File paths
DATA_FILE = "bot_data.json"
ECONOMY_FILE = "economy_data.json"
SHOP_FILE = "shop_items.json"
ROLE_SALARIES_FILE = "role_salaries.json"
QUARANTINE_FILE = "quarantine_data.json"
BUSINESS_FILE = "business_data.json"
LAST_SALARY_FILE = "last_salary.json"
LAST_BUSINESS_PROFIT_FILE = "last_business_profit.json"
SIMPLE_BUSINESS_FILE = "simple_businesses.json"
MOVIES_FILE = "movies.json"
MOVIE_AWARD_FILE = "movie_award.json"
BANNED_WORDS_FILE = "banned_words.json"
PENDING_TAX_FILE = "pending_tax.json"
TAX_PUNISHMENT_FILE = "tax_punishment.json"
SPAM_CONFIG_FILE = "spam_config.json"
PREFIXLESS_CONFIG_FILE = "prefixless_config.json"
ELECTIONS_FILE = "elections.json"
SHARES_FILE = "shares.json"
BIRTHDAYS_FILE = "birthdays.json"
BIRTHDAY_CONFIG_FILE = "birthday_config.json"

# Clan files
CLANS_FILE = "clans.json"
CLAN_MEMBERS_FILE = "clan_members.json"
CLAN_INVITES_FILE = "clan_invites.json"

def format_money(amount):
    return f"${amount:,}"

def parse_money_amount(text: str) -> int:
    """Parse money shorthand: 5m = 5,000,000, 5b = 5,000,000,000, 5t = 5,000,000,000,000"""
    text = text.lower().strip()
    if text.endswith('t'):
        return int(float(text[:-1]) * 1_000_000_000_000)
    elif text.endswith('b'):
        return int(float(text[:-1]) * 1_000_000_000)
    elif text.endswith('m'):
        return int(float(text[:-1]) * 1_000_000)
    else:
        return int(text)

def parse_duration(text: str) -> int:
    """Parse duration: 5s = 5 seconds, 5m = 5 minutes, 5h = 5 hours"""
    text = text.lower().strip()
    if text.endswith('s'):
        return int(text[:-1])
    elif text.endswith('m'):
        return int(text[:-1]) * 60
    elif text.endswith('h'):
        return int(text[:-1]) * 3600
    else:
        return int(text)

def create_embed(title, description, color=discord.Color.blue()):
    embed = discord.Embed(title=title, description=description, color=color, timestamp=datetime.datetime.now())
    return embed

def has_staff_permission(member):
    if member.guild_permissions.administrator:
        return True
    staff_roles = ["Admin", "Moderator", "Staff", "Sergeant", "President", "Director general", "Secretary general", "Vice President", "Chief of staff", "Prime Minister"]
    for role in member.roles:
        if role.name in staff_roles:
            return True
    return False
    
    


def to_superscript(text: str) -> str:
    sup_map = {
        'a': 'ᵃ', 'b': 'ᵇ', 'c': 'ᶜ', 'd': 'ᵈ', 'e': 'ᵉ', 'f': 'ᶠ', 'g': 'ᵍ',
        'h': 'ʰ', 'i': 'ⁱ', 'j': 'ʲ', 'k': 'ᵏ', 'l': 'ˡ', 'm': 'ᵐ', 'n': 'ⁿ',
        'o': 'ᵒ', 'p': 'ᵖ', 'q': 'q', 'r': 'ʳ', 's': 'ˢ', 't': 'ᵗ', 'u': 'ᵘ',
        'v': 'ᵛ', 'w': 'ʷ', 'x': 'ˣ', 'y': 'ʸ', 'z': 'ᶻ',
        '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴', '5': '⁵',
        '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹',
        'A': 'ᴬ', 'B': 'ᴮ', 'C': 'ᶜ', 'D': 'ᴰ', 'E': 'ᴱ', 'F': 'ᶠ', 'G': 'ᴳ',
        'H': 'ᴴ', 'I': 'ᴵ', 'J': 'ᴶ', 'K': 'ᴷ', 'L': 'ᴸ', 'M': 'ᴹ', 'N': 'ᴺ',
        'O': 'ᴼ', 'P': 'ᴾ', 'Q': 'Q', 'R': 'ᴿ', 'S': 'ˢ', 'T': 'ᵀ', 'U': 'ᵁ',
        'V': 'ⱽ', 'W': 'ᵂ', 'X': 'ˣ', 'Y': 'ʸ', 'Z': 'ᶻ'
    }
    return ''.join(sup_map.get(ch, ch) for ch in text)

async def update_clan_nickname(member: discord.Member, clan_name: str = None):
    try:
        current_nick = member.display_name
        clean_name = re.sub(r'\s*\[.*?\]$', '', current_nick)
        sup_chars = ''.join(set(to_superscript('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')))
        clean_name = re.sub(rf'\s+[{re.escape(sup_chars)}]+$', '', clean_name)
        clean_name = re.sub(rf'[{re.escape(sup_chars)}]+$', '', clean_name)
        clean_name = clean_name.strip()
        if clan_name:
            tiny_clan = to_superscript(clan_name)
            new_nick = f"{clean_name} {tiny_clan}".strip()
            if len(new_nick) > 32:
                new_nick = new_nick[:32]
        else:
            new_nick = clean_name
        if new_nick != member.display_name:
            await member.edit(nick=new_nick, reason="Clan tag update")
    except discord.Forbidden:
        print(f"No permission to change nickname for {member.name}")
    except Exception as e:
        print(f"Nickname update error: {e}")

# ==================== SHARES DATA ====================
def load_shares():
    try:
        with open(SHARES_FILE, "r") as f:
            return json.load(f)
    except:
        return {"studios": {}, "businesses": {}}

def save_shares():
    with open(SHARES_FILE, "w") as f:
        json.dump(bot.shares, f, indent=2)

# ==================== BIRTHDAY FUNCTIONS ====================
def load_birthdays():
    try:
        with open(BIRTHDAYS_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_birthdays():
    with open(BIRTHDAYS_FILE, "w") as f:
        json.dump(bot.birthdays, f, indent=2)

def load_birthday_config():
    try:
        with open(BIRTHDAY_CONFIG_FILE, "r") as f:
            return json.load(f)
    except:
        return {"role_name": "Birthday", "wish": "🎉 Happy Birthday! Have an amazing day!"}

def save_birthday_config():
    with open(BIRTHDAY_CONFIG_FILE, "w") as f:
        json.dump(bot.birthday_config, f, indent=2)

# ==================== ELECTIONS ====================
def load_elections():
    try:
        with open(ELECTIONS_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_elections():
    with open(ELECTIONS_FILE, "w") as f:
        json.dump(bot.elections, f, indent=2)

# ==================== PREFIXLESS CONFIG FUNCTIONS ====================
def load_prefixless_config():
    try:
        with open(PREFIXLESS_CONFIG_FILE, "r") as f:
            return json.load(f)
    except:
        return {"enabled_roles": []}

def save_prefixless_config(config):
    with open(PREFIXLESS_CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)
        
        


# ==================== EARLY DATA LOADS ====================
def load_movies():
    try:
        with open(MOVIES_FILE, "r") as f:
            return json.load(f)
    except:
        return []

def save_movies():
    # Prune movies per server to MAX_MOVIES_PER_SERVER
    servers = {}
    for movie in bot.movies:
        server_id = movie.get("server_id")
        if server_id not in servers:
            servers[server_id] = []
        servers[server_id].append(movie)

    pruned = []
    for server_id, movie_list in servers.items():
        movie_list.sort(key=lambda m: m.get("date", "2000-01-01T00:00:00"), reverse=True)
        pruned.extend(movie_list[:MAX_MOVIES_PER_SERVER])

    bot.movies = pruned
    with open(MOVIES_FILE, "w") as f:
        json.dump(bot.movies, f, indent=2)

def load_last_movie_award():
    try:
        with open(MOVIE_AWARD_FILE, "r") as f:
            data = json.load(f)
            return data.get("last_award", "2000-01-01T00:00:00")
    except:
        return "2000-01-01T00:00:00"

def save_last_movie_award(date_iso):
    with open(MOVIE_AWARD_FILE, "w") as f:
        json.dump({"last_award": date_iso, "updated_at": datetime.datetime.now().isoformat()}, f, indent=2)

def load_pending_tax():
    try:
        with open(PENDING_TAX_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_pending_tax():
    with open(PENDING_TAX_FILE, "w") as f:
        json.dump(bot.pending_tax, f, indent=2)

def load_tax_punishments():
    try:
        with open(TAX_PUNISHMENT_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_tax_punishments():
    with open(TAX_PUNISHMENT_FILE, "w") as f:
        json.dump(bot.tax_punishments, f, indent=2)

def load_spam_config():
    try:
        with open(SPAM_CONFIG_FILE, "r") as f:
            return json.load(f)
    except:
        return {"enabled": False, "threshold": 5, "timeframe": 5, "action": "mute", "duration": 5}

def save_spam_config(config):
    with open(SPAM_CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

# ==================== LOAD DATA INTO BOT ====================
bot.movies = load_movies()
bot.pending_tax = load_pending_tax()
bot.tax_punishments = load_tax_punishments()
bot.spam_config = load_spam_config()
bot.prefixless_config = load_prefixless_config()
bot.user_messages = {}
bot.shares = load_shares()
bot.birthdays = load_birthdays()
bot.birthday_config = load_birthday_config()
bot.elections = load_elections()

# ==================== DATABASE CLASS ====================
class Database:
    def __init__(self):
        self.pool = None
        self.connected = False

    async def connect(self):
        database_url = os.getenv('SUPABASE_URL')
        if not database_url:
            print("⚠️  SUPABASE_URL not set – database features disabled.")
            return False
        try:
            self.pool = await asyncpg.create_pool(database_url, min_size=1, max_size=5)
            self.connected = True
            print("✅ Connected to Supabase PostgreSQL.")
            await self.create_tables()
            return True
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            return False

    async def create_tables(self):
        async with self.pool.acquire() as conn:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS economy (
                    user_id BIGINT PRIMARY KEY,
                    wallet INTEGER DEFAULT 0,
                    bank INTEGER DEFAULT 0,
                    last_daily TIMESTAMP,
                    last_work TIMESTAMP,
                    owned_items JSONB DEFAULT '{}',
                    businesses JSONB DEFAULT '{}'
                )
            ''')
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS warnings (
                    user_id BIGINT,
                    guild_id BIGINT,
                    count INTEGER DEFAULT 0,
                    PRIMARY KEY (user_id, guild_id)
                )
            ''')
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS quarantine (
                    guild_id BIGINT,
                    user_id BIGINT,
                    channel_id BIGINT,
                    reason TEXT,
                    quarantined_by BIGINT,
                    quarantined_at TIMESTAMP,
                    PRIMARY KEY (guild_id, user_id)
                )
            ''')
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS shop_items (
                    category TEXT,
                    item_name TEXT,
                    price INTEGER,
                    description TEXT,
                    emoji TEXT,
                    rarity TEXT DEFAULT 'common',
                    PRIMARY KEY (category, item_name)
                )
            ''')
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS role_salaries (
                    role_name TEXT PRIMARY KEY,
                    salary INTEGER
                )
            ''')
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS banned_words (
                    guild_id BIGINT,
                    word TEXT,
                    PRIMARY KEY (guild_id, word)
                )
            ''')
            print("✅ Database tables verified/created.")

    # ==================== ECONOMY METHODS ====================
    async def load_economy(self):
        wallets = {}
        banks = {}
        last_daily = {}
        last_work = {}
        owned_items = {}
        businesses = {}
        async with self.pool.acquire() as conn:
            rows = await conn.fetch('SELECT * FROM economy')
            for row in rows:
                uid = str(row['user_id'])
                wallets[uid] = row['wallet']
                banks[uid] = row['bank']
                if row['last_daily']:
                    last_daily[uid] = row['last_daily'].isoformat()
                if row['last_work']:
                    last_work[uid] = row['last_work'].isoformat()
                owned_items[uid] = json.loads(row['owned_items']) if row['owned_items'] else {}
                businesses[uid] = json.loads(row['businesses']) if row['businesses'] else {}
        return wallets, banks, last_daily, last_work, owned_items, businesses

    async def save_economy(self, wallets, banks, last_daily, last_work, owned_items, businesses):
        if not self.connected:
            return
        async with self.pool.acquire() as conn:
            for uid, wallet in wallets.items():
                bank = banks.get(uid, 0)
                ld = last_daily.get(uid)
                lw = last_work.get(uid)
                oi = json.dumps(owned_items.get(uid, {}))
                biz = json.dumps(businesses.get(uid, {}))
                await conn.execute('''
                    INSERT INTO economy (user_id, wallet, bank, last_daily, last_work, owned_items, businesses)
                    VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7::jsonb)
                    ON CONFLICT (user_id) DO UPDATE SET
                        wallet = EXCLUDED.wallet,
                        bank = EXCLUDED.bank,
                        last_daily = EXCLUDED.last_daily,
                        last_work = EXCLUDED.last_work,
                        owned_items = EXCLUDED.owned_items,
                        businesses = EXCLUDED.businesses
                ''', int(uid), wallet, bank,
                    datetime.datetime.fromisoformat(ld) if ld else None,
                    datetime.datetime.fromisoformat(lw) if lw else None,
                    oi, biz)

    # ==================== WARNINGS METHODS ====================
    async def load_warnings(self):
        warnings = {}
        async with self.pool.acquire() as conn:
            rows = await conn.fetch('SELECT * FROM warnings')
            for row in rows:
                guild = str(row['guild_id'])
                user = str(row['user_id'])
                if guild not in warnings:
                    warnings[guild] = {}
                warnings[guild][user] = row['count']
        return warnings

    async def save_warnings(self, warnings_dict):
        if not self.connected:
            return
        async with self.pool.acquire() as conn:
            for guild, users in warnings_dict.items():
                for user, count in users.items():
                    await conn.execute('''
                        INSERT INTO warnings (user_id, guild_id, count)
                        VALUES ($1, $2, $3)
                        ON CONFLICT (user_id, guild_id) DO UPDATE SET count = EXCLUDED.count
                    ''', int(user), int(guild), count)

    # ==================== QUARANTINE METHODS ====================
    async def load_quarantine(self):
        quarantined = {}
        channels = {}
        async with self.pool.acquire() as conn:
            rows = await conn.fetch('SELECT * FROM quarantine')
            for row in rows:
                guild = str(row['guild_id'])
                user = str(row['user_id'])
                if guild not in quarantined:
                    quarantined[guild] = {}
                quarantined[guild][user] = {
                    "channel_id": row['channel_id'],
                    "reason": row['reason'],
                    "quarantined_by": str(row['quarantined_by']),
                    "quarantined_at": row['quarantined_at'].isoformat()
                }
                if guild not in channels:
                    channels[guild] = {}
                channels[guild][str(row['channel_id'])] = user
        return quarantined, channels

    async def save_quarantine(self, quarantined_dict):
        if not self.connected:
            return
        async with self.pool.acquire() as conn:
            await conn.execute('DELETE FROM quarantine')
            for guild, users in quarantined_dict.items():
                for user, info in users.items():
                    await conn.execute('''
                        INSERT INTO quarantine (guild_id, user_id, channel_id, reason, quarantined_by, quarantined_at)
                        VALUES ($1, $2, $3, $4, $5, $6)
                    ''', int(guild), int(user), info['channel_id'], info['reason'],
                        int(info['quarantined_by']), datetime.datetime.fromisoformat(info['quarantined_at']))

    # ==================== SHOP ITEMS METHODS ====================
    async def load_shop_items(self):
        items = {}
        async with self.pool.acquire() as conn:
            rows = await conn.fetch('SELECT * FROM shop_items')
            for row in rows:
                cat = row['category']
                if cat not in items:
                    items[cat] = []
                items[cat].append({
                    "name": row['item_name'],
                    "price": row['price'],
                    "description": row['description'] or "",
                    "emoji": row['emoji'] or "🛍️",
                    "rarity": row.get('rarity', 'common')
                })
        return items

    async def save_shop_items(self, items_dict):
        if not self.connected:
            return
        async with self.pool.acquire() as conn:
            await conn.execute('DELETE FROM shop_items')
            for category, item_list in items_dict.items():
                for item in item_list:
                    await conn.execute('''
                        INSERT INTO shop_items (category, item_name, price, description, emoji, rarity)
                        VALUES ($1, $2, $3, $4, $5, $6)
                    ''', category, item['name'], item['price'],
                        item.get('description', ''), item.get('emoji', '🛍️'), item.get('rarity', 'common'))

    # ==================== ROLE SALARIES METHODS ====================
    async def load_role_salaries(self):
        salaries = {"default": 1000}
        async with self.pool.acquire() as conn:
            rows = await conn.fetch('SELECT * FROM role_salaries')
            for row in rows:
                salaries[row['role_name']] = row['salary']
        return salaries

    async def save_role_salaries(self, salaries_dict):
        if not self.connected:
            return
        async with self.pool.acquire() as conn:
            await conn.execute('DELETE FROM role_salaries')
            for role, salary in salaries_dict.items():
                await conn.execute('''
                    INSERT INTO role_salaries (role_name, salary) VALUES ($1, $2)
                ''', role, salary)

    # ==================== BANNED WORDS METHODS ====================
    async def load_banned_words(self):
        banned = {}
        async with self.pool.acquire() as conn:
            rows = await conn.fetch('SELECT * FROM banned_words')
            for row in rows:
                guild = str(row['guild_id'])
                word = row['word']
                if guild not in banned:
                    banned[guild] = []
                banned[guild].append(word)
        return banned

    async def save_banned_words(self, banned_dict):
        if not self.connected:
            return
        async with self.pool.acquire() as conn:
            await conn.execute('DELETE FROM banned_words')
            for guild, words in banned_dict.items():
                for word in words:
                    await conn.execute('''
                        INSERT INTO banned_words (guild_id, word) VALUES ($1, $2)
                    ''', int(guild), word)

    async def close(self):
        if self.pool:
            await self.pool.close()

# Create the global database instance
db = Database()




# ==================== DATA LOADING FUNCTIONS ====================
def load_data():
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except:
        return {"afk_users": {}, "warnings": {}, "muted_users": {}}

def load_economy():
    try:
        with open(ECONOMY_FILE, "r") as f:
            return json.load(f)
    except:
        return {"wallets": {}, "banks": {}, "last_daily": {}, "last_work": {}, "owned_items": {}, "businesses": {}}

def load_shop():
    try:
        with open(SHOP_FILE, "r") as f:
            data = json.load(f)
            for cat, items in data.items():
                for item in items:
                    if 'rarity' not in item:
                        item['rarity'] = 'common'
            required_cats = ["roles", "vehicles", "properties", "aircraft", "yachts", "jewelry", "pets", "collectables"]
            for cat in required_cats:
                if cat not in data:
                    data[cat] = [] if cat != "aircraft" else {}
            return data
    except:
        return {
            "roles": [], "vehicles": [], "properties": [], 
            "aircraft": {}, "yachts": [], "jewelry": [], 
            "pets": [], "collectables": []
        }

def load_role_salaries():
    try:
        with open(ROLE_SALARIES_FILE, "r") as f:
            return json.load(f)
    except:
        return {"default": 1000, "Admin": 5000, "Moderator": 3000}

def load_quarantine():
    try:
        with open(QUARANTINE_FILE, "r") as f:
            return json.load(f)
    except:
        return {"quarantined_users": {}, "quarantine_channels": {}}

def load_businesses():
    try:
        with open(BUSINESS_FILE, "r") as f:
            return json.load(f)
    except:
        return {"businesses": {}, "business_types": {}}

def load_last_salary():
    try:
        with open(LAST_SALARY_FILE, "r") as f:
            return json.load(f)
    except:
        return {"last_salary": "2000-01-01T00:00:00"}

def load_last_business_profit():
    try:
        with open(LAST_BUSINESS_PROFIT_FILE, "r") as f:
            return json.load(f)
    except:
        return {"last_business_profit": "2000-01-01T00:00:00"}

def load_simple_businesses():
    try:
        with open(SIMPLE_BUSINESS_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_simple_businesses():
    with open(SIMPLE_BUSINESS_FILE, "w") as f:
        json.dump(bot.simple_businesses, f, indent=2)

def load_banned_words():
    try:
        with open(BANNED_WORDS_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_banned_words():
    with open(BANNED_WORDS_FILE, "w") as f:
        json.dump(bot.banned_words, f, indent=2)

def load_clans():
    try:
        with open(CLANS_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_clans():
    with open(CLANS_FILE, "w") as f:
        json.dump(bot.clans, f, indent=2)

def load_clan_members():
    try:
        with open(CLAN_MEMBERS_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_clan_members():
    with open(CLAN_MEMBERS_FILE, "w") as f:
        json.dump(bot.clan_members, f, indent=2)

def load_clan_invites():
    try:
        with open(CLAN_INVITES_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_clan_invites():
    with open(CLAN_INVITES_FILE, "w") as f:
        json.dump(bot.clan_invites, f, indent=2)

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump({"afk_users": bot.afk_users, "warnings": bot.warnings, "muted_users": bot.muted_users}, f, indent=2)

def save_economy():
    with open(ECONOMY_FILE, "w") as f:
        json.dump({
            "wallets": bot.wallets, "banks": bot.banks, "last_daily": bot.last_daily,
            "last_work": bot.last_work, "owned_items": bot.owned_items, "businesses": bot.businesses
        }, f, indent=2)

def save_quarantine():
    with open(QUARANTINE_FILE, "w") as f:
        json.dump({"quarantined_users": bot.quarantined_users, "quarantine_channels": bot.quarantine_channels}, f, indent=2)

def save_businesses():
    with open(BUSINESS_FILE, "w") as f:
        json.dump({"businesses": bot.businesses, "business_types": bot.business_types}, f, indent=2)

def save_last_salary(last_salary_time):
    with open(LAST_SALARY_FILE, "w") as f:
        json.dump({"last_salary": last_salary_time, "saved_at": datetime.datetime.now().isoformat()}, f, indent=2)

def save_last_business_profit(last_profit_time):
    with open(LAST_BUSINESS_PROFIT_FILE, "w") as f:
        json.dump({"last_business_profit": last_profit_time, "saved_at": datetime.datetime.now().isoformat()}, f, indent=2)

async def async_save_economy():
    if db.connected:
        await db.save_economy(bot.wallets, bot.banks, bot.last_daily, bot.last_work, bot.owned_items, bot.businesses)

async def async_save_warnings():
    if db.connected:
        await db.save_warnings(bot.warnings)

async def async_save_quarantine():
    if db.connected:
        await db.save_quarantine(bot.quarantined_users)

async def async_save_shop_items():
    if db.connected:
        await db.save_shop_items(bot.shop_items)

async def async_save_role_salaries():
    if db.connected:
        await db.save_role_salaries(bot.role_salaries)

async def async_save_banned_words():
    if db.connected:
        await db.save_banned_words(bot.banned_words)

# ==================== LOAD ALL DATA INTO BOT ====================
print("📊 Loading data...")
data = load_data()
economy = load_economy()
shop_items = load_shop()
role_salaries = load_role_salaries()
quarantine_data = load_quarantine()
business_data = load_businesses()
last_salary_data = load_last_salary()
last_business_profit_data = load_last_business_profit()
simple_business_data = load_simple_businesses()
banned_words_data = load_banned_words()

if 'RAILWAY_ENVIRONMENT' in os.environ:
    print("⚠️  WARNING: Running on Railway - JSON data may reset on restart!")
    print("💡 Tip: Data is saved to Supabase if SUPABASE_URL is set.")

bot.afk_users = data.get("afk_users", {})
bot.warnings = data.get("warnings", {})
bot.muted_users = data.get("muted_users", {})
bot.wallets = economy.get("wallets", {})
bot.banks = economy.get("banks", {})
bot.last_daily = economy.get("last_daily", {})
bot.last_work = economy.get("last_work", {})
bot.owned_items = economy.get("owned_items", {})
bot.businesses = economy.get("businesses", {})
bot.shop_items = shop_items
bot.role_salaries = role_salaries
bot.quarantined_users = quarantine_data.get("quarantined_users", {})
bot.quarantine_channels = quarantine_data.get("quarantine_channels", {})
bot.business_types = business_data.get("business_types", {})
bot.start_time = datetime.datetime.now()
bot.active_lawsuits = {}
bot.simple_businesses = simple_business_data
bot.snipe_messages = {}
bot.pending_trades = {}
bot.clans = load_clans()
bot.clan_members = load_clan_members()
bot.clan_invites = load_clan_invites()
bot.banned_words = banned_words_data
bot.deleted_banned_messages = []

# Load actor stats
try:
    with open("actor_stats.json", "r") as f:
        bot.actor_stats = json.load(f)
except:
    bot.actor_stats = {}

# Initialize studios
bot.studios = {}

# ==================== AUTO-MOD RULE FUNCTIONS ====================
def load_auto_rules():
    try:
        with open("auto_mod_rules.json", "r") as f:
            return json.load(f)
    except:
        return {}

def save_auto_rules(rules):
    with open("auto_mod_rules.json", "w") as f:
        json.dump(rules, f, indent=2)

def load_warning_counts():
    try:
        with open("auto_mod_warnings.json", "r") as f:
            return json.load(f)
    except:
        return {}

def save_warning_counts(counts):
    with open("auto_mod_warnings.json", "w") as f:
        json.dump(counts, f, indent=2)

bot.auto_rules = load_auto_rules()
bot.auto_warnings = load_warning_counts()

# ==================== ROLE TAX RATES ====================
try:
    with open("role_tax_rates.json", "r") as f:
        bot.role_tax_rates = json.load(f)
except:
    bot.role_tax_rates = {}

# ==================== TIMEZONE DATA ====================
try:
    with open("user_timezones.json", "r") as f:
        bot.user_timezones = json.load(f)
except:
    bot.user_timezones = {}

print("✅ Data loaded successfully!")

# ==================== WEB SERVER ====================
async def health_check(request):
    return web.Response(text="OK")

async def run_web_server():
    app = web.Application()
    app.router.add_get('/health', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get('PORT', 8000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"🌐 Health check server running on port {port}")
    await asyncio.Event().wait()

def start_web_server():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_web_server())
    loop.run_forever()

threading.Thread(target=start_web_server, daemon=True).start()

# ==================== ON_READY EVENT ====================
@bot.event
async def on_ready():
    print(f'✅ Logged in as {bot.user.name}')
    print(f'🆔 Bot ID: {bot.user.id}')
    print(f'🔗 Connected to {len(bot.guilds)} servers')
    print(f'🏢 Host: Render')

    if await db.connect():
        wallets, banks, last_daily, last_work, owned_items, businesses = await db.load_economy()
        if wallets:
            bot.wallets = wallets
            bot.banks = banks
            bot.last_daily = last_daily
            bot.last_work = last_work
            bot.owned_items = owned_items
            bot.businesses = businesses
            print("✅ Loaded economy data from Supabase.")
        else:
            print("ℹ️ No economy data in Supabase yet – using JSON.")
        warnings = await db.load_warnings()
        if warnings:
            bot.warnings = warnings
            print("✅ Loaded warnings from Supabase.")
        quarantined, channels = await db.load_quarantine()
        if quarantined:
            bot.quarantined_users = quarantined
            bot.quarantine_channels = channels
            print("✅ Loaded quarantine data from Supabase.")
        shop_items_db = await db.load_shop_items()
        if shop_items_db:
            bot.shop_items = shop_items_db
            print("✅ Loaded shop items from Supabase.")
        role_salaries_db = await db.load_role_salaries()
        if role_salaries_db:
            bot.role_salaries = role_salaries_db
            print("✅ Loaded role salaries from Supabase.")
        banned_words_db = await db.load_banned_words()
        if banned_words_db:
            bot.banned_words = banned_words_db
            print("✅ Loaded banned words from Supabase.")

    # Ensure all data is loaded
    if not hasattr(bot, 'pending_tax'):
        bot.pending_tax = load_pending_tax()
    if not hasattr(bot, 'tax_punishments'):
        bot.tax_punishments = load_tax_punishments()
    if not hasattr(bot, 'spam_config'):
        bot.spam_config = load_spam_config()
    if not hasattr(bot, 'prefixless_config'):
        bot.prefixless_config = load_prefixless_config()
    if not hasattr(bot, 'shares'):
        bot.shares = load_shares()
    if not hasattr(bot, 'birthdays'):
        bot.birthdays = load_birthdays()
    if not hasattr(bot, 'birthday_config'):
        bot.birthday_config = load_birthday_config()
    if not hasattr(bot, 'elections'):
        bot.elections = load_elections()

    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="!h for commands"))
    print("🎉 Bot is ready and running 24/7!")

    # ========== START BACKGROUND TASKS ==========
    await asyncio.sleep(5)
    if not weekly_salaries.is_running():
        weekly_salaries.start()
        print("💰 Weekly salaries task started")
    if not check_muted_users.is_running():
        check_muted_users.start()
        print("🔇 Mute check task started")
    if not business_profits.is_running():
        business_profits.start()
        print("🏢 Business profits task started")
    if not weekly_movie_award.is_running():
        weekly_movie_award.start()
        print("🏆 Weekly movie award task started")
    if not check_loan_defaults.is_running():
        check_loan_defaults.start()
        print("💸 Loan default & repossession checker started")
    if not check_tax_punishments.is_running():
        check_tax_punishments.start()
        print("💰 Tax punishment checker started")
    if not check_birthdays.is_running():
        check_birthdays.start()
        print("🎂 Birthday checker started")
    if not check_elections.is_running():
        check_elections.start()
        print("🗳️ Election checker started")

    # Prune movies on startup
    save_movies()
    print("🎬 Pruned movies on startup")

# ==================== PREFIXLESS ROLE MANAGEMENT ====================
def can_use_prefixless(member: discord.Member) -> bool:
    """Check if member has any role that allows prefixless commands."""
    if member.guild_permissions.administrator:
        return True
    for role in member.roles:
        if role.name in bot.prefixless_config.get("enabled_roles", []):
            return True
    return False

@bot.command(name="prefixless")
@commands.has_permissions(administrator=True)
async def add_prefixless(ctx, *, role_name: str):
    """Add a role to prefixless access. Usage: !prefixless Admin"""
    role = discord.utils.get(ctx.guild.roles, name=role_name)
    if not role:
        for r in ctx.guild.roles:
            if r.name.lower() == role_name.lower():
                role = r
                break
    if not role:
        return await ctx.send(f"❌ Role `{role_name}` not found.")
    
    config = bot.prefixless_config
    if role.name in config["enabled_roles"]:
        return await ctx.send(f"⚠️ `{role.name}` already has prefixless access.")
    
    config["enabled_roles"].append(role.name)
    save_prefixless_config(config)
    embed = create_embed("✅ Prefixless Added", f"**{role.name}** can now use commands without `!` prefix.", discord.Color.green())
    await ctx.send(embed=embed)

@bot.command(name="rp", aliases=["removeprefixless"])
@commands.has_permissions(administrator=True)
async def remove_prefixless(ctx, *, role_name: str):
    """Remove a role from prefixless access. Usage: !rp Admin"""
    role = discord.utils.get(ctx.guild.roles, name=role_name)
    if not role:
        for r in ctx.guild.roles:
            if r.name.lower() == role_name.lower():
                role = r
                break
    if not role:
        return await ctx.send(f"❌ Role `{role_name}` not found.")
    
    config = bot.prefixless_config
    if role.name not in config["enabled_roles"]:
        return await ctx.send(f"⚠️ `{role.name}` does not have prefixless access.")
    
    config["enabled_roles"].remove(role.name)
    save_prefixless_config(config)
    embed = create_embed("✅ Prefixless Removed", f"**{role.name}** can no longer use commands without `!` prefix.", discord.Color.red())
    await ctx.send(embed=embed)

@bot.command(name="prefixlesslist", aliases=["plist"])
@commands.has_permissions(administrator=True)
async def list_prefixless(ctx):
    """List all roles with prefixless access."""
    config = bot.prefixless_config
    if not config["enabled_roles"]:
        return await ctx.send("📭 No roles have prefixless access.")
    embed = discord.Embed(title="🔓 Prefixless Access Roles", color=discord.Color.blue())
    embed.description = "\n".join(f"• {role}" for role in config["enabled_roles"])
    await ctx.send(embed=embed)
    
    


# ==================== COUNTRY GUESSER GAME ====================
COUNTRIES_BY_CONTINENT = {
    "africa": [
        ("Algeria", "dz"), ("Angola", "ao"), ("Benin", "bj"), ("Botswana", "bw"),
        ("Burkina Faso", "bf"), ("Burundi", "bi"), ("Cabo Verde", "cv"), ("Cameroon", "cm"),
        ("Central African Republic", "cf"), ("Chad", "td"), ("Comoros", "km"), ("Congo", "cg"),
        ("Djibouti", "dj"), ("Egypt", "eg"), ("Equatorial Guinea", "gq"), ("Eritrea", "er"),
        ("Eswatini", "sz"), ("Ethiopia", "et"), ("Gabon", "ga"), ("Gambia", "gm"),
        ("Ghana", "gh"), ("Guinea", "gn"), ("Guinea-Bissau", "gw"), ("Ivory Coast", "ci"),
        ("Kenya", "ke"), ("Lesotho", "ls"), ("Liberia", "lr"), ("Libya", "ly"),
        ("Madagascar", "mg"), ("Malawi", "mw"), ("Mali", "ml"), ("Mauritania", "mr"),
        ("Mauritius", "mu"), ("Morocco", "ma"), ("Mozambique", "mz"), ("Namibia", "na"),
        ("Niger", "ne"), ("Nigeria", "ng"), ("Rwanda", "rw"), ("Sao Tome and Principe", "st"),
        ("Senegal", "sn"), ("Seychelles", "sc"), ("Sierra Leone", "sl"), ("Somalia", "so"),
        ("South Africa", "za"), ("South Sudan", "ss"), ("Sudan", "sd"), ("Tanzania", "tz"),
        ("Togo", "tg"), ("Tunisia", "tn"), ("Uganda", "ug"), ("Zambia", "zm"), ("Zimbabwe", "zw")
    ],
    "asia": [
        ("Afghanistan", "af"), ("Armenia", "am"), ("Azerbaijan", "az"), ("Bahrain", "bh"),
        ("Bangladesh", "bd"), ("Bhutan", "bt"), ("Brunei", "bn"), ("Cambodia", "kh"),
        ("China", "cn"), ("Cyprus", "cy"), ("Georgia", "ge"), ("India", "in"),
        ("Indonesia", "id"), ("Iran", "ir"), ("Iraq", "iq"), ("Israel", "il"),
        ("Japan", "jp"), ("Jordan", "jo"), ("Kazakhstan", "kz"), ("Kuwait", "kw"),
        ("Kyrgyzstan", "kg"), ("Laos", "la"), ("Lebanon", "lb"), ("Malaysia", "my"),
        ("Maldives", "mv"), ("Mongolia", "mn"), ("Myanmar", "mm"), ("Nepal", "np"),
        ("North Korea", "kp"), ("Oman", "om"), ("Pakistan", "pk"), ("Palestine", "ps"),
        ("Philippines", "ph"), ("Qatar", "qa"), ("Russia", "ru"), ("Saudi Arabia", "sa"),
        ("Singapore", "sg"), ("South Korea", "kr"), ("Sri Lanka", "lk"), ("Syria", "sy"),
        ("Taiwan", "tw"), ("Tajikistan", "tj"), ("Thailand", "th"), ("Timor-Leste", "tl"),
        ("Turkey", "tr"), ("Turkmenistan", "tm"), ("United Arab Emirates", "ae"),
        ("Uzbekistan", "uz"), ("Vietnam", "vn"), ("Yemen", "ye")
    ],
    "europe": [
        ("Albania", "al"), ("Andorra", "ad"), ("Austria", "at"), ("Belarus", "by"),
        ("Belgium", "be"), ("Bosnia and Herzegovina", "ba"), ("Bulgaria", "bg"),
        ("Croatia", "hr"), ("Cyprus", "cy"), ("Czech Republic", "cz"), ("Denmark", "dk"),
        ("Estonia", "ee"), ("Finland", "fi"), ("France", "fr"), ("Germany", "de"),
        ("Greece", "gr"), ("Hungary", "hu"), ("Iceland", "is"), ("Ireland", "ie"),
        ("Italy", "it"), ("Kosovo", "xk"), ("Latvia", "lv"), ("Liechtenstein", "li"),
        ("Lithuania", "lt"), ("Luxembourg", "lu"), ("Malta", "mt"), ("Moldova", "md"),
        ("Monaco", "mc"), ("Montenegro", "me"), ("Netherlands", "nl"), ("North Macedonia", "mk"),
        ("Norway", "no"), ("Poland", "pl"), ("Portugal", "pt"), ("Romania", "ro"),
        ("Russia", "ru"), ("San Marino", "sm"), ("Serbia", "rs"), ("Slovakia", "sk"),
        ("Slovenia", "si"), ("Spain", "es"), ("Sweden", "se"), ("Switzerland", "ch"),
        ("Ukraine", "ua"), ("United Kingdom", "gb"), ("Vatican City", "va")
    ],
    "north_america": [
        ("Antigua and Barbuda", "ag"), ("Bahamas", "bs"), ("Barbados", "bb"),
        ("Belize", "bz"), ("Canada", "ca"), ("Costa Rica", "cr"), ("Cuba", "cu"),
        ("Dominica", "dm"), ("Dominican Republic", "do"), ("El Salvador", "sv"),
        ("Grenada", "gd"), ("Guatemala", "gt"), ("Haiti", "ht"), ("Honduras", "hn"),
        ("Jamaica", "jm"), ("Mexico", "mx"), ("Nicaragua", "ni"), ("Panama", "pa"),
        ("Saint Kitts and Nevis", "kn"), ("Saint Lucia", "lc"), ("Saint Vincent and the Grenadines", "vc"),
        ("Trinidad and Tobago", "tt"), ("United States", "us")
    ],
    "south_america": [
        ("Argentina", "ar"), ("Bolivia", "bo"), ("Brazil", "br"), ("Chile", "cl"),
        ("Colombia", "co"), ("Ecuador", "ec"), ("Guyana", "gy"), ("Paraguay", "py"),
        ("Peru", "pe"), ("Suriname", "sr"), ("Uruguay", "uy"), ("Venezuela", "ve")
    ],
    "oceania": [
        ("Australia", "au"), ("Fiji", "fj"), ("Kiribati", "ki"), ("Marshall Islands", "mh"),
        ("Micronesia", "fm"), ("Nauru", "nr"), ("New Zealand", "nz"), ("Palau", "pw"),
        ("Papua New Guinea", "pg"), ("Samoa", "ws"), ("Solomon Islands", "sb"),
        ("Tonga", "to"), ("Tuvalu", "tv"), ("Vanuatu", "vu")
    ]
}

ALL_COUNTRIES = []
for continent, countries in COUNTRIES_BY_CONTINENT.items():
    ALL_COUNTRIES.extend(countries)

active_games = {}

@bot.command(name="startguess")
async def start_guess_game(ctx, continent: str = "random", rounds: int = 10):
    channel_id = ctx.channel.id
    if channel_id in active_games:
        return await ctx.send("❌ A game is already running in this channel. End it with `!endguess` first.")
    continent = continent.lower()
    if continent == "random":
        country_pool = ALL_COUNTRIES.copy()
    elif continent in COUNTRIES_BY_CONTINENT:
        country_pool = COUNTRIES_BY_CONTINENT[continent].copy()
    else:
        return await ctx.send(f"❌ Invalid continent. Options: africa, asia, europe, north_america, south_america, oceania, random")
    if rounds < 1 or rounds > 30:
        return await ctx.send("❌ Rounds must be between 1 and 30.")
    random.shuffle(country_pool)
    game_data = {
        "active": True,
        "channel_id": channel_id,
        "countries": country_pool[:rounds],
        "current_index": 0,
        "round_ended": False,
        "correct_this_round": [],
        "points_awarded": {1: 3, 2: 2, 3: 1},
        "timer_task": None,
        "continent": continent,
        "total_rounds": rounds,
        "game_scores": {}
    }
    active_games[channel_id] = game_data
    await ctx.send(f"🎮 **Country Guesser Game Started!**\n🌍 Continent: {continent.title()}\n🏆 {rounds} flags will be shown.\n📢 **Just type the country name** (case insensitive) to guess!\nThe first correct gets 3 points, second 2 points, third 1 point.\nYou have 10 seconds per flag.\nUse `!endguess` to stop early.")
    await next_round(ctx)
    
    


async def next_round(ctx):
    channel_id = ctx.channel.id
    game = active_games.get(channel_id)
    if not game or not game["active"]:
        return
    if game["current_index"] >= len(game["countries"]):
        await end_game(ctx)
        return
    game["round_ended"] = False
    game["correct_this_round"] = []
    country, code = game["countries"][game["current_index"]]
    game["current_country"] = country
    game["current_code"] = code
    flag_url = f"https://flagcdn.com/w640/{code}.png"
    embed = discord.Embed(title=f"🌍 Flag {game['current_index']+1}/{game['total_rounds']}", color=discord.Color.blue())
    embed.set_image(url=flag_url)
    embed.set_footer(text="Type the country name! You have 10 seconds.")
    msg = await ctx.send(embed=embed)
    game["round_message_id"] = msg.id
    async def timer():
        await asyncio.sleep(10)
        if channel_id in active_games and active_games[channel_id] == game and not game["round_ended"]:
            game["round_ended"] = True
            correct_name = game["current_country"]
            await ctx.send(f"⏰ Time's up! The correct answer was **{correct_name}**. Moving to next flag in 5 seconds...")
            await asyncio.sleep(5)
            game["current_index"] += 1
            await next_round(ctx)
    task = asyncio.create_task(timer())
    game["timer_task"] = task

async def end_game(ctx):
    channel_id = ctx.channel.id
    game = active_games.pop(channel_id, None)
    if game and game.get("timer_task"):
        game["timer_task"].cancel()
    if not game or not game["game_scores"]:
        await ctx.send("🛑 Game ended. No scores recorded.")
        return
    sorted_scores = sorted(game["game_scores"].items(), key=lambda x: x[1], reverse=True)[:10]
    embed = create_embed("🏆 Game Final Scores", "", discord.Color.gold())
    medals = ["🥇", "🥈", "🥉"]
    for i, (uid, score) in enumerate(sorted_scores, 1):
        try:
            user = await bot.fetch_user(int(uid))
            name = user.display_name
        except:
            name = f"<@{uid}>"
        prefix = medals[i-1] if i <= 3 else f"{i}."
        embed.add_field(name=f"{prefix} {name}", value=f"⭐ {score} points", inline=False)
    await ctx.send(embed=embed)

@bot.command(name="endguess")
async def end_guess_game(ctx):
    channel_id = ctx.channel.id
    if channel_id not in active_games:
        return await ctx.send("❌ No active game in this channel.")
    await end_game(ctx)

@bot.command(name="countryscore")
async def country_score_multi(ctx, member: discord.Member = None):
    target = member or ctx.author
    user_id = str(target.id)
    game = active_games.get(ctx.channel.id)
    if not game:
        return await ctx.send("No active game in this channel.")
    score = game["game_scores"].get(user_id, 0)
    embed = create_embed(f"🌍 {target.name}'s Game Score", f"**Points:** {score}", discord.Color.gold())
    await ctx.send(embed=embed)

@bot.command(name="countrylb")
async def country_leaderboard_multi(ctx):
    game = active_games.get(ctx.channel.id)
    if not game or not game["game_scores"]:
        return await ctx.send("No active game or no scores yet.")
    sorted_scores = sorted(game["game_scores"].items(), key=lambda x: x[1], reverse=True)[:10]
    embed = create_embed("🏆 Current Game Leaderboard", "", discord.Color.gold())
    medals = ["🥇", "🥈", "🥉"]
    for i, (uid, score) in enumerate(sorted_scores, 1):
        try:
            user = await bot.fetch_user(int(uid))
            name = user.display_name
        except:
            name = f"<@{uid}>"
        prefix = medals[i-1] if i <= 3 else f"{i}."
        embed.add_field(name=f"{prefix} {name}", value=f"⭐ {score} points", inline=False)
    await ctx.send(embed=embed)
    
    


# ==================== EVENT HANDLERS ====================
async def auto_unmute(member, mute_role, guild, minutes):
    await asyncio.sleep(minutes * 60)
    if mute_role in member.roles:
        try:
            await member.remove_roles(mute_role)
        except:
            pass

@bot.event
async def on_member_join(member):
    print(f"🔔 DEBUG: {member.name} joined {member.guild.name}")
    embed = create_embed("Welcome", f"Welcome {member.mention} to {member.guild.name}!", discord.Color.green())
    embed.add_field(name="Member Count", value=f"{member.guild.member_count}", inline=True)
    embed.set_image(url="https://i.imgur.com/xfwhTnF.png")
    if member.avatar:
        embed.set_thumbnail(url=member.avatar.url)

    target_channels = ["welcome", "general"]
    sent_to_any = False

    for ch_name in target_channels:
        channel = discord.utils.get(member.guild.text_channels, name=ch_name)
        if channel:
            perms = channel.permissions_for(member.guild.me)
            if perms.send_messages:
                try:
                    await channel.send(embed=embed)
                    print(f"  → Welcome message sent in #{ch_name}")
                    sent_to_any = True
                except Exception as e:
                    print(f"  → Failed to send in #{ch_name}: {e}")
            else:
                print(f"  → Bot lacks 'Send Messages' in #{ch_name}")

    if not sent_to_any:
        channel = member.guild.system_channel
        if channel:
            perms = channel.permissions_for(member.guild.me)
            if perms.send_messages:
                await channel.send(embed=embed)
                print("  → Welcome message sent in system channel")
            else:
                print("  → Bot lacks 'Send Messages' in system channel")
        else:
            print("  → No suitable channel found for welcome message")

@bot.event
async def on_member_remove(member):
    user_id = str(member.id)
    if user_id in bot.businesses:
        del bot.businesses[user_id]
        save_businesses()
        print(f"🗑️ Deleted business for {member.name} (left server)")
    loans = load_loans_adv()
    if user_id in loans:
        del loans[user_id]
        save_loans_adv(loans)
        print(f"🗑️ Deleted loan for {member.name} (left server)")

# ==================== SPAM DETECTION HELPER ====================
def is_spam(message_content: str, config: dict) -> bool:
    emojis = re.findall(r'[\U00010000-\U0010ffff]', message_content)
    if len(emojis) >= config.get("threshold", 3):
        return True
    if len(message_content) > 10:
        for char in set(message_content):
            if message_content.count(char) > config.get("threshold", 3) * 3:
                return True
    invite_patterns = [
        r'discord\.gg\/[a-zA-Z0-9]+',
        r'discordapp\.com\/invite\/[a-zA-Z0-9]+',
        r'discord\.com\/invite\/[a-zA-Z0-9]+'
    ]
    for pattern in invite_patterns:
        if re.search(pattern, message_content.lower()):
            return True
    return False
    
    


@bot.event
async def on_message(message):
    # ========== PREFIXLESS COMMAND HANDLING ==========
    if can_use_prefixless(message.author):
        content = message.content.strip()
        if content and not content.startswith('!'):
            parts = shlex.split(content)
            if parts:
                cmd_name = parts[0].lower()
                cmd = bot.get_command(cmd_name)
                if cmd:
                    ctx = await bot.get_context(message)
                    ctx.command = cmd
                    ctx.invoked_with = cmd.name
                    ctx.args = [ctx]
                    message.content = f"!{cmd_name} " + " ".join(parts[1:]) if len(parts) > 1 else f"!{cmd_name}"
                    await bot.process_commands(message)
                    return

    await bot.process_commands(message)

    if message.author.bot or not message.guild:
        return

    user_id = str(message.author.id)
    guild_id = str(message.guild.id)

    # ----- SPAM DETECTION -----
    config = bot.spam_config
    if config.get("enabled", False):
        if user_id not in bot.user_messages:
            bot.user_messages[user_id] = []
        bot.user_messages[user_id].append(datetime.datetime.now())
        timeframe = datetime.timedelta(seconds=config.get("timeframe", 5))
        bot.user_messages[user_id] = [ts for ts in bot.user_messages[user_id] if datetime.datetime.now() - ts < timeframe]
        if len(bot.user_messages[user_id]) > config.get("threshold", 3):
            if is_spam(message.content, config):
                action = config.get("action", "mute")
                duration = config.get("duration", 5)
                try:
                    if action == "mute":
                        mute_role = discord.utils.get(message.guild.roles, name="Muted")
                        if not mute_role:
                            try:
                                mute_role = await message.guild.create_role(name="Muted", color=discord.Color.dark_gray())
                                for channel in message.guild.channels:
                                    await channel.set_permissions(mute_role, send_messages=False, speak=False)
                            except:
                                pass
                        if mute_role:
                            await message.author.add_roles(mute_role, reason="Auto-mod: spam detected")
                            await asyncio.sleep(duration * 60)
                            if mute_role in message.author.roles:
                                await message.author.remove_roles(mute_role)
                        await message.channel.send(f"🔇 {message.author.mention} was muted for {duration} minutes (spam)")
                    elif action == "warn":
                        await message.author.send(f"⚠️ Warning: You were warned for spamming in {message.guild.name}")
                        await message.channel.send(f"⚠️ {message.author.mention} was warned for spamming")
                    elif action == "kick":
                        await message.author.kick(reason="Spam")
                        await message.channel.send(f"👢 {message.author.mention} was kicked for spamming")
                    elif action == "ban":
                        await message.author.ban(reason="Spam")
                        await message.channel.send(f"🔨 {message.author.mention} was banned for spamming")
                except:
                    pass
                bot.user_messages[user_id] = []
                return

    # ----- AFK welcome back -----
    if user_id in bot.afk_users and not message.content.startswith('!'):
        info = bot.afk_users.pop(user_id)
        try:
            time_afk = (datetime.datetime.now() - datetime.datetime.fromisoformat(info["time"])).seconds // 60
            await message.channel.send(f"👋 Welcome back {message.author.mention}! You were AFK for {time_afk} minutes.")
            save_data()
            asyncio.create_task(async_save_warnings())
        except:
            pass

    # ----- AFK ping reply -----
    if message.mentions:
        for mentioned in message.mentions:
            mentioned_id = str(mentioned.id)
            if mentioned_id in bot.afk_users:
                afk_info = bot.afk_users[mentioned_id]
                reason = afk_info.get("reason", "No reason")
                time_afk = (datetime.datetime.now() - datetime.datetime.fromisoformat(afk_info["time"])).seconds // 60
                embed = discord.Embed(
                    title=f"🔕 {mentioned.display_name} is AFK",
                    description=f"**Reason:** {reason}\n**For:** {time_afk} minutes",
                    color=discord.Color.orange()
                )
                if mentioned.avatar:
                    embed.set_thumbnail(url=mentioned.avatar.url)
                await message.channel.send(embed=embed)
                break

    # ----- ADVANCED AUTO-MOD: Check rules -----
    rules = load_auto_rules()
    guild_rules = {k.split('|')[1]: v for k, v in rules.items() if k.startswith(guild_id)}
    if guild_rules:
        content_lower = message.content.lower()
        for word, rule in guild_rules.items():
            if word in content_lower:
                action = rule["action"]
                try:
                    if action == "delete":
                        await message.delete()
                        await message.author.send(f"⚠️ Your message in {message.guild.name} was deleted because it contained a banned word: `{word}`")
                    elif action == "warn":
                        await message.delete()
                        await message.author.send(f"⚠️ Warning: Your message in {message.guild.name} contained a banned word: `{word}`. Further violations may result in mute or ban.")
                        warnings_data = load_warning_counts()
                        key = f"{guild_id}|{message.author.id}|{word}"
                        warnings_data[key] = warnings_data.get(key, 0) + 1
                        save_warning_counts(warnings_data)
                    elif action == "mute":
                        await message.delete()
                        mute_role = discord.utils.get(message.guild.roles, name="Muted")
                        if not mute_role:
                            try:
                                mute_role = await message.guild.create_role(name="Muted", color=discord.Color.dark_gray())
                                for channel in message.guild.channels:
                                    await channel.set_permissions(mute_role, send_messages=False, speak=False)
                            except:
                                pass
                        if mute_role:
                            duration = rule.get("duration", 5)
                            await message.author.add_roles(mute_role, reason=f"Auto-mod: banned word '{word}'")
                            asyncio.create_task(auto_unmute(message.author, mute_role, message.guild, duration))
                        await message.author.send(f"⚠️ You have been muted for {duration} minutes in {message.guild.name} for using a banned word: `{word}`.")
                    elif action == "ban":
                        await message.delete()
                        await message.author.ban(reason=f"Auto-mod: banned word '{word}'")
                        try:
                            await message.author.send(f"⚠️ You have been banned from {message.guild.name} for using a banned word: `{word}`.")
                        except:
                            pass
                except discord.Forbidden:
                    print(f"Could not perform action {action} on {message.author.name}")
                except Exception as e:
                    print(f"Auto-mod error: {e}")
                break

    # ----- Quarantine check -----
    if guild_id in bot.quarantined_users and user_id in bot.quarantined_users[guild_id]:
        quarantine_info = bot.quarantined_users[guild_id][user_id]
        quarantine_channel_id = quarantine_info.get("channel_id")
        if str(message.channel.id) != str(quarantine_channel_id):
            try:
                await message.delete()
                await message.author.send("⚠️ You are quarantined! You can only talk in the quarantine channel.")
            except:
                pass
            return

    # ----- Country Guesser: listen for guesses -----
    game = active_games.get(message.channel.id)
    if game and game["active"] and not game["round_ended"]:
        guess = message.content.strip().lower()
        guess = re.sub(r'[^\w\s]', '', guess)
        correct_name = game["current_country"].lower()
        if guess == correct_name:
            uid = str(message.author.id)
            if uid in game["correct_this_round"]:
                return
            position = len(game["correct_this_round"]) + 1
            if position > 3:
                return
            game["correct_this_round"].append(uid)
            points = game["points_awarded"][position]
            old = game.get("game_scores", {}).get(uid, 0)
            if "game_scores" not in game:
                game["game_scores"] = {}
            game["game_scores"][uid] = old + points
            await message.channel.send(f"🎉 **{message.author.display_name}** guessed correctly! (+{points} points) [Position {position}]")
            if position == 3 or len(game["correct_this_round"]) >= 3:
                if game.get("timer_task"):
                    game["timer_task"].cancel()
                game["round_ended"] = True
                correct_name_full = game["current_country"]
                await message.channel.send(f"✅ Round ended. The correct answer was **{correct_name_full}**. Next flag in 5 seconds...")
                await asyncio.sleep(5)
                game["current_index"] += 1
                await next_round(message.channel)

    # ----- Custom responses -----
    if message.content.strip().lower() == "acknowledge me":
        if any(role.name == "Tribul Chief" for role in message.author.roles):
            await message.channel.send("I acknowledge you, my Tribul chief")

    if message.content.strip().lower() == "best staff in ford high":
        await message.channel.send("spider")
        
        



# ==================== LOAN FUNCTIONS ====================
LOANS_ADV_FILE = "loans_adv.json"

def load_loans_adv():
    try:
        with open(LOANS_ADV_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_loans_adv(data):
    with open(LOANS_ADV_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ==================== ON_MESSAGE_DELETE EVENT (UPDATED WITH LIMITS) ====================
@bot.event
async def on_message_delete(message):
    if message.author.bot:
        return
    if not hasattr(bot, 'snipe_messages'):
        bot.snipe_messages = {}

    channel_id = message.channel.id
    if channel_id not in bot.snipe_messages:
        bot.snipe_messages[channel_id] = []

    bot.snipe_messages[channel_id].append({
        "author": message.author,
        "content": message.content,
        "timestamp": datetime.datetime.now(),
        "deleted_by_automod": False
    })

    # Trim per-channel list
    if len(bot.snipe_messages[channel_id]) > MAX_SNIPE_MESSAGES_PER_CHANNEL:
        bot.snipe_messages[channel_id] = bot.snipe_messages[channel_id][-MAX_SNIPE_MESSAGES_PER_CHANNEL:]

    # Global safety trim
    total = sum(len(v) for v in bot.snipe_messages.values())
    if total > MAX_GLOBAL_SNIPES:
        channels = sorted(bot.snipe_messages.keys(), key=lambda c: len(bot.snipe_messages[c]), reverse=True)
        for ch in channels:
            if total <= MAX_GLOBAL_SNIPES:
                break
            excess = total - MAX_GLOBAL_SNIPES
            remove = min(len(bot.snipe_messages[ch]), excess)
            bot.snipe_messages[ch] = bot.snipe_messages[ch][remove:]
            total -= remove
            if not bot.snipe_messages[ch]:
                del bot.snipe_messages[ch]

# ==================== SNIPE COMMAND (UPDATED) ====================
@bot.command(name="s", aliases=["snipe"])
async def snipe_command(ctx):
    channel_id = ctx.channel.id
    if channel_id not in bot.snipe_messages or not bot.snipe_messages[channel_id]:
        return await ctx.send("❌ Nothing to snipe.", delete_after=5)

    data = bot.snipe_messages[channel_id][-1]
    embed = create_embed(f"🕵️ Snipe | #{ctx.channel.name}",
        f"**Author:** {data['author'].mention}\n**Content:** {data['content']}\n**Deleted at:** {data['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}",
        discord.Color.blue())
    if data.get('deleted_by_automod', False):
        embed.add_field(name="🤖 Auto-Mod", value=f"Deleted for banned word: `{data.get('banned_word', 'unknown')}`\nAction: `{data.get('action', 'delete')}`", inline=False)
        embed.color = discord.Color.red()
    await ctx.send(embed=embed)

# ==================== CLAN TAG PERSISTENCE ====================
@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    if before.display_name == after.display_name:
        return
    user_id = str(after.id)
    clan_id = None
    for cid, members in bot.clan_members.items():
        if user_id in members:
            clan_id = cid
            break
    if not clan_id:
        return
    clan = bot.clans.get(clan_id)
    if not clan:
        return
    await update_clan_nickname(after, clan["clan_name"])
    
    


# ==================== BASIC COMMANDS ====================
@bot.command(name="ping")
async def ping(ctx):
    latency = round(bot.latency * 1000)
    embed = create_embed("🏓 Pong!", f"**Latency:** {latency}ms\n**Status:** Online ✅\n**Host:** Render", discord.Color.green())
    await ctx.send(embed=embed)

@bot.command(name="afk")
async def afk(ctx, *, reason="No reason"):
    user_id = str(ctx.author.id)
    bot.afk_users[user_id] = {"reason": reason, "time": datetime.datetime.now().isoformat()}
    save_data()
    embed = create_embed("⏸️ AFK Set", f"{ctx.author.mention} is now AFK\n**Reason:** {reason}", discord.Color.blue())
    if ctx.author.avatar:
        embed.set_thumbnail(url=ctx.author.avatar.url)
    await ctx.send(embed=embed)

@bot.command(name="modlogs", aliases=["automodlogs"])
@commands.has_permissions(administrator=True)
async def modlogs(ctx, limit: int = 10):
    if not hasattr(bot, 'deleted_banned_messages'):
        bot.deleted_banned_messages = []
    guild_logs = [log for log in bot.deleted_banned_messages if log.get("guild_id") == str(ctx.guild.id)]
    guild_logs.reverse()
    top_logs = guild_logs[:min(limit, 25)]
    if not top_logs:
        return await ctx.send("📭 No auto-mod deletions recorded yet.")
    embed = create_embed("🤖 Auto-Mod Logs", f"Last {len(top_logs)} deleted messages", discord.Color.orange())
    for log in top_logs:
        timestamp = datetime.datetime.fromisoformat(log["timestamp"]).strftime("%H:%M:%S")
        embed.add_field(
            name=f"{timestamp} - {log['author']}",
            value=f"Word: `{log['banned_word']}`\nAction: `{log.get('action', 'delete')}`\nContent: {log['content'][:50]}...",
            inline=False
        )
    await ctx.send(embed=embed)

@bot.command(name="avatar", aliases=["av", "pfp"])
async def avatar(ctx, member: discord.Member = None):
    target = member or ctx.author
    embed = discord.Embed(title=f"{target.name}'s Avatar", color=discord.Color.blue())
    embed.set_image(url=target.avatar.url if target.avatar else target.default_avatar.url)
    embed.set_footer(text=f"Requested by {ctx.author.name}")
    await ctx.send(embed=embed)

# ==================== STAFF CHECK FUNCTION ====================
async def is_user_staff(ctx):
    if ctx.guild is None:
        return False
    if ctx.author.guild_permissions.administrator:
        return True
    staff_role_names = [
        "Admin", "Mod", "Sergeant", "President", "Director general", "Secretary general",
        "Vice President", "Chief of staff", "Prime Minister", "Co Founder", "Founder"
    ]
    return any(role.name in staff_role_names for role in ctx.author.roles)

# ==================== NICK COMMAND (STAFF ONLY) ====================
@bot.command(name="nick", aliases=["nickname", "rename"])
@commands.check(is_user_staff)
async def change_nickname(ctx, member: discord.Member, *, new_nick: str = None):
    if ctx.guild is None:
        return await ctx.send("❌ This command can only be used in a server.")
    if new_nick is None or new_nick.lower() == "reset":
        new_nick = member.name
    try:
        await member.edit(nick=new_nick, reason=f"Nickname changed by {ctx.author}")
        embed = create_embed("✅ Nickname Changed", f"{member.mention}'s nickname is now **{new_nick}**", discord.Color.green())
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to change that user's nickname.")

# ==================== LEGACY WORD MANAGEMENT ====================
@bot.command(name="addword", aliases=["addbannedword"])
@commands.check(is_user_staff)
async def add_banned_word(ctx, *, word: str):
    if ctx.guild is None:
        return await ctx.send("❌ This command can only be used in a server.")
    guild_id = str(ctx.guild.id)
    word_lower = word.lower().strip()
    rules = load_auto_rules()
    key = f"{guild_id}|{word_lower}"
    rules[key] = {"action": "delete", "duration": None, "threshold": None}
    save_auto_rules(rules)
    if guild_id not in bot.banned_words:
        bot.banned_words[guild_id] = []
    if word_lower not in bot.banned_words[guild_id]:
        bot.banned_words[guild_id].append(word_lower)
        save_banned_words()
    embed = create_embed("✅ Word Added", f"`{word}` has been added to auto-mod filter (action: delete).", discord.Color.green())
    await ctx.send(embed=embed)

@bot.command(name="removeword", aliases=["delword", "removebannedword"])
@commands.check(is_user_staff)
async def remove_banned_word(ctx, *, word: str):
    if ctx.guild is None:
        return await ctx.send("❌ This command can only be used in a server.")
    guild_id = str(ctx.guild.id)
    word_lower = word.lower().strip()
    rules = load_auto_rules()
    key = f"{guild_id}|{word_lower}"
    if key in rules:
        del rules[key]
        save_auto_rules(rules)
    if guild_id in bot.banned_words and word_lower in bot.banned_words[guild_id]:
        bot.banned_words[guild_id].remove(word_lower)
        if not bot.banned_words[guild_id]:
            del bot.banned_words[guild_id]
        save_banned_words()
    embed = create_embed("✅ Word Removed", f"`{word}` has been removed from the auto-mod filter.", discord.Color.green())
    await ctx.send(embed=embed)

@bot.command(name="wordlist", aliases=["bannedwords", "words"])
@commands.check(is_user_staff)
async def list_banned_words(ctx):
    if ctx.guild is None:
        return await ctx.send("❌ This command can only be used in a server.")
    guild_id = str(ctx.guild.id)
    rules = load_auto_rules()
    guild_rules = {k.split('|')[1]: v for k, v in rules.items() if k.startswith(guild_id)}
    if not guild_rules:
        return await ctx.send("📭 No auto-mod rules have been set for this server. Use `!setautomod` to add one.")
    embed = create_embed("🚫 Auto-Mod Rules", f"Total: {len(guild_rules)} rules", discord.Color.red())
    for word, rule in guild_rules.items():
        action = rule["action"]
        detail = ""
        if action == "mute":
            detail = f" ({rule['duration']} min mute)"
        elif action == "warn":
            detail = " (warning DM)"
        embed.add_field(name=word, value=f"{action}{detail}", inline=False)
    await ctx.send(embed=embed)

# ==================== ADVANCED AUTO-MOD RULES ====================
@bot.command(name="setautomod")
@commands.check(is_user_staff)
async def set_automod(ctx, word: str, action: str, param: int = None):
    if ctx.guild is None:
        return await ctx.send("❌ This command can only be used in a server.")
    action = action.lower()
    if action not in ["delete", "warn", "mute", "ban"]:
        return await ctx.send("❌ Action must be delete, warn, mute, or ban.")
    if action == "mute" and param is None:
        param = 5
    guild_id = str(ctx.guild.id)
    key = f"{guild_id}|{word.lower()}"
    rules = load_auto_rules()
    rules[key] = {"action": action, "duration": param if action == "mute" else None, "threshold": None}
    save_auto_rules(rules)
    if action == "delete":
        if guild_id not in bot.banned_words:
            bot.banned_words[guild_id] = []
        if word.lower() not in bot.banned_words[guild_id]:
            bot.banned_words[guild_id].append(word.lower())
            save_banned_words()
    await ctx.send(f"✅ Auto-mod rule set: `{word}` → `{action}`" + (f" for {param} minutes" if action == "mute" else ""))

@bot.command(name="removeautomod")
@commands.check(is_user_staff)
async def remove_automod(ctx, word: str):
    if ctx.guild is None:
        return await ctx.send("❌ This command can only be used in a server.")
    guild_id = str(ctx.guild.id)
    key = f"{guild_id}|{word.lower()}"
    rules = load_auto_rules()
    if key not in rules:
        return await ctx.send(f"❌ No rule found for `{word}`.")
    del rules[key]
    save_auto_rules(rules)
    if guild_id in bot.banned_words and word.lower() in bot.banned_words[guild_id]:
        bot.banned_words[guild_id].remove(word.lower())
        if not bot.banned_words[guild_id]:
            del bot.banned_words[guild_id]
        save_banned_words()
    await ctx.send(f"✅ Auto-mod rule for `{word}` removed.")

@bot.command(name="automodlist")
@commands.check(is_user_staff)
async def automod_list(ctx):
    await list_banned_words(ctx)

@bot.command(name="migrate_automod")
@commands.has_permissions(administrator=True)
async def migrate_automod_cmd(ctx):
    rules = load_auto_rules()
    migrated = 0
    for guild_id, words in bot.banned_words.items():
        for w in words:
            key = f"{guild_id}|{w.lower()}"
            if key not in rules:
                rules[key] = {"action": "delete", "duration": None, "threshold": None}
                migrated += 1
    save_auto_rules(rules)
    await ctx.send(f"✅ Migrated {migrated} old banned words to new auto-mod rules (all set to 'delete').")
    
    
    


# ==================== SPAM CONFIGURATION COMMANDS ====================
@bot.command(name="setspam")
@commands.check(is_user_staff)
async def set_spam_config(ctx, setting: str, value: str):
    """Configure spam detection: threshold, timeframe, action, duration"""
    config = bot.spam_config
    if setting == "enabled":
        config["enabled"] = value.lower() == "true"
    elif setting == "threshold":
        config["threshold"] = int(value)
    elif setting == "timeframe":
        config["timeframe"] = int(value)
    elif setting == "action":
        if value.lower() not in ["mute", "warn", "kick", "ban"]:
            return await ctx.send("❌ Action must be: mute, warn, kick, ban")
        config["action"] = value.lower()
    elif setting == "duration":
        config["duration"] = int(value)
    else:
        return await ctx.send("❌ Settings: enabled, threshold, timeframe, action, duration")
    save_spam_config(config)
    await ctx.send(f"✅ Spam config updated: `{setting}` = `{value}`")

@bot.command(name="spamconfig")
@commands.check(is_user_staff)
async def show_spam_config(ctx):
    """Show current spam detection configuration"""
    config = bot.spam_config
    embed = discord.Embed(title="🛡️ Spam Detection Config", color=discord.Color.blue())
    embed.add_field(name="Enabled", value=str(config.get("enabled", False)), inline=True)
    embed.add_field(name="Threshold", value=f"{config.get('threshold', 3)} messages", inline=True)
    embed.add_field(name="Timeframe", value=f"{config.get('timeframe', 5)} seconds", inline=True)
    embed.add_field(name="Action", value=config.get("action", "mute"), inline=True)
    embed.add_field(name="Duration", value=f"{config.get('duration', 5)} minutes", inline=True)
    await ctx.send(embed=embed)

# ==================== MODERATION COMMANDS ====================
def can_moderate(moderator: discord.Member, target: discord.Member) -> bool:
    if moderator == target:
        return False
    if moderator.guild_permissions.administrator:
        return True
    return moderator.top_role.position > target.top_role.position

@bot.command(name="mute")
@commands.has_permissions(manage_messages=True)
async def mute(ctx, member: discord.Member, duration: str = "10m", *, reason="No reason"):
    """Mute a user. Duration formats: 5s, 5m, 5h"""
    if not can_moderate(ctx.author, member):
        return await ctx.send("❌ You cannot moderate a user with a higher or equal role.")
    if member.guild_permissions.administrator:
        return await ctx.send("❌ Cannot mute an administrator.")
    
    seconds = parse_duration(duration)
    if seconds <= 0:
        return await ctx.send("❌ Invalid duration. Use formats like: 5s, 5m, 5h")
    minutes = seconds / 60
    
    mute_role = discord.utils.get(ctx.guild.roles, name="Muted")
    if not mute_role:
        try:
            mute_role = await ctx.guild.create_role(name="Muted", color=discord.Color.dark_gray(), reason="Mute role for bot")
            for channel in ctx.guild.channels:
                try:
                    await channel.set_permissions(mute_role, send_messages=False, speak=False, add_reactions=False)
                except:
                    pass
        except discord.Forbidden:
            return await ctx.send("❌ I don't have permission to create roles.")
    await member.add_roles(mute_role, reason=f"Muted by {ctx.author}: {reason}")
    unmute_time = datetime.datetime.now() + datetime.timedelta(minutes=minutes)
    bot.muted_users[str(member.id)] = {"unmute_at": unmute_time.isoformat(), "reason": reason, "guild_id": ctx.guild.id}
    save_data()
    embed = create_embed("🔇 User Muted", f"**User:** {member.mention}\n**Duration:** {duration}\n**Reason:** {reason}\n**Until:** {unmute_time.strftime('%H:%M:%S')}", discord.Color.orange())
    await ctx.send(embed=embed)
    async def auto_unmute():
        await asyncio.sleep(minutes * 60)
        if str(member.id) in bot.muted_users:
            try:
                if mute_role in member.roles:
                    await member.remove_roles(mute_role)
                    del bot.muted_users[str(member.id)]
                    save_data()
                    await ctx.send(f"🔊 {member.mention} has been automatically unmuted.", delete_after=10)
            except:
                pass
    asyncio.create_task(auto_unmute())

@bot.command(name="um")
@commands.has_permissions(manage_messages=True)
async def unmute(ctx, member: discord.Member):
    mute_role = discord.utils.get(ctx.guild.roles, name="Muted")
    if not mute_role or mute_role not in member.roles:
        return await ctx.send("❌ This user is not muted.")
    await member.remove_roles(mute_role)
    if str(member.id) in bot.muted_users:
        del bot.muted_users[str(member.id)]
        save_data()
    embed = create_embed("🔊 User Unmuted", f"{member.mention} has been unmuted by {ctx.author.mention}", discord.Color.green())
    await ctx.send(embed=embed)

@bot.command(name="k")
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason="No reason"):
    if not can_moderate(ctx.author, member):
        return await ctx.send("❌ You cannot kick a user with a higher or equal role.")
    if member.guild_permissions.administrator:
        return await ctx.send("❌ Cannot kick an administrator.")
    mod_stats_file = "mod_action_stats.json"
    try:
        with open(mod_stats_file, "r") as f:
            stats = json.load(f)
    except:
        stats = {}
    guild_id = str(ctx.guild.id)
    actor_id = str(ctx.author.id)
    if guild_id not in stats:
        stats[guild_id] = {}
    if actor_id not in stats[guild_id]:
        stats[guild_id][actor_id] = {"kicks": 0, "bans": 0}
    stats[guild_id][actor_id]["kicks"] = stats[guild_id][actor_id].get("kicks", 0) + 1
    with open(mod_stats_file, "w") as f:
        json.dump(stats, f, indent=2)
    try:
        await member.kick(reason=f"{ctx.author}: {reason}")
        embed = create_embed("👢 User Kicked", f"**User:** {member.mention}\n**Reason:** {reason}\n**By:** {ctx.author.mention}", discord.Color.orange())
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to kick this user.")

@bot.command(name="b")
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason="No reason"):
    if not can_moderate(ctx.author, member):
        return await ctx.send("❌ You cannot ban a user with a higher or equal role.")
    if member.guild_permissions.administrator:
        return await ctx.send("❌ Cannot ban an administrator.")
    mod_stats_file = "mod_action_stats.json"
    try:
        with open(mod_stats_file, "r") as f:
            stats = json.load(f)
    except:
        stats = {}
    guild_id = str(ctx.guild.id)
    actor_id = str(ctx.author.id)
    if guild_id not in stats:
        stats[guild_id] = {}
    if actor_id not in stats[guild_id]:
        stats[guild_id][actor_id] = {"kicks": 0, "bans": 0}
    stats[guild_id][actor_id]["bans"] = stats[guild_id][actor_id].get("bans", 0) + 1
    with open(mod_stats_file, "w") as f:
        json.dump(stats, f, indent=2)
    try:
        await member.ban(reason=f"{ctx.author}: {reason}")
        embed = create_embed("🔨 User Banned", f"**User:** {member.mention}\n**Reason:** {reason}\n**By:** {ctx.author.mention}", discord.Color.red())
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to ban this user.")

@bot.command(name="clear", aliases=["purge"])
@commands.has_permissions(manage_messages=True)
async def clear(ctx, amount: int = 10):
    if amount < 1 or amount > 100:
        return await ctx.send("❌ Amount must be between 1 and 100.", delete_after=5)
    try:
        deleted = await ctx.channel.purge(limit=amount + 1)
        embed = create_embed("🧹 Messages Cleared", f"Cleared **{len(deleted)-1}** messages", discord.Color.green())
        msg = await ctx.send(embed=embed)
        await asyncio.sleep(3)
        await msg.delete()
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to delete messages.", delete_after=5)

@bot.command(name="warn")
@commands.has_permissions(manage_messages=True)
async def warn(ctx, member: discord.Member, *, reason="No reason"):
    if member.guild_permissions.administrator:
        return await ctx.send("❌ Cannot warn an administrator.")
    user_id = str(member.id)
    guild_id = str(ctx.guild.id)
    if guild_id not in bot.warnings:
        bot.warnings[guild_id] = {}
    bot.warnings[guild_id][user_id] = bot.warnings[guild_id].get(user_id, 0) + 1
    save_data()
    asyncio.create_task(async_save_warnings())
    embed = create_embed("⚠️ User Warned", f"**User:** {member.mention}\n**Reason:** {reason}\n**Total Warnings:** {bot.warnings[guild_id][user_id]}\n**By:** {ctx.author.mention}", discord.Color.orange())
    await ctx.send(embed=embed)

@bot.command(name="warnings")
async def warnings(ctx, member: discord.Member = None):
    target = member or ctx.author
    user_id = str(target.id)
    guild_id = str(ctx.guild.id)
    count = bot.warnings.get(guild_id, {}).get(user_id, 0)
    embed = create_embed(f"📊 Warnings for {target.name}", f"**Total Warnings:** {count}\n**User:** {target.mention}", discord.Color.blue() if count == 0 else discord.Color.orange() if count < 3 else discord.Color.red())
    await ctx.send(embed=embed)
    
    


# ==================== ECONOMY COMMANDS ====================
@bot.command(name="balance", aliases=["bal", "money"])
async def balance(ctx, member: discord.Member = None):
    target = member or ctx.author
    user_id = str(target.id)
    wallet = bot.wallets.get(user_id, 0)
    bank = bot.banks.get(user_id, 0)
    total = wallet + bank
    embed = create_embed(f"💰 {target.name}'s Balance", f"**Wallet:** {format_money(wallet)}\n**Bank:** {format_money(bank)}\n**Total:** {format_money(total)}", discord.Color.gold())
    if member:
        embed.set_footer(text=f"Requested by {ctx.author.name}")
    await ctx.send(embed=embed)

@bot.command(name="daily")
async def daily(ctx):
    user_id = str(ctx.author.id)
    last_claim = bot.last_daily.get(user_id)
    if last_claim:
        last_time = datetime.datetime.fromisoformat(last_claim)
        if (datetime.datetime.now() - last_time).total_seconds() < 86400:
            hours_left = 23 - int((datetime.datetime.now() - last_time).seconds // 3600)
            minutes_left = 59 - int(((datetime.datetime.now() - last_time).seconds % 3600) // 60)
            return await ctx.send(f"⏳ Already claimed! Come back in **{hours_left}h {minutes_left}m**")
    amount = 10000
    bot.wallets[user_id] = bot.wallets.get(user_id, 0) + amount
    bot.last_daily[user_id] = datetime.datetime.now().isoformat()
    save_economy()
    asyncio.create_task(async_save_economy())
    embed = create_embed("💰 Daily Reward Claimed!", f"You claimed **{format_money(amount)}**!\n**New Balance:** {format_money(bot.wallets[user_id])}", discord.Color.green())
    await ctx.send(embed=embed)

@bot.command(name="work")
async def work(ctx):
    user_id = str(ctx.author.id)
    last_work = bot.last_work.get(user_id)
    if last_work:
        last_time = datetime.datetime.fromisoformat(last_work)
        if (datetime.datetime.now() - last_time).total_seconds() < 3600:
            minutes_left = 59 - int(((datetime.datetime.now() - last_time).seconds % 3600) // 60)
            seconds_left = 59 - ((datetime.datetime.now() - last_time).seconds % 60)
            return await ctx.send(f"⏳ Work again in **{minutes_left}m {seconds_left}s**")
    amount = random.randint(5000, 20000)
    bot.wallets[user_id] = bot.wallets.get(user_id, 0) + amount
    bot.last_work[user_id] = datetime.datetime.now().isoformat()
    save_economy()
    asyncio.create_task(async_save_economy())
    jobs = ["worked at a coffee shop ☕", "fixed some computers 💻", "delivered packages 📦", "did freelance work 💼", "worked as a cashier 🏪", "did gardening 🌱", "fixed cars 🚗", "did construction 🏗️"]
    job = random.choice(jobs)
    embed = create_embed("💼 Work Complete!", f"You {job} and earned **{format_money(amount)}**!\n**New Balance:** {format_money(bot.wallets[user_id])}", discord.Color.green())
    await ctx.send(embed=embed)

@bot.command(name="deposit", aliases=["dep"])
async def deposit(ctx, amount: str):
    user_id = str(ctx.author.id)
    wallet = bot.wallets.get(user_id, 0)
    if amount.lower() == "all":
        amount_num = wallet
    else:
        try:
            amount_num = parse_money_amount(amount)
            if amount_num <= 0:
                return await ctx.send("❌ Amount must be positive!")
        except:
            return await ctx.send("❌ Invalid amount! Use a number, 'all', or shorthand like 5m (million), 5b (billion), 5t (trillion).")
    if wallet < amount_num:
        return await ctx.send(f"❌ You only have {format_money(wallet)}!")
    bot.wallets[user_id] -= amount_num
    bot.banks[user_id] = bot.banks.get(user_id, 0) + amount_num
    save_economy()
    asyncio.create_task(async_save_economy())
    embed = create_embed("🏦 Deposit Successful", f"Deposited **{format_money(amount_num)}**\n**Wallet:** {format_money(bot.wallets[user_id])}\n**Bank:** {format_money(bot.banks[user_id])}", discord.Color.green())
    await ctx.send(embed=embed)

@bot.command(name="withdraw", aliases=["with"])
async def withdraw(ctx, amount: str):
    user_id = str(ctx.author.id)
    bank = bot.banks.get(user_id, 0)
    if amount.lower() == "all":
        amount_num = bank
    else:
        try:
            amount_num = parse_money_amount(amount)
            if amount_num <= 0:
                return await ctx.send("❌ Amount must be positive!")
        except:
            return await ctx.send("❌ Invalid amount! Use a number, 'all', or shorthand like 5m (million), 5b (billion), 5t (trillion).")
    if bank < amount_num:
        return await ctx.send(f"❌ You only have {format_money(bank)} in bank!")
    bot.banks[user_id] -= amount_num
    bot.wallets[user_id] = bot.wallets.get(user_id, 0) + amount_num
    save_economy()
    asyncio.create_task(async_save_economy())
    embed = create_embed("💵 Withdrawal Successful", f"Withdrew **{format_money(amount_num)}**\n**Wallet:** {format_money(bot.wallets[user_id])}\n**Bank:** {format_money(bot.banks[user_id])}", discord.Color.green())
    await ctx.send(embed=embed)

@bot.command(name="transfer", aliases=["pay"])
async def transfer(ctx, member: discord.Member, amount: str):
    try:
        amount_num = parse_money_amount(amount)
    except:
        return await ctx.send("❌ Invalid amount! Use a number or shorthand like 5m (million), 5b (billion), 5t (trillion).")
    if amount_num <= 0:
        return await ctx.send("❌ Amount must be positive!")
    if member.id == ctx.author.id:
        return await ctx.send("❌ You can't transfer to yourself!")
    if member.bot:
        return await ctx.send("❌ You can't transfer to bots!")
    sender_id = str(ctx.author.id)
    receiver_id = str(member.id)
    sender_wallet = bot.wallets.get(sender_id, 0)
    if sender_wallet < amount_num:
        return await ctx.send(f"❌ You only have {format_money(sender_wallet)}!")
    tax = int(amount_num * 0.02)
    transfer_amount = amount_num - tax
    bot.wallets[sender_id] -= amount_num
    bot.wallets[receiver_id] = bot.wallets.get(receiver_id, 0) + transfer_amount
    save_economy()
    asyncio.create_task(async_save_economy())
    embed = create_embed("💸 Transfer Successful", f"**From:** {ctx.author.mention}\n**To:** {member.mention}\n**Amount:** {format_money(transfer_amount)}\n**Tax (2%):** {format_money(tax)}\n**Total Sent:** {format_money(amount_num)}\n**Your Balance:** {format_money(bot.wallets[sender_id])}", discord.Color.green())
    await ctx.send(embed=embed)

@bot.command(name="rich", aliases=["richest", "leaderboard", "lb"])
async def rich(ctx):
    guild_members = [m for m in ctx.guild.members if not m.bot]
    totals = []
    for member in guild_members:
        uid = str(member.id)
        wallet = bot.wallets.get(uid, 0)
        bank = bot.banks.get(uid, 0)
        total = wallet + bank
        totals.append((member, total))
    totals.sort(key=lambda x: x[1], reverse=True)
    top10 = totals[:10]
    embed = create_embed(f"🏆 Richest Members in {ctx.guild.name}", "", discord.Color.gold())
    if not top10:
        embed.description = "No economy data found."
    else:
        medals = ["🥇", "🥈", "🥉"]
        for i, (member, total) in enumerate(top10, 1):
            if i <= 3:
                prefix = medals[i-1]
            else:
                prefix = f"{i}."
            embed.add_field(name=f"{prefix} {member.display_name}", value=f"💲 {format_money(total)}", inline=False)
    await ctx.send(embed=embed)
    
    


# ==================== GAMBLING COMMANDS ====================
@bot.command(name="gamble")
async def gamble(ctx, amount: str):
    try:
        amount_num = parse_money_amount(amount)
    except:
        return await ctx.send("❌ Invalid amount! Use a number or shorthand like 5m (million), 5b (billion), 5t (trillion).")
    if amount_num <= 0:
        return await ctx.send("❌ Amount must be positive!")
    user_id = str(ctx.author.id)
    wallet = bot.wallets.get(user_id, 0)
    if wallet < amount_num:
        return await ctx.send(f"❌ You only have {format_money(wallet)}!")
    if random.random() < 0.45:
        win_amount = int(amount_num * 1.5)
        bot.wallets[user_id] = wallet + win_amount
        result, color, profit = f"🎰 You won {format_money(win_amount)}!", discord.Color.green(), win_amount - amount_num
    else:
        bot.wallets[user_id] = wallet - amount_num
        result, color, profit = f"🎰 You lost {format_money(amount_num)}.", discord.Color.red(), -amount_num
    save_economy()
    asyncio.create_task(async_save_economy())
    embed = create_embed("🎲 Gambling", f"{result}\n**Profit/Loss:** {format_money(profit)}\n**New Balance:** {format_money(bot.wallets[user_id])}\n**Chance:** 45% win 1.5x", color)
    await ctx.send(embed=embed)

@bot.command(name="coinflip", aliases=["cf", "flip"])
async def coinflip(ctx, choice: str, amount: str):
    choice = choice.lower()
    if choice in ["h", "head", "heads"]:
        user_choice = "heads"
    elif choice in ["t", "tail", "tails"]:
        user_choice = "tails"
    else:
        return await ctx.send("❌ Choose `heads` or `tails`.")
    try:
        amount_num = parse_money_amount(amount)
    except:
        return await ctx.send("❌ Invalid amount! Use a number or shorthand like 5m (million), 5b (billion), 5t (trillion).")
    if amount_num <= 0:
        return await ctx.send("❌ Amount must be positive!")
    user_id = str(ctx.author.id)
    wallet = bot.wallets.get(user_id, 0)
    if wallet < amount_num:
        return await ctx.send(f"❌ You need {format_money(amount_num)}!")
    result = random.choice(["heads", "tails"])
    win = user_choice == result
    embed = create_embed("🪙 Coin Flip!", f"**Bet:** {format_money(amount_num)} on {user_choice}\n**Flipping...**", discord.Color.blue())
    msg = await ctx.send(embed=embed)
    await asyncio.sleep(1.5)
    if win:
        win_amount = amount_num * 2
        bot.wallets[user_id] = wallet + win_amount
        result_text = f"**It's {result}! You won {format_money(win_amount)}!**"
        color, profit = discord.Color.green(), win_amount - amount_num
    else:
        bot.wallets[user_id] = wallet - amount_num
        result_text = f"**It's {result}! You lost {format_money(amount_num)}.**"
        color, profit = discord.Color.red(), -amount_num
    save_economy()
    asyncio.create_task(async_save_economy())
    embed = create_embed("🎉 You Win!" if win else "💸 You Lose", f"{result_text}\n\n**Choice:** {user_choice}\n**Result:** {result}\n**Profit/Loss:** {format_money(profit)}\n**New Balance:** {format_money(bot.wallets[user_id])}", color)
    await msg.edit(embed=embed)

@bot.command(name="numbers", aliases=["guessnumbers"])
async def guess_numbers(ctx, amount: str, num1: int, num2: int):
    try:
        amount_num = parse_money_amount(amount)
    except:
        return await ctx.send("❌ Invalid amount! Use a number or shorthand like 5m (million), 5b (billion), 5t (trillion).")
    if amount_num <= 0:
        return await ctx.send("❌ Amount must be positive!")
    if not (1 <= num1 <= 10 and 1 <= num2 <= 10):
        return await ctx.send("❌ Numbers must be between 1 and 10.")
    user_id = str(ctx.author.id)
    wallet = bot.wallets.get(user_id, 0)
    if wallet < amount_num:
        return await ctx.send(f"❌ You only have {format_money(wallet)}!")
    draw1, draw2 = random.randint(1, 10), random.randint(1, 10)
    matches = 0
    if num1 == draw1 or num1 == draw2:
        matches += 1
    if num2 == draw1 or num2 == draw2:
        matches += 1
    if num1 == num2 and matches == 2 and draw1 == draw2:
        matches = 1
    if matches == 2:
        win_amount = amount_num * 2
        bot.wallets[user_id] = wallet + win_amount
        result, color, profit = f"🎉 Both match! Won {format_money(win_amount)}!", discord.Color.green(), win_amount - amount_num
    elif matches == 1:
        win_amount = int(amount_num * 0.5)
        bot.wallets[user_id] = wallet + win_amount
        result, color, profit = f"👍 One match! Won {format_money(win_amount)}.", discord.Color.blue(), win_amount - amount_num
    else:
        bot.wallets[user_id] = wallet - amount_num
        result, color, profit = f"💔 No matches! Lost {format_money(amount_num)}.", discord.Color.red(), -amount_num
    save_economy()
    asyncio.create_task(async_save_economy())
    embed = create_embed("🎲 Number Guess", f"**Your numbers:** {num1}, {num2}\n**Drawn:** {draw1}, {draw2}\n{result}\n**Profit/Loss:** {format_money(profit)}\n**New Balance:** {format_money(bot.wallets[user_id])}", color)
    await ctx.send(embed=embed)

@bot.command(name="horserace")
async def horserace(ctx, amount: str, horse: int):
    try:
        amount_num = parse_money_amount(amount)
    except:
        return await ctx.send("❌ Invalid amount! Use a number or shorthand like 5m (million), 5b (billion), 5t (trillion).")
    if amount_num <= 0:
        return await ctx.send("❌ Amount must be positive!")
    if not (1 <= horse <= 4):
        return await ctx.send("❌ Choose horse 1-4.")
    user_id = str(ctx.author.id)
    wallet = bot.wallets.get(user_id, 0)
    if wallet < amount_num:
        return await ctx.send(f"❌ You only have {format_money(wallet)}!")
    winner = random.randint(1, 4)
    if horse == winner:
        win_amount = amount_num * 3
        bot.wallets[user_id] = wallet + win_amount
        result, color, profit = f"🏆 Your horse won! +{format_money(win_amount)}", discord.Color.green(), win_amount - amount_num
    else:
        bot.wallets[user_id] = wallet - amount_num
        result, color, profit = f"🐎 Your horse lost. Winner was #{winner}. Lost {format_money(amount_num)}", discord.Color.red(), -amount_num
    save_economy()
    asyncio.create_task(async_save_economy())
    embed = create_embed("🏇 Horse Race", f"**Bet:** {format_money(amount_num)} on horse #{horse}\n**Winner:** #{winner}\n{result}\n**Profit/Loss:** {format_money(profit)}\n**New Balance:** {format_money(bot.wallets[user_id])}", color)
    await ctx.send(embed=embed)

@bot.command(name="dice")
async def dice(ctx, amount: str, guess: int):
    try:
        amount_num = parse_money_amount(amount)
    except:
        return await ctx.send("❌ Invalid amount! Use a number or shorthand like 5m (million), 5b (billion), 5t (trillion).")
    if amount_num <= 0:
        return await ctx.send("❌ Amount must be positive!")
    if not (1 <= guess <= 6):
        return await ctx.send("❌ Guess must be 1-6.")
    user_id = str(ctx.author.id)
    wallet = bot.wallets.get(user_id, 0)
    if wallet < amount_num:
        return await ctx.send(f"❌ You only have {format_money(wallet)}!")
    roll = random.randint(1, 6)
    if guess == roll:
        win_amount = amount_num * 5
        bot.wallets[user_id] = wallet + win_amount
        result, color, profit = f"🎲 Correct! Won {format_money(win_amount)}", discord.Color.green(), win_amount - amount_num
    else:
        bot.wallets[user_id] = wallet - amount_num
        result, color, profit = f"🎲 Wrong! Rolled {roll}. Lost {format_money(amount_num)}", discord.Color.red(), -amount_num
    save_economy()
    asyncio.create_task(async_save_economy())
    embed = create_embed("🎲 Dice Roll", f"**Bet:** {format_money(amount_num)} on {guess}\n**Roll:** {roll}\n{result}\n**Profit/Loss:** {format_money(profit)}\n**New Balance:** {format_money(bot.wallets[user_id])}", color)
    await ctx.send(embed=embed)

# ==================== BUSINESS COMMANDS ====================
@bot.command(name="createbusiness", aliases=["startbusiness"])
async def createbusiness(ctx, business_type: str, business_name: str, investment: str):
    user_id = str(ctx.author.id)
    wallet = bot.wallets.get(user_id, 0)
    
    try:
        investment_num = parse_money_amount(investment)
    except:
        return await ctx.send("❌ Invalid investment amount! Use a number or shorthand like 5m (million), 5b (billion), 5t (trillion).")
    
    if investment_num < 10000:
        embed = create_embed(
            "❌ Investment Too Low",
            "Minimum investment is $10,000!\nBusiness types and their minimum investments:\n• Cafe: $10,000\n• Shop: $20,000\n• Factory: $50,000\n• Farm: $30,000\n• Tech: $100,000\n• Restaurant: $40,000",
            discord.Color.red()
        )
        await ctx.send(embed=embed)
        return
    if wallet < investment_num:
        embed = create_embed(
            "❌ Insufficient Funds",
            f"You need {format_money(investment_num)} but only have {format_money(wallet)}!",
            discord.Color.red()
        )
        await ctx.send(embed=embed)
        return
    if user_id in bot.businesses:
        embed = create_embed("❌ Business Limit", "You already own a business! You can only own one business at a time.", discord.Color.red())
        await ctx.send(embed=embed)
        return
    business_type = business_type.lower()
    valid_types = {
        "cafe": {"min": 10000, "profit": 0.15, "emoji": "☕"},
        "shop": {"min": 20000, "profit": 0.20, "emoji": "🛍️"},
        "factory": {"min": 50000, "profit": 0.25, "emoji": "🏭"},
        "farm": {"min": 30000, "profit": 0.18, "emoji": "🚜"},
        "tech": {"min": 100000, "profit": 0.30, "emoji": "💻"},
        "restaurant": {"min": 40000, "profit": 0.22, "emoji": "🍽️"}
    }
    if business_type not in valid_types:
        embed = create_embed(
            "❌ Invalid Business Type",
            f"Available types: {', '.join(valid_types.keys())}\nExample: `!createbusiness cafe \"Coffee Corner\" 50000`",
            discord.Color.red()
        )
        await ctx.send(embed=embed)
        return
    type_info = valid_types[business_type]
    if investment_num < type_info["min"]:
        embed = create_embed(
            "❌ Investment Too Low",
            f"Minimum investment for {business_type} is {format_money(type_info['min'])}!",
            discord.Color.red()
        )
        await ctx.send(embed=embed)
        return
    bot.businesses[user_id] = {
        "name": business_name,
        "type": business_type,
        "investment": investment_num,
        "profit_rate": type_info["profit"],
        "created_at": datetime.datetime.now().isoformat(),
        "last_profit": None,
        "total_profit": 0,
        "level": 1,
        "emoji": type_info["emoji"]
    }
    bot.wallets[user_id] = wallet - investment_num
    save_economy()
    asyncio.create_task(async_save_economy())
    save_businesses()
    daily_profit = int(investment_num * type_info["profit"])
    embed = create_embed(
        f"🏢 Business Created! {type_info['emoji']}",
        f"**Business Name:** {business_name}\n**Type:** {business_type.title()}\n**Investment:** {format_money(investment_num)}\n**Daily Profit:** {format_money(daily_profit)}\n**Profit Rate:** {type_info['profit']*100}%\n**Level:** 1\n\nYour business will generate profits every 24 hours!\nUse `!mybusiness` to check your business status.",
        discord.Color.green()
    )
    await ctx.send(embed=embed)

@bot.command(name="mybusiness", aliases=["business", "mybiz"])
async def mybusiness(ctx):
    user_id = str(ctx.author.id)
    if user_id not in bot.businesses:
        embed = create_embed(
            "🏢 No Business",
            "You don't own a business yet!\nStart one with `!createbusiness <type> <name> <investment>`\n\n**Available Types:**\n• `cafe` - Coffee shop (min: $10,000)\n• `shop` - Retail store (min: $20,000)\n• `factory` - Manufacturing (min: $50,000)\n• `farm` - Agriculture (min: $30,000)\n• `tech` - Technology (min: $100,000)\n• `restaurant` - Food service (min: $40,000)",
            discord.Color.blue()
        )
        await ctx.send(embed=embed)
        return
    business = bot.businesses[user_id]
    last_profit_text = "Never"
    if business["last_profit"]:
        last_time = datetime.datetime.fromisoformat(business["last_profit"])
        time_since = datetime.datetime.now() - last_time
        hours_since = int(time_since.total_seconds() // 3600)
        last_profit_text = f"{hours_since} hours ago"
    daily_profit = int(business["investment"] * business["profit_rate"])
    next_profit_in = 24 - (datetime.datetime.now().hour % 24)
    embed = create_embed(
        f"{business['emoji']} {business['name']}",
        f"**Type:** {business['type'].title()}\n**Level:** {business['level']}\n**Investment:** {format_money(business['investment'])}\n**Daily Profit:** {format_money(daily_profit)}\n**Total Profits:** {format_money(business['total_profit'])}\n**Last Profit:** {last_profit_text}\n**Next Profit In:** ~{next_profit_in} hours\n\n**Commands:**\n• `!upgradebusiness` - Upgrade your business\n• `!collectprofit` - Collect your profits\n• `!closebusiness` - Close your business\n• `!invest <amount>` - Invest more money",
        discord.Color.gold()
    )
    await ctx.send(embed=embed)
    
    


@bot.command(name="collectprofit")
async def collectprofit(ctx):
    user_id = str(ctx.author.id)
    if user_id not in bot.businesses:
        embed = create_embed("❌ No Business", "You don't own a business!", discord.Color.red())
        await ctx.send(embed=embed)
        return
    
    business = bot.businesses[user_id]
    
    # Check cooldown
    if business.get("last_profit"):
        last_time = datetime.datetime.fromisoformat(business["last_profit"])
        time_since = datetime.datetime.now() - last_time
        if time_since.total_seconds() < 86400:
            hours_left = 23 - int(time_since.seconds // 3600)
            minutes_left = 59 - int((time_since.seconds % 3600) // 60)
            embed = create_embed(
                "⏳ Profit Not Ready",
                f"Your business needs more time to generate profits!\nCome back in **{hours_left}h {minutes_left}m**",
                discord.Color.orange()
            )
            await ctx.send(embed=embed)
            return
    
    daily_profit = int(business["investment"] * business["profit_rate"])
    business["total_profit"] += daily_profit
    business["last_profit"] = datetime.datetime.now().isoformat()
    save_businesses()
    
    # DISTRIBUTE PROFIT TO SHAREHOLDERS
    shares_data = bot.shares["businesses"].get(user_id, {"total_shares": 100, "shares": {user_id: 100}})
    total_shares = shares_data.get("total_shares", 100)
    share_dict = shares_data.get("shares", {user_id: total_shares})
    
    distributed = {}
    for shareholder_id, share_count in share_dict.items():
        if share_count > 0:
            cut = int(daily_profit * share_count / total_shares)
            if cut > 0:
                bot.wallets[shareholder_id] = bot.wallets.get(shareholder_id, 0) + cut
                distributed[shareholder_id] = cut
    
    save_economy()
    asyncio.create_task(async_save_economy())
    save_shares()
    
    description = (
        f"**Business:** {business['name']}\n"
        f"**Daily Profit:** {format_money(daily_profit)}\n"
        f"**Distributed among shareholders:**\n"
    )
    for uid, amt in distributed.items():
        try:
            user = await bot.fetch_user(int(uid))
            name = user.display_name
        except:
            name = f"<@{uid}>"
        description += f"• {name}: {format_money(amt)}\n"
    
    embed = create_embed(
        f"💰 Profit Collected! {business['emoji']}",
        description,
        discord.Color.green()
    )
    await ctx.send(embed=embed)

@bot.command(name="upgradebusiness")
async def upgradebusiness(ctx):
    user_id = str(ctx.author.id)
    if user_id not in bot.businesses:
        embed = create_embed("❌ No Business", "You don't own a business!", discord.Color.red())
        await ctx.send(embed=embed)
        return
    business = bot.businesses[user_id]
    current_level = business["level"]
    if current_level >= 10:
        embed = create_embed("❌ Max Level", "Your business is already at maximum level!", discord.Color.red())
        await ctx.send(embed=embed)
        return
    upgrade_cost = business["investment"] * 0.5
    wallet = bot.wallets.get(user_id, 0)
    if wallet < upgrade_cost:
        embed = create_embed(
            "❌ Insufficient Funds",
            f"Upgrade costs {format_money(int(upgrade_cost))} but you only have {format_money(wallet)}!",
            discord.Color.red()
        )
        await ctx.send(embed=embed)
        return
    business["level"] += 1
    business["investment"] += int(upgrade_cost)
    business["profit_rate"] += 0.02
    bot.wallets[user_id] = wallet - int(upgrade_cost)
    save_economy()
    asyncio.create_task(async_save_economy())
    save_businesses()
    new_daily_profit = int(business["investment"] * business["profit_rate"])
    embed = create_embed(
        f"⬆️ Business Upgraded! {business['emoji']}",
        f"**Business:** {business['name']}\n**New Level:** {business['level']}\n**New Investment:** {format_money(business['investment'])}\n**New Daily Profit:** {format_money(new_daily_profit)}\n**Upgrade Cost:** {format_money(int(upgrade_cost))}\n\nYour business is now more profitable!",
        discord.Color.green()
    )
    await ctx.send(embed=embed)

@bot.command(name="closebusiness")
async def closebusiness(ctx):
    user_id = str(ctx.author.id)
    if user_id not in bot.businesses:
        embed = create_embed("❌ No Business", "You don't own a business!", discord.Color.red())
        await ctx.send(embed=embed)
        return
    business = bot.businesses[user_id]
    refund = business["investment"] // 2
    bot.wallets[user_id] = bot.wallets.get(user_id, 0) + refund
    del bot.businesses[user_id]
    save_economy()
    asyncio.create_task(async_save_economy())
    save_businesses()
    embed = create_embed(
        f"🏢 Business Closed",
        f"**Business:** {business['name']}\n**Refund Received:** {format_money(refund)}\n**Total Profits Made:** {format_money(business['total_profit'])}\n**New Balance:** {format_money(bot.wallets[user_id])}\n\nYou can start a new business anytime with `!createbusiness`",
        discord.Color.orange()
    )
    await ctx.send(embed=embed)

@bot.command(name="invest")
async def invest(ctx, amount: str):
    """Invest more money into your business."""
    user_id = str(ctx.author.id)
    if user_id not in bot.businesses:
        return await ctx.send("❌ You don't own a business. Create one with `!createbusiness` first.")
    
    try:
        amount_num = parse_money_amount(amount)
    except:
        return await ctx.send("❌ Invalid amount! Use a number or shorthand like 5m (million), 5b (billion), 5t (trillion).")
    if amount_num <= 0:
        return await ctx.send("❌ Amount must be positive.")
    
    wallet = bot.wallets.get(user_id, 0)
    if wallet < amount_num:
        return await ctx.send(f"❌ You need {format_money(amount_num)} in your wallet.")
    
    business = bot.businesses[user_id]
    old_daily = int(business["investment"] * business["profit_rate"])
    business["investment"] += amount_num
    increase = int(amount_num / 100000) * 0.01
    business["profit_rate"] += increase
    bot.wallets[user_id] = wallet - amount_num
    new_daily = int(business["investment"] * business["profit_rate"])
    
    save_economy()
    asyncio.create_task(async_save_economy())
    save_businesses()
    
    embed = create_embed("📈 Investment Successful",
                         f"**Business:** {business['name']}\n**Investment Added:** {format_money(amount_num)}\n**New Total Investment:** {format_money(business['investment'])}\n**New Daily Profit:** {format_money(new_daily)} (was {format_money(old_daily)})",
                         discord.Color.green())
    await ctx.send(embed=embed)

@bot.command(name="topbusinesses", aliases=["topbiz"])
async def top_businesses(ctx):
    """Show the top 10 businesses by total investment."""
    if not bot.businesses:
        return await ctx.send("📭 No businesses have been created yet.")
    
    biz_list = []
    for uid, biz in bot.businesses.items():
        try:
            user = await bot.fetch_user(int(uid))
            name = user.display_name
        except:
            name = f"<@{uid}>"
        biz_list.append((name, biz["name"], biz["investment"], biz["total_profit"], biz["profit_rate"]))
    
    biz_list.sort(key=lambda x: x[2], reverse=True)
    top10 = biz_list[:10]
    
    embed = discord.Embed(title="🏆 Top Businesses", color=discord.Color.gold())
    medals = ["🥇", "🥈", "🥉"]
    for i, (owner, name, investment, profit, rate) in enumerate(top10, 1):
        prefix = medals[i-1] if i <= 3 else f"{i}."
        embed.add_field(
            name=f"{prefix} {name}",
            value=f"**Owner:** {owner}\n**Investment:** {format_money(investment)}\n**Total Profits:** {format_money(profit)}\n**Rate:** {rate*100:.1f}%",
            inline=False
        )
    await ctx.send(embed=embed)
    
    


# ==================== SHOP & TRADING COMMANDS ====================
@bot.command(name="shop")
async def shop(ctx, category: str = None):
    if not category:
        cats = ""
        for cat in bot.shop_items:
            if bot.shop_items[cat]:
                cats += f"• `!shop {cat}` - {len(bot.shop_items[cat])} item(s)\n"
        embed = create_embed("🛒 Shop - Categories", f"{cats}\n**Buy:** `!buy <category> <item>`\n**Balance:** {format_money(bot.wallets.get(str(ctx.author.id), 0))}", discord.Color.blue())
        await ctx.send(embed=embed)
        return
    category = category.lower()
    if category not in bot.shop_items or not bot.shop_items[category]:
        return await ctx.send(f"❌ No items in **{category}**.")
    items = bot.shop_items[category]
    rarity_colors = {
        "common": "⚪ Common", "uncommon": "🟢 Uncommon", "rare": "🔵 Rare",
        "epic": "🟣 Epic", "legendary": "🟡 Legendary"
    }
    embed = create_embed(f"🛒 {category.title()} Shop", f"Use `!buy {category} <item>`\n**Balance:** {format_money(bot.wallets.get(str(ctx.author.id), 0))}", discord.Color.blue())
    for i, item in enumerate(items, 1):
        rarity_text = rarity_colors.get(item.get('rarity', 'common'), item.get('rarity', 'common').title())
        embed.add_field(
            name=f"{item.get('emoji','📦')} {i}. {item['name']} - {format_money(item['price'])} [{rarity_text}]",
            value=item.get('description', 'No description'), inline=False
        )
    await ctx.send(embed=embed)

@bot.command(name="buy")
async def buy(ctx, category: str = None, *, item_name: str = None):
    if not category or not item_name:
        return await ctx.send("❌ Usage: `!buy <category> <item_name>`")
    category = category.lower()
    if category not in bot.shop_items:
        return await ctx.send(f"❌ Category `{category}` not found.")
    item = next((i for i in bot.shop_items[category] if i["name"].lower() == item_name.lower()), None)
    if not item:
        return await ctx.send(f"❌ Item `{item_name}` not found in {category}.")
    user_id = str(ctx.author.id)
    wallet = bot.wallets.get(user_id, 0)
    if wallet < item["price"]:
        return await ctx.send(f"❌ You need {format_money(item['price'])}!")
    if category == "roles":
        role = discord.utils.get(ctx.guild.roles, name=item["name"])
        if not role:
            try:
                role = await ctx.guild.create_role(name=item["name"], color=discord.Color.gold(), reason="Shop purchase")
            except discord.Forbidden:
                return await ctx.send("❌ I can't create roles.")
        if role in ctx.author.roles:
            return await ctx.send(f"❌ You already have {role.mention}.")
        try:
            await ctx.author.add_roles(role)
        except discord.Forbidden:
            return await ctx.send("❌ I can't give you that role.")
    bot.wallets[user_id] -= item["price"]
    if user_id not in bot.owned_items:
        bot.owned_items[user_id] = {}
    if category not in bot.owned_items[user_id]:
        bot.owned_items[user_id][category] = []
    bot.owned_items[user_id][category].append(item["name"])
    save_economy()
    asyncio.create_task(async_save_economy())
    embed = create_embed("✅ Purchase Successful!", f"You bought **{item['name']}** for {format_money(item['price'])}.\n**New Balance:** {format_money(bot.wallets[user_id])}", discord.Color.green())
    if category == "roles":
        embed.add_field(name="🎭 Role Added", value=f"You now have the **{item['name']}** role!", inline=False)
    await ctx.send(embed=embed)

@bot.command(name="inventory", aliases=["inv", "items"])
async def inventory(ctx, member: discord.Member = None):
    target = member or ctx.author
    user_id = str(target.id)
    if user_id not in bot.owned_items or not bot.owned_items[user_id]:
        return await ctx.send(f"📦 {target.name} has no items.")
    total = sum(len(items) for items in bot.owned_items[user_id].values())
    embed = create_embed(f"📦 {target.name}'s Inventory", f"**Total Items:** {total}", discord.Color.blue())
    for cat, items in bot.owned_items[user_id].items():
        if items:
            embed.add_field(name=f"{cat.title()} ({len(items)})", value="\n".join([f"• {i}" for i in items[:10]]) + ("..." if len(items)>10 else ""), inline=False)
    if member:
        embed.set_footer(text=f"Requested by {ctx.author.name}")
    await ctx.send(embed=embed)

@bot.command(name="sellitem")
async def sell_item(ctx, buyer: discord.Member, item_name: str, price: str):
    try:
        price_num = parse_money_amount(price)
    except:
        return await ctx.send("❌ Invalid price! Use a number or shorthand like 5m (million), 5b (billion), 5t (trillion).")
    if price_num <= 0:
        return await ctx.send("❌ Price must be positive.")
    if buyer == ctx.author:
        return await ctx.send("❌ You cannot sell to yourself.")
    seller_id = str(ctx.author.id)
    buyer_id = str(buyer.id)
    owned = bot.owned_items.get(seller_id, {})
    found_cat = None
    found_item = None
    for cat, items in owned.items():
        for it in items:
            if it.lower() == item_name.lower():
                found_cat, found_item = cat, it
                break
        if found_item:
            break
    if not found_item:
        return await ctx.send(f"❌ You don't own **{item_name}**.")
    if not hasattr(bot, 'pending_trades'):
        bot.pending_trades = {}
    trade_id = f"{seller_id}_{buyer_id}_{found_item}"
    bot.pending_trades[trade_id] = {
        "seller": ctx.author.id,
        "buyer": buyer.id,
        "item": found_item,
        "category": found_cat,
        "price": price_num,
        "timestamp": datetime.datetime.now().isoformat()
    }
    embed = create_embed("📦 Item Offered", f"**Seller:** {ctx.author.mention}\n**Buyer:** {buyer.mention}\n**Item:** {found_item}\n**Price:** {format_money(price_num)}\n\nBuyer has 60 seconds to accept with `!buyitem {ctx.author.name} {found_item}`.", discord.Color.blue())
    await ctx.send(embed=embed)
    await asyncio.sleep(60)
    if trade_id in bot.pending_trades:
        del bot.pending_trades[trade_id]
        await ctx.send(f"⏰ Trade offer for **{found_item}** expired.")

@bot.command(name="buyitem")
async def buy_item(ctx, seller: discord.Member, *, item_name: str):
    buyer_id = str(ctx.author.id)
    seller_id = str(seller.id)
    trade_id = f"{seller_id}_{buyer_id}_{item_name}"
    if not hasattr(bot, 'pending_trades') or trade_id not in bot.pending_trades:
        return await ctx.send("❌ No active trade offer found.")
    trade = bot.pending_trades[trade_id]
    if trade["buyer"] != ctx.author.id:
        return await ctx.send("❌ This trade is not for you.")
    price = trade["price"]
    buyer_wallet = bot.wallets.get(buyer_id, 0)
    if buyer_wallet < price:
        return await ctx.send(f"❌ You need {format_money(price)} to buy this item.")
    seller_items = bot.owned_items.get(seller_id, {})
    if trade["category"] in seller_items and trade["item"] in seller_items[trade["category"]]:
        seller_items[trade["category"]].remove(trade["item"])
        if not seller_items[trade["category"]]:
            del seller_items[trade["category"]]
        buyer_items = bot.owned_items.get(buyer_id, {})
        if trade["category"] not in buyer_items:
            buyer_items[trade["category"]] = []
        buyer_items[trade["category"]].append(trade["item"])
        bot.owned_items[buyer_id] = buyer_items
        bot.wallets[buyer_id] -= price
        bot.wallets[seller_id] = bot.wallets.get(seller_id, 0) + price
        save_economy()
        asyncio.create_task(async_save_economy())
        del bot.pending_trades[trade_id]
        embed = create_embed("✅ Purchase Complete", f"{ctx.author.mention} bought **{trade['item']}** from {seller.mention} for {format_money(price)}.", discord.Color.green())
        await ctx.send(embed=embed)
    else:
        await ctx.send("❌ The seller no longer has that item.")
        del bot.pending_trades[trade_id]
        
        


# ==================== ADMIN MONEY COMMANDS ====================
@bot.command(name="givemoney")
@commands.has_permissions(administrator=True)
async def givemoney(ctx, member: discord.Member, amount: str):
    try:
        amount_num = parse_money_amount(amount)
    except:
        return await ctx.send("❌ Invalid amount! Use a number or shorthand like 5m (million), 5b (billion), 5t (trillion).")
    if amount_num <= 0:
        return await ctx.send("❌ Positive amount only.")
    user_id = str(member.id)
    bot.wallets[user_id] = bot.wallets.get(user_id, 0) + amount_num
    save_economy()
    asyncio.create_task(async_save_economy())
    embed = create_embed("✅ Money Given", f"Gave {format_money(amount_num)} to {member.mention}\n**New Balance:** {format_money(bot.wallets[user_id])}", discord.Color.green())
    embed.set_footer(text=f"Given by {ctx.author.name}")
    await ctx.send(embed=embed)

@bot.command(name="addmoney")
@commands.has_permissions(administrator=True)
async def addmoney(ctx, amount: str):
    try:
        amount_num = parse_money_amount(amount)
    except:
        return await ctx.send("❌ Invalid amount! Use a number or shorthand like 5m (million), 5b (billion), 5t (trillion).")
    if amount_num <= 0:
        return await ctx.send("❌ Positive amount only.")
    user_id = str(ctx.author.id)
    bot.wallets[user_id] = bot.wallets.get(user_id, 0) + amount_num
    save_economy()
    asyncio.create_task(async_save_economy())
    embed = create_embed("✅ Money Added", f"Added {format_money(amount_num)} to your wallet!\n**New Balance:** {format_money(bot.wallets[user_id])}", discord.Color.green())
    await ctx.send(embed=embed)

@bot.command(name="setbalance")
@commands.has_permissions(administrator=True)
async def setbalance(ctx, member: discord.Member, amount: str):
    try:
        amount_num = parse_money_amount(amount)
    except:
        return await ctx.send("❌ Invalid amount! Use a number or shorthand like 5m (million), 5b (billion), 5t (trillion).")
    if amount_num < 0:
        return await ctx.send("❌ Amount cannot be negative.")
    user_id = str(member.id)
    bot.wallets[user_id] = amount_num
    save_economy()
    asyncio.create_task(async_save_economy())
    embed = create_embed("✅ Balance Set", f"Set {member.mention}'s wallet to {format_money(amount_num)}", discord.Color.green())
    embed.set_footer(text=f"Set by {ctx.author.name}")
    await ctx.send(embed=embed)

# ==================== SHOP MANAGEMENT ====================
@bot.command(name="addshopitem")
@commands.has_permissions(administrator=True)
async def addshopitem(ctx, category: str, name: str, price: int, rarity: str = "common", *, description: str = ""):
    if price <= 0:
        return await ctx.send("❌ Price must be >0.")
    category = category.lower()
    if category not in bot.shop_items:
        bot.shop_items[category] = []
    for item in bot.shop_items[category]:
        if item["name"].lower() == name.lower():
            return await ctx.send(f"❌ Item '{name}' already exists in {category}.")
    rarity = rarity.lower()
    if rarity not in ["common", "uncommon", "rare", "epic", "legendary"]:
        return await ctx.send("❌ Rarity must be: common, uncommon, rare, epic, legendary")
    emoji_map = {
        "common": "⚪", "uncommon": "🟢", "rare": "🔵",
        "epic": "🟣", "legendary": "🟡"
    }
    new_item = {
        "name": name, "price": price, "description": description,
        "emoji": emoji_map[rarity], "rarity": rarity
    }
    bot.shop_items[category].append(new_item)
    asyncio.create_task(async_save_shop_items())
    with open(SHOP_FILE, "w") as f:
        json.dump(bot.shop_items, f, indent=2)
    embed = create_embed("✅ Shop Item Added",
        f"**Item:** {name}\n**Category:** {category}\n**Price:** {format_money(price)}\n**Rarity:** {rarity.title()}\n**Description:** {description if description else 'No description'}",
        discord.Color.green())
    await ctx.send(embed=embed)

@bot.command(name="removeitem", aliases=["shopremove", "delitem"])
@commands.has_permissions(administrator=True)
async def remove_shop_item(ctx, category: str, *, item_name: str):
    category = category.lower()
    if category not in bot.shop_items:
        return await ctx.send(f"❌ Category `{category}` not found.")
    found = None
    for item in bot.shop_items[category]:
        if item["name"].lower() == item_name.lower():
            found = item
            break
    if not found:
        return await ctx.send(f"❌ Item `{item_name}` not found in {category}.")
    bot.shop_items[category].remove(found)
    asyncio.create_task(async_save_shop_items())
    with open(SHOP_FILE, "w") as f:
        json.dump(bot.shop_items, f, indent=2)
    embed = create_embed("✅ Item Removed", f"Removed **{found['name']}** from {category} shop.", discord.Color.green())
    await ctx.send(embed=embed)

@bot.command(name="editshopitem", aliases=["edititem"])
@commands.has_permissions(administrator=True)
async def editshopitem(ctx, category: str, item_name: str, new_price: int, *, new_description: str):
    category = category.lower()
    for item in bot.shop_items.get(category, []):
        if item["name"].lower() == item_name.lower():
            item["price"] = new_price
            item["description"] = new_description
            asyncio.create_task(async_save_shop_items())
            with open(SHOP_FILE, "w") as f:
                json.dump(bot.shop_items, f, indent=2)
            embed = create_embed("✅ Item Updated", f"**Item:** {item_name}\n**New Price:** {format_money(new_price)}\n**New Description:** {new_description}", discord.Color.green())
            await ctx.send(embed=embed)
            return
    await ctx.send(f"❌ Item `{item_name}` not found in {category}.")

# ==================== SALARY COMMANDS ====================
@bot.command(name="setsalary")
@commands.has_permissions(administrator=True)
async def setsalary(ctx, amount: str, *, role_name: str):
    """
    Set a weekly salary for a role.
    Usage: !setsalary <amount> <role name>
    Example: !setsalary 6m Managing director
    """
    try:
        salary = parse_money_amount(amount)
    except:
        return await ctx.send("❌ Invalid salary amount! Use a number or shorthand like 5m (million), 5b (billion), 5t (trillion).")

    if salary < 0:
        return await ctx.send("❌ Salary cannot be negative.")

    role = discord.utils.get(ctx.guild.roles, name=role_name)
    if not role:
        for r in ctx.guild.roles:
            if r.name.lower() == role_name.lower():
                role = r
                break
    if not role:
        return await ctx.send(f"❌ Role `{role_name}` not found.")

    bot.role_salaries[role.name] = salary
    asyncio.create_task(async_save_role_salaries())
    with open(ROLE_SALARIES_FILE, "w") as f:
        json.dump(bot.role_salaries, f, indent=2)

    embed = create_embed(
        "✅ Salary Set",
        f"**Role:** {role.name}\n**Weekly Salary:** {format_money(salary)}",
        discord.Color.green()
    )
    await ctx.send(embed=embed)

@bot.command(name="salarylist")
async def salarylist(ctx):
    if not bot.role_salaries:
        return await ctx.send("📭 No salaries have been set.")
    embed = discord.Embed(title="💰 Role Salaries (Weekly)", description="Salaries paid every 7 days", color=discord.Color.gold())
    default = bot.role_salaries.get("default", 1000)
    embed.add_field(name="👤 Default", value=format_money(default), inline=False)
    for role, salary in bot.role_salaries.items():
        if role != "default":
            embed.add_field(name=f"👑 {role}", value=format_money(salary), inline=True)
    await ctx.send(embed=embed)

@bot.command(name="paysalary", aliases=["paysalaries", "salarypay", "forcepay"])
@commands.has_permissions(administrator=True)
async def paysalary(ctx):
    await ctx.send("💰 Processing weekly salaries...")
    total = 0
    count = 0
    pending_tax = {}
    for guild in bot.guilds:
        for member in guild.members:
            if not member.bot:
                user_id = str(member.id)
                salary = bot.role_salaries.get("default", 1000)
                for role in member.roles:
                    if role.name in bot.role_salaries and bot.role_salaries[role.name] > salary:
                        salary = bot.role_salaries[role.name]
                weekly = salary * 7
                tax_rate = 5
                if hasattr(bot, 'role_tax_rates'):
                    for role in member.roles:
                        if role.name in bot.role_tax_rates:
                            tax_rate = max(tax_rate, bot.role_tax_rates[role.name])
                tax = int(weekly * tax_rate / 100)
                net = weekly - tax
                bot.banks[user_id] = bot.banks.get(user_id, 0) + net
                if tax > 0:
                    pending_tax[user_id] = pending_tax.get(user_id, 0) + tax
                total += weekly
                count += 1
    if not hasattr(bot, 'pending_tax'):
        bot.pending_tax = {}
    for uid, tax in pending_tax.items():
        bot.pending_tax[uid] = bot.pending_tax.get(uid, 0) + tax
    save_pending_tax()
    save_economy()
    asyncio.create_task(async_save_economy())
    with open(LAST_SALARY_FILE, "w") as f:
        json.dump({"last_salary": datetime.datetime.now().isoformat(), "salaries_given": count, "total_amount": total, "date": datetime.datetime.now().strftime("%Y-%m-%d"), "paid_by": str(ctx.author.id), "manual_payment": True}, f, indent=2)
    embed = create_embed("💰 Manual Salary Payment", f"**Total Paid:** {format_money(total)}\n**Users Paid:** {count}", discord.Color.green())
    await ctx.send(embed=embed)

@bot.command(name="next_salary")
async def next_salary(ctx):
    """Show how long until the next automatic salary payment (7-day cycle)."""
    try:
        with open(LAST_SALARY_FILE, "r") as f:
            last_data = json.load(f)
        last_time_str = last_data.get("last_salary", "2000-01-01T00:00:00")
        last_time = datetime.datetime.fromisoformat(last_time_str)
    except:
        last_time = datetime.datetime.now() - datetime.timedelta(days=7)
    
    next_time = last_time + datetime.timedelta(days=7)
    now = datetime.datetime.now()
    
    if now >= next_time:
        remaining = datetime.timedelta(seconds=0)
        status = "🔴 Salaries are overdue! Use `!paysalary` to pay them manually."
    else:
        remaining = next_time - now
        status = f"✅ Next automatic salary payment in **{remaining.days}d {remaining.seconds//3600}h {(remaining.seconds%3600)//60}m**"
    
    embed = discord.Embed(title="⏱️ Next Salary Payment", color=discord.Color.blue())
    embed.add_field(name="Last Salary Payment", value=last_time.strftime("%Y-%m-%d %H:%M:%S UTC"), inline=False)
    embed.add_field(name="Next Scheduled", value=next_time.strftime("%Y-%m-%d %H:%M:%S UTC"), inline=False)
    embed.add_field(name="Status", value=status, inline=False)
    await ctx.send(embed=embed)
    
    
    

# ==================== UTILITY COMMANDS ====================
@bot.command(name="uptime")
async def uptime(ctx):
    delta = datetime.datetime.now() - bot.start_time
    hours = delta.seconds // 3600
    minutes = (delta.seconds % 3600) // 60
    seconds = delta.seconds % 60
    embed = discord.Embed(title="🕐 Bot Uptime Stats", color=discord.Color.green())
    embed.add_field(name="⏰ Online For", value=f"**{hours}h {minutes}m {seconds}s**", inline=True)
    embed.add_field(name="🔄 Since", value=f"{bot.start_time.strftime('%Y-%m-%d %H:%M:%S')}", inline=True)
    embed.set_footer(text=f"Requested by {ctx.author.name}")
    await ctx.send(embed=embed)

# ==================== SHORTENED ROLE COMMANDS (staff only) ====================
@bot.command(name="cr", aliases=["createrole"])
@commands.check(is_user_staff)
async def create_role_short(ctx, role_name: str, color: str = None):
    if ctx.guild is None:
        return await ctx.send("❌ This command can only be used in a server.")
    try:
        color_value = discord.Color.default()
        if color:
            if color.startswith('#'):
                color_value = discord.Color(int(color[1:], 16))
            else:
                try:
                    color_value = getattr(discord.Color, color.lower())()
                except AttributeError:
                    color_value = discord.Color(int(color, 16))
        role = await ctx.guild.create_role(name=role_name, color=color_value, reason=f"Created by {ctx.author}")
        embed = create_embed("✅ Role Created", f"Role **{role.name}** has been created.", discord.Color.green())
        await ctx.send(embed=embed)
    except discord.Forbidden:
        embed = create_embed("❌ Error", "I don't have permission to create roles.", discord.Color.red())
        await ctx.send(embed=embed)
    except Exception as e:
        embed = create_embed("❌ Error", f"Could not create role: {str(e)}", discord.Color.red())
        await ctx.send(embed=embed)

@bot.command(name="ar", aliases=["addrole"])
@commands.check(is_user_staff)
async def add_role_short(ctx, member: discord.Member, *, role_name: str):
    if ctx.guild is None:
        return await ctx.send("❌ This command can only be used in a server.")
    role = discord.utils.get(ctx.guild.roles, name=role_name)
    if not role:
        embed = create_embed("❌ Error", f"Role `{role_name}` not found.", discord.Color.red())
        await ctx.send(embed=embed)
        return
    if role in member.roles:
        embed = create_embed("❌ Error", f"{member.mention} already has the role {role.mention}.", discord.Color.red())
        await ctx.send(embed=embed)
        return
    if ctx.author.top_role <= role and not ctx.author.guild_permissions.administrator:
        return await ctx.send("❌ You cannot assign a role that is higher than or equal to your highest role.")
    try:
        await member.add_roles(role, reason=f"Added by {ctx.author}")
        embed = create_embed("✅ Role Added", f"Added {role.mention} to {member.mention}.", discord.Color.green())
        await ctx.send(embed=embed)
    except discord.Forbidden:
        embed = create_embed("❌ Error", "I don't have permission to manage that role.", discord.Color.red())
        await ctx.send(embed=embed)

@bot.command(name="rr", aliases=["removerole"])
@commands.check(is_user_staff)
async def remove_role_short(ctx, member: discord.Member, *, role_name: str):
    if ctx.guild is None:
        return await ctx.send("❌ This command can only be used in a server.")
    role = discord.utils.get(ctx.guild.roles, name=role_name)
    if not role:
        embed = create_embed("❌ Error", f"Role `{role_name}` not found.", discord.Color.red())
        await ctx.send(embed=embed)
        return
    if role not in member.roles:
        embed = create_embed("❌ Error", f"{member.mention} does not have the role {role.mention}.", discord.Color.red())
        await ctx.send(embed=embed)
        return
    if ctx.author.top_role <= role and not ctx.author.guild_permissions.administrator:
        return await ctx.send("❌ You cannot remove a role that is higher than or equal to your highest role.")
    try:
        await member.remove_roles(role, reason=f"Removed by {ctx.author}")
        embed = create_embed("✅ Role Removed", f"Removed {role.mention} from {member.mention}.", discord.Color.green())
        await ctx.send(embed=embed)
    except discord.Forbidden:
        embed = create_embed("❌ Error", "I don't have permission to manage that role.", discord.Color.red())
        await ctx.send(embed=embed)

# ==================== ROLE MEMBERS COMMAND ====================
@bot.command(name="rolemembers", aliases=["rm"])
@commands.has_permissions(manage_roles=True)
async def role_members(ctx, *, role_name: str):
    """List all members with a specific role. Admin/Manage Roles only."""
    role = discord.utils.get(ctx.guild.roles, name=role_name)
    if not role:
        for r in ctx.guild.roles:
            if r.name.lower() == role_name.lower():
                role = r
                break
    if not role:
        return await ctx.send(f"❌ Role `{role_name}` not found.")
    members = [member for member in ctx.guild.members if role in member.roles]
    if not members:
        return await ctx.send(f"📭 No members have the role **{role.name}**.")
    member_list = "\n".join([f"{i+1}. {m.mention} ({m.name})" for i, m in enumerate(members[:50])])
    if len(members) > 50:
        member_list += f"\n... and {len(members)-50} more."
    embed = discord.Embed(title=f"👥 Members with {role.name}", description=member_list, color=role.color)
    embed.set_footer(text=f"Total: {len(members)} members")
    await ctx.send(embed=embed)

# ==================== ROLE ICON COMMANDS ====================
@bot.command(name="roleicon", aliases=["addroleicon"])
@commands.has_permissions(administrator=True)
async def add_role_icon(ctx, role_name: str, emoji: str):
    """Add an icon (emoji) to a role. Admin only."""
    role = discord.utils.get(ctx.guild.roles, name=role_name)
    if not role:
        for r in ctx.guild.roles:
            if r.name.lower() == role_name.lower():
                role = r
                break
    if not role:
        return await ctx.send(f"❌ Role `{role_name}` not found.")
    try:
        with open("role_icons.json", "r") as f:
            icons = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        icons = {}
    
    icons[str(role.id)] = emoji
    with open("role_icons.json", "w") as f:
        json.dump(icons, f, indent=2)
    
    await ctx.send(f"✅ Role **{role.name}** icon set to {emoji} (will appear in embeds)")

@bot.command(name="removeicon", aliases=["removeroleicon"])
@commands.has_permissions(administrator=True)
async def remove_role_icon(ctx, role_name: str):
    """Remove the icon from a role. Admin only."""
    role = discord.utils.get(ctx.guild.roles, name=role_name)
    if not role:
        for r in ctx.guild.roles:
            if r.name.lower() == role_name.lower():
                role = r
                break
    if not role:
        return await ctx.send(f"❌ Role `{role_name}` not found.")
    
    try:
        with open("role_icons.json", "r") as f:
            icons = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        icons = {}
    
    if str(role.id) in icons:
        del icons[str(role.id)]
        with open("role_icons.json", "w") as f:
            json.dump(icons, f, indent=2)
        await ctx.send(f"✅ Removed icon from **{role.name}**.")
    else:
        await ctx.send(f"ℹ️ No icon was set for **{role.name}**.")

# ==================== ROLE HIERARCHY COMMAND ====================
@bot.command(name="roleposition", aliases=["setroleposition"])
@commands.has_permissions(administrator=True)
async def set_role_position(ctx, role_name: str, position: int):
    """Change the position (hierarchy) of a role. Admin only."""
    role = discord.utils.get(ctx.guild.roles, name=role_name)
    if not role:
        for r in ctx.guild.roles:
            if r.name.lower() == role_name.lower():
                role = r
                break
    if not role:
        return await ctx.send(f"❌ Role `{role_name}` not found.")
    if position < 0:
        return await ctx.send("❌ Position must be 0 or higher.")
    if position >= len(ctx.guild.roles):
        return await ctx.send(f"❌ Position cannot exceed {len(ctx.guild.roles)-1}.")
    try:
        await role.edit(position=position)
        await ctx.send(f"✅ **{role.name}** moved to position {position}.")
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to move that role.")
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")
        
        


# ==================== QUARANTINE COMMANDS ====================
@bot.command(name="q")
@commands.has_permissions(manage_messages=True)
async def quarantine(ctx, member: discord.Member, *, reason="No reason provided"):
    if not can_moderate(ctx.author, member):
        return await ctx.send("❌ You cannot quarantine a user with a higher or equal role.")
    if member.guild_permissions.administrator:
        embed = create_embed("❌ Error", "Cannot quarantine an administrator.", discord.Color.red())
        await ctx.send(embed=embed)
        return

    guild_id = str(ctx.guild.id)
    user_id = str(member.id)

    if guild_id in bot.quarantined_users and user_id in bot.quarantined_users[guild_id]:
        embed = create_embed("❌ Error", f"{member.mention} is already quarantined!", discord.Color.red())
        await ctx.send(embed=embed)
        return

    quarantine_category = discord.utils.get(ctx.guild.categories, name="Quarantine")
    if not quarantine_category:
        try:
            quarantine_category = await ctx.guild.create_category(name="Quarantine", reason="Quarantine system")
            for role in ctx.guild.roles:
                await quarantine_category.set_permissions(role, view_channel=False)
        except discord.Forbidden:
            embed = create_embed("❌ Error", "I don't have permission to create categories!", discord.Color.red())
            await ctx.send(embed=embed)
            return

    quarantine_role = discord.utils.get(ctx.guild.roles, name="Quarantined")
    if not quarantine_role:
        try:
            quarantine_role = await ctx.guild.create_role(name="Quarantined", color=discord.Color.dark_gray(), reason="Quarantine system")
            for channel in ctx.guild.channels:
                if channel.category != quarantine_category:
                    try:
                        await channel.set_permissions(quarantine_role, view_channel=False, send_messages=False, read_messages=False)
                    except:
                        pass
        except discord.Forbidden:
            embed = create_embed("❌ Error", "I don't have permission to create roles!", discord.Color.red())
            await ctx.send(embed=embed)
            return

    await member.add_roles(quarantine_role, reason="Quarantined")

    channel_name = "quarantine"
    quarantine_channel = discord.utils.get(quarantine_category.text_channels, name=channel_name)

    if not quarantine_channel:
        staff_role_names = [
            "president", "vice president", "prime minister", "Chief of staff",
            "Attorney general", "LEGENDARY", "Hall of famers", "Admin", "Mod", "sergeant","secretary general","Director general","Managing director"
        ]
        overwrites = {
            ctx.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            quarantine_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_messages=True),
            ctx.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_messages=True)
        }
        for role in ctx.guild.roles:
            if role.name in staff_role_names or role.permissions.administrator:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_messages=True)
        try:
            quarantine_channel = await ctx.guild.create_text_channel(
                name=channel_name,
                category=quarantine_category,
                overwrites=overwrites,
                reason="Quarantine channel"
            )
        except discord.Forbidden:
            embed = create_embed("❌ Error", "I don't have permission to create channels!", discord.Color.red())
            await ctx.send(embed=embed)
            return
    else:
        await quarantine_channel.set_permissions(member, view_channel=True, send_messages=True, read_messages=True)

    if guild_id not in bot.quarantined_users:
        bot.quarantined_users[guild_id] = {}
    bot.quarantined_users[guild_id][user_id] = {
        "channel_id": quarantine_channel.id,
        "reason": reason,
        "quarantined_by": str(ctx.author.id),
        "quarantined_at": datetime.datetime.now().isoformat()
    }
    if guild_id not in bot.quarantine_channels:
        bot.quarantine_channels[guild_id] = {}
    bot.quarantine_channels[guild_id][str(quarantine_channel.id)] = user_id
    save_quarantine()
    asyncio.create_task(async_save_quarantine())

    embed = create_embed(
        "🦠 User Quarantined",
        f"**User:** {member.mention}\n**Reason:** {reason}\n**By:** {ctx.author.mention}\n**Channel:** {quarantine_channel.mention}\n\nThe user can only talk in the quarantine channel until released.",
        discord.Color.orange()
    )
    await ctx.send(embed=embed)

    quarantine_embed = create_embed(
        "🦠 You have been quarantined",
        f"You have been placed in quarantine by {ctx.author.mention}\n**Reason:** {reason}\n\nYou can only communicate in this channel until a staff member releases you.",
        discord.Color.orange()
    )
    await quarantine_channel.send(f"{member.mention}", embed=quarantine_embed)

@bot.command(name="uq")
@commands.has_permissions(manage_messages=True)
async def unquarantine(ctx, member: discord.Member):
    guild_id = str(ctx.guild.id)
    user_id = str(member.id)

    if guild_id not in bot.quarantined_users or user_id not in bot.quarantined_users[guild_id]:
        embed = create_embed("❌ Error", f"{member.mention} is not quarantined!", discord.Color.red())
        await ctx.send(embed=embed)
        return

    quarantine_info = bot.quarantined_users[guild_id][user_id]
    channel_id = quarantine_info.get("channel_id")

    quarantine_role = discord.utils.get(ctx.guild.roles, name="Quarantined")
    if quarantine_role and quarantine_role in member.roles:
        await member.remove_roles(quarantine_role, reason="Unquarantined")

    if channel_id:
        try:
            channel = ctx.guild.get_channel(int(channel_id))
            if channel:
                await channel.set_permissions(member, overwrite=None)
        except:
            pass

    del bot.quarantined_users[guild_id][user_id]
    if not bot.quarantined_users[guild_id]:
        del bot.quarantined_users[guild_id]

    if guild_id in bot.quarantine_channels and str(channel_id) in bot.quarantine_channels[guild_id]:
        del bot.quarantine_channels[guild_id][str(channel_id)]
        if not bot.quarantine_channels[guild_id]:
            del bot.quarantine_channels[guild_id]

    save_quarantine()
    asyncio.create_task(async_save_quarantine())

    if channel_id:
        channel = ctx.guild.get_channel(int(channel_id))
        if channel and guild_id not in bot.quarantined_users:
            try:
                await channel.delete(reason="No quarantined users left")
                print(f"Deleted quarantine channel {channel.name}")
            except Exception as e:
                print(f"Failed to delete quarantine channel: {e}")

    embed = create_embed("✅ User Released", f"{member.mention} has been released from quarantine by {ctx.author.mention}\nThey can now participate in regular channels.", discord.Color.green())
    await ctx.send(embed=embed)
    try:
        await member.send(f"🎉 You have been released from quarantine in {ctx.guild.name}!")
    except:
        pass

@bot.command(name="quarantinelist", aliases=["qlist"])
@commands.has_permissions(manage_messages=True)
async def quarantinelist(ctx):
    guild_id = str(ctx.guild.id)
    if guild_id not in bot.quarantined_users or not bot.quarantined_users[guild_id]:
        embed = create_embed("🦠 Quarantine List", "No users are currently quarantined.", discord.Color.blue())
        await ctx.send(embed=embed)
        return
    embed = create_embed("🦠 Quarantined Users", f"Total: {len(bot.quarantined_users[guild_id])}", discord.Color.orange())
    for user_id, info in bot.quarantined_users[guild_id].items():
        try:
            user = await bot.fetch_user(int(user_id))
            quarantined_by = await bot.fetch_user(int(info["quarantined_by"])) if info.get("quarantined_by") else "Unknown"
            quarantined_at = datetime.datetime.fromisoformat(info["quarantined_at"]).strftime("%Y-%m-%d %H:%M")
            embed.add_field(name=f"👤 {user.name}", value=f"**Reason:** {info['reason']}\n**By:** {quarantined_by.name}\n**Since:** {quarantined_at}", inline=False)
        except:
            continue
    await ctx.send(embed=embed)

# ==================== COURT COMMANDS ====================
@bot.command(name="sue")
async def sue(ctx, member: discord.Member, *, reason: str):
    if member.id == ctx.author.id:
        return await ctx.send("⚖️ You cannot sue yourself.")
    case_id = f"{ctx.author.id}-{member.id}"
    bot.active_lawsuits[case_id] = {
        "plaintiff": ctx.author,
        "defendant": member,
        "reason": reason
    }
    embed = create_embed(
        "⚖️ LAWSUIT FILED",
        f"**Plaintiff:** {ctx.author.mention}\n**Defendant:** {member.mention}\n**Reason:** {reason}\n\n📢 **Awaiting a Judge's ruling.**\nAdministrators can use `!guilty @defendant <amount>` or `!dismiss @defendant`.",
        discord.Color.orange()
    )
    await ctx.send(embed=embed)

@bot.command(name="guilty")
@commands.has_permissions(administrator=True)
async def guilty(ctx, member: discord.Member, amount: str):
    try:
        amount_num = parse_money_amount(amount)
    except:
        return await ctx.send("❌ Invalid amount! Use a number or shorthand like 5m (million), 5b (billion), 5t (trillion).")
    if amount_num <= 0:
        return await ctx.send("❌ Fine must be positive.")
    found_case = None
    case_key = None
    for cid, data in bot.active_lawsuits.items():
        if data["defendant"].id == member.id:
            found_case = data
            case_key = cid
            break
    if not found_case:
        return await ctx.send(f"⚖️ There is no active lawsuit against {member.display_name}.")
    plaintiff = found_case["plaintiff"]
    target_id = str(member.id)
    plaintiff_id = str(plaintiff.id)
    def_wallet = bot.wallets.get(target_id, 0)
    def_bank = bot.banks.get(target_id, 0)
    if (def_wallet + def_bank) < amount_num:
        return await ctx.send("⚖️ The defendant doesn't have enough money to pay that settlement!")
    if def_wallet >= amount_num:
        bot.wallets[target_id] -= amount_num
    else:
        remaining = amount_num - def_wallet
        bot.wallets[target_id] = 0
        bot.banks[target_id] -= remaining
    bot.wallets[plaintiff_id] = bot.wallets.get(plaintiff_id, 0) + amount_num
    save_economy()
    asyncio.create_task(async_save_economy())
    del bot.active_lawsuits[case_key]
    embed = create_embed(
        "⚖️ JUDICIAL VERDICT: GUILTY",
        f"**Judge:** {ctx.author.mention}\n**Defendant:** {member.mention}\n**Plaintiff:** {plaintiff.mention}\n**Fine:** {format_money(amount_num)}\n\n💰 The settlement has been transferred automatically.",
        discord.Color.red()
    )
    await ctx.send(embed=embed)

@bot.command(name="dismiss")
@commands.has_permissions(administrator=True)
async def dismiss(ctx, member: discord.Member):
    for cid, data in list(bot.active_lawsuits.items()):
        if data["defendant"].id == member.id:
            del bot.active_lawsuits[cid]
            return await ctx.send(f"⚖️ The lawsuit against {member.mention} has been dismissed.")
    await ctx.send("⚖️ No active lawsuit found for that member.")
    
    


# ==================== TIMEZONE COMMANDS ====================
@bot.command(name="settz")
async def set_timezone(ctx, tz_name: str):
    """Set your timezone (e.g., Europe/London, America/New_York, Africa/Lagos)."""
    try:
        zone = zoneinfo.ZoneInfo(tz_name)
    except zoneinfo.ZoneInfoNotFoundError:
        return await ctx.send(f"❌ Unknown timezone. Use a valid IANA name (e.g., `Europe/London`, `America/New_York`).")
    user_id = str(ctx.author.id)
    bot.user_timezones[user_id] = tz_name
    with open("user_timezones.json", "w") as f:
        json.dump(bot.user_timezones, f, indent=2)
    now = datetime.datetime.now(zone)
    current_time = now.strftime("%H:%M:%S")
    await ctx.send(f"✅ Timezone set to **{tz_name}**. Your current time: {current_time}")

@bot.command(name="tz")
async def show_time(ctx, member: discord.Member = None):
    """Show current time for yourself or a mentioned user."""
    target = member or ctx.author
    user_id = str(target.id)
    tz_name = bot.user_timezones.get(user_id)
    if not tz_name:
        if member:
            return await ctx.send(f"❌ {target.mention} has not set a timezone. Use `!settz <timezone>`.")
        else:
            return await ctx.send("❌ You have not set a timezone. Use `!settz <timezone>` (e.g., `!settz Europe/London`).")
    try:
        zone = zoneinfo.ZoneInfo(tz_name)
    except:
        return await ctx.send(f"❌ Invalid timezone stored for {target.name}. Please reset with `!settz`.")
    now = datetime.datetime.now(zone)
    current_time = now.strftime("%Y-%m-%d %H:%M:%S")
    embed = discord.Embed(title=f"🕒 Current time for {target.display_name}", color=discord.Color.blue())
    embed.add_field(name="Timezone", value=tz_name, inline=True)
    embed.add_field(name="Local Time", value=current_time, inline=True)
    await ctx.send(embed=embed)

# ==================== ADMIN SAY COMMAND ====================
@bot.command(name="say")
@commands.has_permissions(administrator=True)
async def admin_say(ctx, *, message: str):
    """Make the bot say a message in the #general channel. Admin only."""
    general_channel = discord.utils.get(ctx.guild.text_channels, name="general")
    if not general_channel:
        general_channel = ctx.guild.system_channel
    if not general_channel:
        for channel in ctx.guild.text_channels:
            if channel.permissions_for(ctx.guild.me).send_messages:
                general_channel = channel
                break
    if not general_channel:
        return await ctx.send("❌ Could not find a suitable channel to send the message.")
    await general_channel.send(message)
    await ctx.send(f"✅ Message sent in {general_channel.mention}")

# ==================== STAFF STATS COMMAND ====================
@bot.command(name="staffstats", aliases=["ss"])
@commands.check(is_user_staff)
async def staff_stats(ctx, member: discord.Member = None):
    """Show moderation stats for a staff member (warns, mutes, kicks, bans)."""
    target = member or ctx.author
    user_id = str(target.id)
    guild_id = str(ctx.guild.id)

    warns = bot.warnings.get(guild_id, {}).get(user_id, 0)
    mutes = 1 if user_id in bot.muted_users else 0

    mod_stats_file = "mod_action_stats.json"
    try:
        with open(mod_stats_file, "r") as f:
            stats = json.load(f)
    except:
        stats = {}

    user_stats = stats.get(guild_id, {}).get(user_id, {"kicks": 0, "bans": 0})

    embed = discord.Embed(title=f"🛡️ Moderation Stats: {target.display_name}", color=discord.Color.blue())
    embed.add_field(name="⚠️ Warnings", value=str(warns), inline=True)
    embed.add_field(name="🔇 Mutes (current)", value=str(mutes), inline=True)
    embed.add_field(name="👢 Kicks", value=str(user_stats.get("kicks", 0)), inline=True)
    embed.add_field(name="🔨 Bans", value=str(user_stats.get("bans", 0)), inline=True)
    embed.set_footer(text=f"Requested by {ctx.author.name}")
    await ctx.send(embed=embed)

# ==================== TAX COMMAND ====================
@bot.command(name="tax")
@commands.has_permissions(administrator=True)
async def set_role_tax(ctx, role_name: str, tax_percent: int):
    """Set the tax percentage (0-50) for a role's weekly salary. Admin only."""
    if tax_percent < 0 or tax_percent > 50:
        return await ctx.send("❌ Tax percentage must be between 0 and 50.")
    role = discord.utils.get(ctx.guild.roles, name=role_name)
    if not role:
        for r in ctx.guild.roles:
            if r.name.lower() == role_name.lower():
                role = r
                break
    if not role:
        return await ctx.send(f"❌ Role `{role_name}` not found.")
    if not hasattr(bot, 'role_tax_rates'):
        bot.role_tax_rates = {}
    bot.role_tax_rates[role.name] = tax_percent
    with open("role_tax_rates.json", "w") as f:
        json.dump(bot.role_tax_rates, f, indent=2)
    await ctx.send(f"✅ Tax for role **{role.name}** set to {tax_percent}%.")
    
    


# ==================== SHARES SYSTEM ====================
SHARES_FILE = "shares.json"
SHARE_EARNINGS_FILE = "share_earnings.json"
PENDING_SHARE_TRADES_FILE = "pending_share_trades.json"

def load_shares():
    try:
        with open(SHARES_FILE, "r") as f:
            return json.load(f)
    except:
        return {"studios": {}, "businesses": {}}

def save_shares():
    with open(SHARES_FILE, "w") as f:
        json.dump(bot.shares, f, indent=2)

def load_share_earnings():
    try:
        with open(SHARE_EARNINGS_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_share_earnings():
    with open(SHARE_EARNINGS_FILE, "w") as f:
        json.dump(bot.share_earnings, f, indent=2)

def load_pending_trades():
    try:
        with open(PENDING_SHARE_TRADES_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_pending_trades():
    with open(PENDING_SHARE_TRADES_FILE, "w") as f:
        json.dump(bot.pending_share_trades, f, indent=2)

# Make sure shares are loaded
if not hasattr(bot, 'shares'):
    bot.shares = load_shares()
if not hasattr(bot, 'share_earnings'):
    bot.share_earnings = load_share_earnings()
if not hasattr(bot, 'pending_share_trades'):
    bot.pending_share_trades = load_pending_trades()

# ----- Helper: Distribute business profit to shareholders (with tax) -----
def distribute_business_profit(owner_id: str, profit: int):
    shares_data = bot.shares["businesses"].get(owner_id, {"total_shares": 100, "shares": {owner_id: 100}})
    total_shares = shares_data.get("total_shares", 100)
    share_dict = shares_data.get("shares", {owner_id: total_shares})
    distributed = {}
    tax_rate = 0.10
    for shareholder_id, share_count in share_dict.items():
        if share_count > 0:
            gross = int(profit * share_count / total_shares)
            if gross > 0:
                tax = int(gross * tax_rate)
                net = gross - tax
                bot.wallets[shareholder_id] = bot.wallets.get(shareholder_id, 0) + net
                if tax > 0:
                    bot.pending_tax[shareholder_id] = bot.pending_tax.get(shareholder_id, 0) + tax
                bot.share_earnings[shareholder_id] = bot.share_earnings.get(shareholder_id, 0) + net
                distributed[shareholder_id] = net
    return distributed

# ----- Helper: Create a pending trade -----
async def create_pending_trade(ctx, share_type: str, owner_id: str, initiator_id: str,
                                counterparty_id: str, amount: float, price: int, initiator_role: str):
    trade_id = str(int(datetime.datetime.now().timestamp() * 1000)) + str(random.randint(1000, 9999))
    bot.pending_share_trades[trade_id] = {
        "owner_id": owner_id,
        "share_type": share_type,
        "buyer_id": buyer_id if initiator_role == "buyer" else counterparty_id,
        "seller_id": seller_id if initiator_role == "seller" else counterparty_id,
        "amount": amount,
        "price": price,
        "created_at": datetime.datetime.now().isoformat(),
        "status": "pending"
    }
    save_pending_trades()

    counterparty = await bot.fetch_user(int(counterparty_id))
    initiator = await bot.fetch_user(int(initiator_id))

    try:
        await counterparty.send(
            f"📩 **New Share Trade Request**\n"
            f"{initiator.mention} wants to **{initiator_role}** **{amount:.2f}** shares of {share_type} (owned by <@{owner_id}>) for {format_money(price)}.\n"
            f"To **accept**, type `!accept_trade {trade_id}`\n"
            f"To **decline**, type `!decline_trade {trade_id}`\n"
            f"You have **120 seconds** to respond."
        )
        await ctx.send(f"✅ Trade request sent to {counterparty.mention}.")
    except discord.Forbidden:
        await ctx.send("❌ Could not DM the counterparty. Trade cancelled.")
        del bot.pending_share_trades[trade_id]
        save_pending_trades()
        return None

    def check(m):
        return m.author.id == counterparty.id and m.content.lower() in [f"!accept_trade {trade_id}", f"!decline_trade {trade_id}"]

    try:
        msg = await bot.wait_for('message', timeout=120.0, check=check)
    except asyncio.TimeoutError:
        if trade_id in bot.pending_share_trades:
            del bot.pending_share_trades[trade_id]
            save_pending_trades()
        await ctx.send("⏰ Trade request expired.")
        return None

    if msg.content.lower().startswith("!decline"):
        if trade_id in bot.pending_share_trades:
            del bot.pending_share_trades[trade_id]
            save_pending_trades()
        await ctx.send(f"❌ {counterparty.mention} declined the trade.")
        return None

    if trade_id not in bot.pending_share_trades:
        await ctx.send("❌ This trade is no longer valid.")
        return None
    trade = bot.pending_share_trades.pop(trade_id)
    save_pending_trades()
    return trade

# ==================== COMMANDS ====================

@bot.command(name="studio_shares", aliases=["myshares"])
async def studio_shares(ctx):
    user_id = str(ctx.author.id)
    embed = discord.Embed(title=f"📊 Shares for {ctx.author.display_name}", color=discord.Color.gold())

    # Studio shares
    studio_found = False
    for owner_id, studio in bot.studios.items():
        shares_data = bot.shares["studios"].get(owner_id, {"total_shares": 100, "shares": {owner_id: 100}})
        user_share = shares_data.get("shares", {}).get(user_id, 0)
        if user_share > 0:
            studio_found = True
            embed.add_field(
                name=f"🎬 {studio['studio_name']} (owned by <@{owner_id}>)",
                value=f"**Your Shares:** {user_share:.2f}/{shares_data['total_shares']:.2f}\n**Shareholders:** {len(shares_data.get('shares', {}))}",
                inline=False
            )
    if not studio_found:
        embed.add_field(name="Studio", value="No studio shares.", inline=False)

    # Business shares
    biz_found = False
    for owner_id, biz in bot.businesses.items():
        shares_data = bot.shares["businesses"].get(owner_id, {"total_shares": 100, "shares": {owner_id: 100}})
        user_share = shares_data.get("shares", {}).get(user_id, 0)
        if user_share > 0:
            biz_found = True
            embed.add_field(
                name=f"🏢 {biz['name']} (owned by <@{owner_id}>)",
                value=f"**Your Shares:** {user_share:.2f}/{shares_data['total_shares']:.2f}\n**Shareholders:** {len(shares_data.get('shares', {}))}",
                inline=False
            )
    if not biz_found:
        embed.add_field(name="Business", value="No business shares.", inline=False)

    await ctx.send(embed=embed)

@bot.command(name="sell_share")
async def sell_share(ctx, share_type: str, owner: discord.Member, buyer: discord.Member,
                     amount: float, price: str):
    """Sell shares you hold in someone else's asset.
    Usage: !sell_share studio @owner @buyer 2.5 5m"""
    share_type = share_type.lower()
    if share_type not in ["studio", "business"]:
        return await ctx.send("❌ Share type must be 'studio' or 'business'.")

    try:
        price_num = parse_money_amount(price)
    except:
        return await ctx.send("❌ Invalid price! Use shorthand like 5m, 2b, etc.")

    if price_num <= 0 or amount <= 0:
        return await ctx.send("❌ Amount and price must be positive.")

    seller_id = str(ctx.author.id)
    buyer_id = str(buyer.id)
    owner_id = str(owner.id)

    if seller_id == buyer_id:
        return await ctx.send("❌ You cannot sell shares to yourself.")

    # Get shares data for the given owner
    if share_type == "studio":
        if owner_id not in bot.studios:
            return await ctx.send(f"❌ {owner.mention} does not own a studio.")
        if owner_id not in bot.shares["studios"]:
            bot.shares["studios"][owner_id] = {"total_shares": 100, "shares": {owner_id: 100}}
        shares_data = bot.shares["studios"][owner_id]
    else:
        if owner_id not in bot.businesses:
            return await ctx.send(f"❌ {owner.mention} does not own a business.")
        if owner_id not in bot.shares["businesses"]:
            bot.shares["businesses"][owner_id] = {"total_shares": 100, "shares": {owner_id: 100}}
        shares_data = bot.shares["businesses"][owner_id]

    # Check seller's shares
    seller_shares = shares_data.get("shares", {}).get(seller_id, 0)
    if seller_shares < amount - 0.0001:
        return await ctx.send(f"❌ You only have {seller_shares:.2f} shares to sell.")

    # Check buyer's wallet
    if bot.wallets.get(buyer_id, 0) < price_num:
        return await ctx.send(f"❌ {buyer.mention} doesn't have enough money.")

    # Create pending trade
    trade = await create_pending_trade(
        ctx, share_type, owner_id,
        initiator_id=seller_id,
        counterparty_id=buyer_id,
        amount=amount,
        price=price_num,
        initiator_role="sell"
    )
    if trade is None:
        return

    # Execute trade (re-check)
    if share_type == "studio":
        shares_data = bot.shares["studios"].get(owner_id, {})
    else:
        shares_data = bot.shares["businesses"].get(owner_id, {})
    if not shares_data:
        await ctx.send("❌ Asset no longer exists. Trade cancelled.")
        return
    if shares_data.get("shares", {}).get(seller_id, 0) < amount - 0.0001:
        await ctx.send("❌ Seller no longer has enough shares.")
        return
    if bot.wallets.get(buyer_id, 0) < price_num:
        await ctx.send("❌ Buyer no longer has enough money.")
        return

    # Transfer
    shares_data["shares"][seller_id] = shares_data["shares"].get(seller_id, 0) - amount
    shares_data["shares"][buyer_id] = shares_data["shares"].get(buyer_id, 0) + amount
    bot.wallets[buyer_id] -= price_num
    bot.wallets[seller_id] = bot.wallets.get(seller_id, 0) + price_num

    save_shares()
    save_economy()
    asyncio.create_task(async_save_economy())

    share_name = "Studio" if share_type == "studio" else "Business"
    embed = create_embed(
        "✅ Trade Completed!",
        f"**{ctx.author.mention}** sold **{amount:.2f}** shares of {owner.mention}'s {share_name} to **{buyer.mention}** for {format_money(price_num)}.\n"
        f"**Seller remaining:** {shares_data['shares'][seller_id]:.2f}\n"
        f"**Buyer's new shares:** {shares_data['shares'][buyer_id]:.2f}",
        discord.Color.green()
    )
    await ctx.send(embed=embed)

@bot.command(name="buyshare")
async def buy_share(ctx, share_type: str, owner: discord.Member, seller: discord.Member,
                    amount: float, price: str):
    """Buy shares from a shareholder of someone's asset.
    Usage: !buyshare studio @owner @seller 2.5 5m"""
    share_type = share_type.lower()
    if share_type not in ["studio", "business"]:
        return await ctx.send("❌ Share type must be 'studio' or 'business'.")

    try:
        price_num = parse_money_amount(price)
    except:
        return await ctx.send("❌ Invalid price! Use shorthand like 5m, 2b, etc.")

    if price_num <= 0 or amount <= 0:
        return await ctx.send("❌ Amount and price must be positive.")

    buyer_id = str(ctx.author.id)
    seller_id = str(seller.id)
    owner_id = str(owner.id)

    if buyer_id == seller_id:
        return await ctx.send("❌ You cannot buy shares from yourself.")

    # Get shares data for the given owner
    if share_type == "studio":
        if owner_id not in bot.studios:
            return await ctx.send(f"❌ {owner.mention} does not own a studio.")
        if owner_id not in bot.shares["studios"]:
            bot.shares["studios"][owner_id] = {"total_shares": 100, "shares": {owner_id: 100}}
        shares_data = bot.shares["studios"][owner_id]
    else:
        if owner_id not in bot.businesses:
            return await ctx.send(f"❌ {owner.mention} does not own a business.")
        if owner_id not in bot.shares["businesses"]:
            bot.shares["businesses"][owner_id] = {"total_shares": 100, "shares": {owner_id: 100}}
        shares_data = bot.shares["businesses"][owner_id]

    # Check seller's shares
    seller_shares = shares_data.get("shares", {}).get(seller_id, 0)
    if seller_shares < amount - 0.0001:
        return await ctx.send(f"❌ Seller only has {seller_shares:.2f} shares available.")

    # Check buyer's wallet
    if bot.wallets.get(buyer_id, 0) < price_num:
        return await ctx.send(f"❌ You don't have enough money.")

    # Create pending trade – seller must confirm
    trade = await create_pending_trade(
        ctx, share_type, owner_id,
        initiator_id=buyer_id,
        counterparty_id=seller_id,
        amount=amount,
        price=price_num,
        initiator_role="buy"
    )
    if trade is None:
        return

    # Execute trade (re-check)
    if share_type == "studio":
        shares_data = bot.shares["studios"].get(owner_id, {})
    else:
        shares_data = bot.shares["businesses"].get(owner_id, {})
    if not shares_data:
        await ctx.send("❌ Asset no longer exists. Trade cancelled.")
        return
    if shares_data.get("shares", {}).get(seller_id, 0) < amount - 0.0001:
        await ctx.send("❌ Seller no longer has enough shares.")
        return
    if bot.wallets.get(buyer_id, 0) < price_num:
        await ctx.send("❌ You no longer have enough money.")
        return

    # Transfer
    shares_data["shares"][seller_id] = shares_data["shares"].get(seller_id, 0) - amount
    shares_data["shares"][buyer_id] = shares_data["shares"].get(buyer_id, 0) + amount
    bot.wallets[buyer_id] -= price_num
    bot.wallets[seller_id] = bot.wallets.get(seller_id, 0) + price_num

    save_shares()
    save_economy()
    asyncio.create_task(async_save_economy())

    share_name = "Studio" if share_type == "studio" else "Business"
    embed = create_embed(
        "✅ Trade Completed!",
        f"**{ctx.author.mention}** bought **{amount:.2f}** shares of {owner.mention}'s {share_name} from **{seller.mention}** for {format_money(price_num)}.\n"
        f"**Seller remaining:** {shares_data['shares'][seller_id]:.2f}\n"
        f"**Your new shares:** {shares_data['shares'][buyer_id]:.2f}",
        discord.Color.green()
    )
    await ctx.send(embed=embed)

@bot.command(name="share_earnings")
async def share_earnings(ctx, member: discord.Member = None):
    target = member or ctx.author
    user_id = str(target.id)
    total = bot.share_earnings.get(user_id, 0)
    embed = create_embed(
        f"💰 Dividend Earnings for {target.display_name}",
        f"**Total earned from shares (after tax):** {format_money(total)}",
        discord.Color.gold()
    )
    await ctx.send(embed=embed)

@bot.command(name="share_holders", aliases=["shareholders"])
async def share_holders(ctx, share_type: str, owner: discord.Member):
    """List shareholders of a specific studio/business.
    Usage: !shareholders studio @owner"""
    share_type = share_type.lower()
    if share_type not in ["studio", "business"]:
        return await ctx.send("❌ Share type must be 'studio' or 'business'.")
    owner_id = str(owner.id)

    if share_type == "studio":
        if owner_id not in bot.studios:
            return await ctx.send(f"❌ {owner.mention} does not own a studio.")
        shares_data = bot.shares["studios"].get(owner_id, {"total_shares": 100, "shares": {owner_id: 100}})
        embed = discord.Embed(title=f"🎬 Shareholders of {bot.studios[owner_id]['studio_name']}", color=discord.Color.magenta())
    else:
        if owner_id not in bot.businesses:
            return await ctx.send(f"❌ {owner.mention} does not own a business.")
        shares_data = bot.shares["businesses"].get(owner_id, {"total_shares": 100, "shares": {owner_id: 100}})
        embed = discord.Embed(title=f"🏢 Shareholders of {bot.businesses[owner_id]['name']}", color=discord.Color.blue())

    share_list = shares_data.get("shares", {})
    if not share_list:
        return await ctx.send("📭 No shareholders found.")
    lines = [f"<@{uid}>: {count:.2f} shares" for uid, count in share_list.items()]
    embed.description = "\n".join(lines)
    await ctx.send(embed=embed)

# Fallback commands for manual accept/decline (informational)
@bot.command(name="accept_trade")
async def accept_trade(ctx, trade_id: str):
    await ctx.send("⚠️ Please accept/decline the trade directly in the DM from the bot – it will automatically process your response.")

@bot.command(name="decline_trade")
async def decline_trade(ctx, trade_id: str):
    await ctx.send("⚠️ Please accept/decline the trade directly in the DM from the bot – it will automatically process your response.")
    
    


# ==================== STUDIO SYSTEM ====================
STUDIO_CREATION_COST = 50000

def load_studios():
    try:
        with open("studios.json", "r") as f:
            return json.load(f)
    except:
        return {}

def save_studios():
    with open("studios.json", "w") as f:
        json.dump(bot.studios, f, indent=2)

# Load studios on startup
bot.studios = load_studios()

@bot.command(name="create_studio", aliases=["createstudio"])
async def create_studio(ctx, *, studio_name: str):
    """Create your own movie studio. Costs $50,000."""
    user_id = str(ctx.author.id)
    if user_id in bot.studios:
        return await ctx.send("❌ You already own a studio. Use `!my_studio` to see it.")
    wallet = bot.wallets.get(user_id, 0)
    if wallet < STUDIO_CREATION_COST:
        return await ctx.send(f"❌ You need {format_money(STUDIO_CREATION_COST)} to create a studio.")
    for owner, data in bot.studios.items():
        if data["studio_name"].lower() == studio_name.lower():
            return await ctx.send(f"❌ A studio named **{studio_name}** already exists.")
    bot.wallets[user_id] = wallet - STUDIO_CREATION_COST
    bot.studios[user_id] = {
        "studio_name": studio_name,
        "total_earnings": 0,
        "movie_count": 0
    }
    # Initialize shares for the studio
    if user_id not in bot.shares["studios"]:
        bot.shares["studios"][user_id] = {"total_shares": 100, "shares": {user_id: 100}}
    save_shares()
    save_economy()
    asyncio.create_task(async_save_economy())
    save_studios()
    embed = create_embed("🎬 Studio Created!", f"**{studio_name}** is now yours! You own 100 shares. Use `!makemovie` to produce films.", discord.Color.green())
    await ctx.send(embed=embed)

@bot.command(name="my_studio", aliases=["mystudio"])
async def my_studio(ctx):
    """Show your studio's stats."""
    user_id = str(ctx.author.id)
    if user_id not in bot.studios:
        return await ctx.send("❌ You don't own a studio. Create one with `!create_studio <name>`.")
    studio = bot.studios[user_id]
    shares_data = bot.shares["studios"].get(user_id, {"total_shares": 100, "shares": {user_id: 100}})
    total_shares = shares_data.get("total_shares", 100)
    your_shares = shares_data.get("shares", {}).get(user_id, total_shares)
    
    embed = create_embed(f"🎬 {studio['studio_name']}", 
                         f"**Owner:** {ctx.author.mention}\n**Movies Made:** {studio['movie_count']}\n**Total Box Office:** {format_money(studio['total_earnings'])}\n**Your Shares:** {your_shares:.2f}/{total_shares:.2f}",
                         discord.Color.blue())
    await ctx.send(embed=embed)

@bot.command(name="top_studios", aliases=["topstudios"])
async def top_studios(ctx):
    """Show the top 10 studios by total box office earnings."""
    if not bot.studios:
        return await ctx.send("📭 No studios have been created yet.")
    studios_list = [(data["studio_name"], data["total_earnings"], data["movie_count"]) for data in bot.studios.values()]
    studios_list.sort(key=lambda x: x[1], reverse=True)
    top10 = studios_list[:10]
    embed = create_embed("🏆 Top Studios", "", discord.Color.gold())
    medals = ["🥇", "🥈", "🥉"]
    for i, (name, earnings, count) in enumerate(top10, 1):
        prefix = medals[i-1] if i <= 3 else f"{i}."
        embed.add_field(name=f"{prefix} {name}", value=f"💰 {format_money(earnings)} | 🎬 {count} movies", inline=False)
    await ctx.send(embed=embed)

@bot.command(name="studio_hits", aliases=["studioid", "studiohit"])
async def studio_hits(ctx, *, studio_name: str):
    """Show the top 5 highest grossing movies from a studio."""
    studio_owner = None
    studio_data = None
    for owner, data in bot.studios.items():
        if data["studio_name"].lower() == studio_name.lower():
            studio_owner = owner
            studio_data = data
            break
    if not studio_data:
        return await ctx.send(f"❌ No studio named **{studio_name}** found.")
    studio_movies = [m for m in bot.movies if m.get("studio") == studio_data["studio_name"]]
    if not studio_movies:
        return await ctx.send(f"📭 **{studio_data['studio_name']}** hasn't released any movies yet.")
    studio_movies.sort(key=lambda x: x["gross_earnings"], reverse=True)
    top5 = studio_movies[:5]
    embed = create_embed(f"🎬 Top Hits of {studio_data['studio_name']}", f"Total movies: {len(studio_movies)}", discord.Color.magenta())
    for i, movie in enumerate(top5, 1):
        producer = ctx.guild.get_member(movie["producer"])
        producer_name = producer.display_name if producer else movie["producer_name"]
        embed.add_field(name=f"{i}. {movie['title']}",
                        value=f"**Earnings:** {format_money(movie['gross_earnings'])}\n**Producer:** {producer_name}",
                        inline=False)
    await ctx.send(embed=embed)

# ==================== ACTOR STATS ====================
def get_actor_hits(user_id: str) -> int:
    """Get the number of hit movies an actor has been in."""
    if not hasattr(bot, 'actor_stats'):
        return 0
    return bot.actor_stats.get(user_id, {}).get("hits", 0)

def give_actor_award(user_id: str, award_type: str, movie_title: str, award_date: str):
    """Give an actor an award item. award_type: 'hit' or 'top'."""
    if user_id not in bot.owned_items:
        bot.owned_items[user_id] = {}
    if "awards" not in bot.owned_items[user_id]:
        bot.owned_items[user_id]["awards"] = []
    if award_type == "hit":
        award_name = f"🏆 Ford High Best Actor Award ({movie_title} - {award_date})"
        if not hasattr(bot, 'actor_stats'):
            try:
                with open("actor_stats.json", "r") as f:
                    bot.actor_stats = json.load(f)
            except:
                bot.actor_stats = {}
        if user_id not in bot.actor_stats:
            bot.actor_stats[user_id] = {"movies": 0, "earnings": 0, "hits": 0}
        bot.actor_stats[user_id]["hits"] = bot.actor_stats[user_id].get("hits", 0) + 1
        asyncio.create_task(save_actor_stats())
    else:
        award_name = f"🏆 Ford High Top Movie Award ({movie_title} - {award_date})"
    if award_name not in bot.owned_items[user_id]["awards"]:
        bot.owned_items[user_id]["awards"].append(award_name)
        save_economy()
        asyncio.create_task(async_save_economy())

async def save_actor_stats():
    with open("actor_stats.json", "w") as f:
        json.dump(bot.actor_stats, f, indent=2)

@bot.command(name="actorstats")
async def actor_stats(ctx, member: discord.Member = None):
    target = member or ctx.author
    user_id = str(target.id)
    try:
        with open("actor_stats.json", "r") as f:
            stats = json.load(f)
    except:
        stats = {}
    actor_data = stats.get(user_id, {"movies": 0, "earnings": 0, "hits": 0})
    embed = create_embed(f"🎭 Actor Stats: {target.name}",
                         f"**Movies Acted In:** {actor_data['movies']}\n**Total Earnings:** {format_money(actor_data['earnings'])}\n**Hit Movies:** {actor_data.get('hits', 0)}",
                         discord.Color.purple())
    await ctx.send(embed=embed)

@bot.command(name="topactors", aliases=["actorleaderboard"])
async def top_actors(ctx):
    if not hasattr(bot, 'actor_stats') or not bot.actor_stats:
        return await ctx.send("📭 No actor stats available yet. Actors need to participate in hit movies first.")
    actors_list = []
    for uid, data in bot.actor_stats.items():
        hits = data.get("hits", 0)
        if hits > 0:
            actors_list.append((uid, hits, data.get("earnings", 0)))
    if not actors_list:
        return await ctx.send("📭 No actors have hit any movies yet.")
    actors_list.sort(key=lambda x: x[1], reverse=True)
    top10 = actors_list[:10]
    embed = create_embed("🏆 Top Actors by Hit Movies", "", discord.Color.gold())
    medals = ["🥇", "🥈", "🥉"]
    for i, (uid, hits, earnings) in enumerate(top10, 1):
        try:
            user = await bot.fetch_user(int(uid))
            name = user.display_name
        except:
            name = f"<@{uid}>"
        prefix = medals[i-1] if i <= 3 else f"{i}."
        embed.add_field(
            name=f"{prefix} {name}",
            value=f"🎬 **{hits}** hit movie(s) | 💰 {format_money(earnings)} total earnings",
            inline=False
        )
    await ctx.send(embed=embed)
    
    


# ==================== MAKE MOVIE ====================
@bot.command(name="makemovie", aliases=["movie"])
async def make_movie(ctx, budget: str, actors_salary: str, title: str, *actors: discord.Member):
    try:
        budget_num = parse_money_amount(budget)
        actors_salary_num = parse_money_amount(actors_salary)
    except:
        return await ctx.send("❌ Invalid amount! Use a number or shorthand like 5m (million), 5b (billion), 5t (trillion).")
    
    user_id = str(ctx.author.id)
    if user_id not in bot.studios:
        return await ctx.send("❌ You don't have a studio. Create one with `!create_studio <name>` first.")
    studio_name = bot.studios[user_id]["studio_name"]
    
    if budget_num < 10000:
        return await ctx.send("❌ Minimum total budget is $10,000.")
    if actors_salary_num < 0:
        return await ctx.send("❌ Actors salary cannot be negative.")
    if actors_salary_num > budget_num:
        return await ctx.send(f"❌ Actors salary ({format_money(actors_salary_num)}) cannot exceed total budget ({format_money(budget_num)}).")
    
    wallet = bot.wallets.get(user_id, 0)
    if wallet < budget_num:
        return await ctx.send(f"❌ You need {format_money(budget_num)} to make a movie.")
    
    # Process actors
    actors = list(actors)[:5]
    if actors:
        actors = list(dict.fromkeys(actors))
        if ctx.author in actors:
            actors.remove(ctx.author)
        if len(actors) > 5:
            actors = actors[:5]
    
    confirmed_actors = []
    if actors:
        per_actor_salary = actors_salary_num // len(actors) if actors else 0
        await ctx.send(f"📢 Sending acting offers to {len(actors)} actor(s). Each will receive {format_money(per_actor_salary)}. They have 60 seconds to accept.")
        for actor in actors:
            try:
                await actor.send(f"🎬 {ctx.author.mention} offers you a role in their movie **{title}** with a salary of {format_money(per_actor_salary)}. Do you accept? Reply `yes` or `no` within 60 seconds.")
                def check(m):
                    return m.author == actor and m.content.lower() in ["yes", "no"]
                msg = await bot.wait_for('message', timeout=60.0, check=check)
                if msg.content.lower() == "yes":
                    confirmed_actors.append(actor)
                    await ctx.send(f"✅ {actor.mention} accepted the role.")
                else:
                    await ctx.send(f"❌ {actor.mention} declined.")
            except asyncio.TimeoutError:
                await ctx.send(f"⏰ {actor.mention} did not respond in time.")
    else:
        await ctx.send("ℹ️ No actors were mentioned. Proceeding without actors.")
    
    # Deduct budget
    bot.wallets[user_id] = wallet - budget_num
    save_economy()
    asyncio.create_task(async_save_economy())
    
    # Pay actors
    actual_actors_salary = 0
    if confirmed_actors:
        per_actor = actors_salary_num // len(confirmed_actors)
        for actor in confirmed_actors:
            aid = str(actor.id)
            bot.wallets[aid] = bot.wallets.get(aid, 0) + per_actor
            actual_actors_salary += per_actor
            if not hasattr(bot, 'actor_stats'):
                try:
                    with open("actor_stats.json", "r") as f:
                        bot.actor_stats = json.load(f)
                except:
                    bot.actor_stats = {}
            if aid not in bot.actor_stats:
                bot.actor_stats[aid] = {"movies": 0, "earnings": 0, "hits": 0}
            bot.actor_stats[aid]["movies"] += 1
            bot.actor_stats[aid]["earnings"] += per_actor
            await save_actor_stats()
        remainder = actors_salary_num - actual_actors_salary
        if remainder > 0:
            bot.wallets[user_id] += remainder
    else:
        bot.wallets[user_id] += actors_salary_num
        actual_actors_salary = 0
    
    production_budget = budget_num - actual_actors_salary
    if production_budget < 0:
        production_budget = 0
    
    # Calculate score with actor influence
    base_score = random.randint(40, 100)
    modifier = min(50, production_budget // 1_000_000)
    
    # Actor influence: if actors have 5+ hits, boost score
    actor_boost = 0
    if confirmed_actors:
        actor_hits = 0
        for actor in confirmed_actors:
            actor_hits += get_actor_hits(str(actor.id))
        # Each hit adds 1% boost, max 20%
        actor_boost = min(20, actor_hits)
        modifier += actor_boost
    
    score = min(100, base_score + modifier)
    
    if score >= 60:
        multiplier = 1.5 + (score - 60) / 100
        gross_earnings = int(production_budget * multiplier)
        color = discord.Color.green()
        is_hit = score >= 80
    else:
        gross_earnings = int(production_budget * (score / 100))
        color = discord.Color.red()
        is_hit = False
    
    # Distribute earnings to shareholders
    if user_id in bot.shares["studios"]:
        shares_data = bot.shares["studios"][user_id]
        total_shares = shares_data.get("total_shares", 100)
        for shareholder_id, share_count in shares_data.get("shares", {}).items():
            if shareholder_id != user_id and share_count > 0:
                share_percentage = share_count / total_shares
                share_earnings = int(gross_earnings * share_percentage)
                bot.wallets[shareholder_id] = bot.wallets.get(shareholder_id, 0) + share_earnings
                try:
                    shareholder = await bot.fetch_user(int(shareholder_id))
                    await shareholder.send(f"🎬 Your studio shares earned you {format_money(share_earnings)} from the movie **{title}**!")
                except:
                    pass
    
    # Update studio earnings
    bot.wallets[user_id] += gross_earnings
    net_profit = (gross_earnings + actual_actors_salary) - budget_num
    bot.studios[user_id]["total_earnings"] += gross_earnings
    bot.studios[user_id]["movie_count"] += 1
    save_studios()
    
    # Save movie record
    movie_record = {
        "title": title,
        "studio": studio_name,
        "budget": budget_num,
        "actors_salary": actual_actors_salary,
        "production_budget": production_budget,
        "gross_earnings": gross_earnings,
        "producer": ctx.author.id,
        "producer_name": ctx.author.display_name,
        "actors": [a.id for a in confirmed_actors],
        "score": score,
        "date": datetime.datetime.now().isoformat(),
        "server_id": ctx.guild.id
    }
    bot.movies.append(movie_record)
    save_movies()
    save_economy()
    asyncio.create_task(async_save_economy())
    
    # Awards
    award_date = datetime.datetime.now().strftime("%Y-%m-%d")
    if is_hit and confirmed_actors:
        for actor in confirmed_actors:
            give_actor_award(str(actor.id), "hit", title, award_date)
        await ctx.send(f"🎭 **{len(confirmed_actors)} actor(s)** received the **Ford High Best Actor Award** for this hit movie!")
    
    server_movies = [m for m in bot.movies if m.get("server_id") == ctx.guild.id]
    if len(server_movies) >= 1:
        current_top = max(server_movies, key=lambda x: x["gross_earnings"])
        if current_top["title"] == title and current_top["producer"] == ctx.author.id and current_top["gross_earnings"] == gross_earnings and len(server_movies) > 1:
            if confirmed_actors:
                for actor in confirmed_actors:
                    give_actor_award(str(actor.id), "top", title, award_date)
                await ctx.send(f"🏆 **{len(confirmed_actors)} actor(s)** received the **Ford High Top Movie Award** for starring in the #1 film on the server!")
    
    # Send embed
    embed = discord.Embed(
        title=f"🎬 {title}",
        description=f"**{studio_name} presents**\n*Now in cinemas*",
        color=color
    )
    embed.add_field(name="Rotten Tomatoes Score", value=f"**{score}%** 🍅", inline=True)
    embed.add_field(name="Total Budget", value=format_money(budget_num), inline=True)
    embed.add_field(name="Actors Salary", value=format_money(actual_actors_salary), inline=True)
    embed.add_field(name="Production Budget", value=format_money(production_budget), inline=True)
    embed.add_field(name="Gross Box Office", value=format_money(gross_earnings), inline=True)
    if confirmed_actors:
        embed.add_field(name="Actors", value=", ".join(a.mention for a in confirmed_actors), inline=False)
        if is_hit:
            embed.add_field(name="🏆 Actor Award", value="All actors received **Ford High Best Actor Award**!", inline=False)
    embed.add_field(name="Producer's Net Profit", value=format_money(net_profit), inline=False)
    if hasattr(bot, 'red_carpet_users') and user_id in bot.red_carpet_users:
        del bot.red_carpet_users[user_id]
        car_choice = random.choice(['Rolls Royce Phantom', 'Lamborghini Aventador', 'Ferrari SF90', 'Bugatti Chiron'])
        embed.add_field(name="✨ Red Carpet Arrival", value=f"{ctx.author.mention} arrived in a luxurious **{car_choice}**!", inline=False)
    embed.set_footer(text=f"Produced by {ctx.author.name} • Studio: {studio_name}")
    await ctx.send(embed=embed)

@bot.command(name="topmovies", aliases=["movieleaderboard", "topgrossing"])
async def top_movies(ctx):
    server_movies = [m for m in bot.movies if m.get("server_id") == ctx.guild.id]
    if not server_movies:
        return await ctx.send("📭 No movies have been made in this server yet. Be the first with `!makemovie`!")
    for movie in server_movies:
        if "gross_earnings" not in movie and "earnings" in movie:
            movie["gross_earnings"] = movie["earnings"]
    server_movies.sort(key=lambda x: x.get("gross_earnings", 0), reverse=True)
    top10 = server_movies[:10]
    embed = discord.Embed(title="🏆 Highest Grossing Films", description=f"Top movies in {ctx.guild.name}", color=discord.Color.gold())
    for i, movie in enumerate(top10, 1):
        producer = ctx.guild.get_member(movie["producer"])
        producer_name = producer.display_name if producer else movie.get("producer_name", "Unknown")
        studio = movie.get("studio", "Unknown Studio")
        earnings = movie.get("gross_earnings", movie.get("earnings", 0))
        embed.add_field(
            name=f"{i}. {movie['title']}",
            value=f"**Studio:** {studio}\n**Box Office:** {format_money(earnings)}\n**Producer:** {producer_name}",
            inline=False
        )
    await ctx.send(embed=embed)

@bot.command(name="forceaward")
@commands.has_permissions(administrator=True)
async def force_movie_award(ctx):
    await weekly_movie_award()
    await ctx.send("✅ Movie award check executed.")
    



# ==================== CLAN COMMANDS ====================
def generate_clan_id():
    return str(int(datetime.datetime.now().timestamp() * 1000)) + str(random.randint(1000, 9999))

@bot.command(name="clan_create")
async def clan_create(ctx, *, clan_name: str):
    user_id = str(ctx.author.id)
    for cid, members in bot.clan_members.items():
        if user_id in members:
            return await ctx.send("❌ You are already in a clan. Leave your current clan first.")
    for cid, data in bot.clans.items():
        if data["clan_name"].lower() == clan_name.lower():
            return await ctx.send("❌ A clan with that name already exists.")
    wallet = bot.wallets.get(user_id, 0)
    cost = 100000
    if wallet < cost:
        return await ctx.send(f"❌ You need {format_money(cost)} to create a clan.")
    try:
        role = await ctx.guild.create_role(name=clan_name, mentionable=True, reason=f"Clan creation by {ctx.author}")
    except discord.Forbidden:
        return await ctx.send("❌ I don't have permission to create roles.")
    bot.wallets[user_id] = wallet - cost
    save_economy()
    asyncio.create_task(async_save_economy())
    clan_id = generate_clan_id()
    bot.clans[clan_id] = {
        "clan_name": clan_name,
        "role_id": role.id,
        "leader_id": user_id,
        "created_at": datetime.datetime.now().isoformat()
    }
    bot.clan_members[clan_id] = [user_id]
    save_clans()
    save_clan_members()
    await ctx.author.add_roles(role)
    await update_clan_nickname(ctx.author, clan_name)
    embed = create_embed(
        "🏰 Clan Created!",
        f"**Clan Name:** {clan_name}\n**Role:** {role.mention}\n**Cost:** {format_money(cost)}\nYour nickname has been updated with the clan tag.\nUse `!clan_invite @user` to invite members.\nUse `!clan_info {clan_name}` to see details.",
        discord.Color.green()
    )
    await ctx.send(embed=embed)

@bot.command(name="clan_invite")
async def clan_invite(ctx, member: discord.Member):
    if member.bot or member == ctx.author:
        return await ctx.send("❌ Invalid target.")
    user_id = str(ctx.author.id)
    clan_id = None
    for cid, members in bot.clan_members.items():
        if user_id in members:
            clan_id = cid
            break
    if not clan_id:
        return await ctx.send("❌ You are not in a clan.")
    clan = bot.clans[clan_id]
    if clan["leader_id"] != user_id:
        return await ctx.send("❌ Only the clan leader can send invites.")
    target_id = str(member.id)
    for cid, members in bot.clan_members.items():
        if target_id in members:
            return await ctx.send(f"❌ {member.mention} is already in a clan.")
    bot.clan_invites[target_id] = {
        "clan_id": clan_id,
        "invited_by": user_id,
        "created_at": datetime.datetime.now().isoformat()
    }
    save_clan_invites()
    try:
        await member.send(f"📩 You have been invited to join the clan **{clan['clan_name']}** by {ctx.author.display_name}.\nUse `!clan_accept` in the server to accept.")
        await ctx.send(f"✅ Invite sent to {member.mention}.")
    except discord.Forbidden:
        await ctx.send(f"⚠️ Could not DM {member.mention}. Invite still pending.")

@bot.command(name="clan_accept")
async def clan_accept(ctx):
    user_id = str(ctx.author.id)
    if user_id not in bot.clan_invites:
        return await ctx.send("❌ You have no pending clan invites.")
    invite = bot.clan_invites[user_id]
    clan_id = invite["clan_id"]
    clan = bot.clans.get(clan_id)
    if not clan:
        await ctx.send("❌ The clan no longer exists. Invite invalid.")
        del bot.clan_invites[user_id]
        save_clan_invites()
        return
    role = ctx.guild.get_role(clan["role_id"])
    if not role:
        return await ctx.send("❌ The clan role no longer exists. Contact an admin.")
    for cid, members in bot.clan_members.items():
        if user_id in members:
            return await ctx.send("❌ You are already in a clan. Leave first.")
    if clan_id not in bot.clan_members:
        bot.clan_members[clan_id] = []
    bot.clan_members[clan_id].append(user_id)
    await ctx.author.add_roles(role)
    await update_clan_nickname(ctx.author, clan["clan_name"])
    del bot.clan_invites[user_id]
    save_clan_members()
    save_clan_invites()
    embed = create_embed("✅ Joined Clan", f"You have joined **{clan['clan_name']}**! Your nickname has been updated.", discord.Color.green())
    await ctx.send(embed=embed)

@bot.command(name="clan_info")
async def clan_info(ctx, *, clan_name: str = None):
    if clan_name:
        clan_id = None
        for cid, data in bot.clans.items():
            if data["clan_name"].lower() == clan_name.lower():
                clan_id = cid
                break
        if not clan_id:
            return await ctx.send("❌ Clan not found.")
    else:
        user_id = str(ctx.author.id)
        clan_id = None
        for cid, members in bot.clan_members.items():
            if user_id in members:
                clan_id = cid
                break
        if not clan_id:
            return await ctx.send("❌ You are not in a clan. Specify a clan name.")
    clan = bot.clans[clan_id]
    members = bot.clan_members.get(clan_id, [])
    member_mentions = []
    for uid in members[:20]:
        user = ctx.guild.get_member(int(uid))
        if user:
            member_mentions.append(user.mention)
        else:
            member_mentions.append(f"<@{uid}>")
    leader = ctx.guild.get_member(int(clan["leader_id"]))
    leader_mention = leader.mention if leader else f"<@{clan['leader_id']}>"
    embed = create_embed(
        f"🏰 Clan: {clan['clan_name']}",
        f"**Leader:** {leader_mention}\n**Member Count:** {len(members)}\n**Created:** {datetime.datetime.fromisoformat(clan['created_at']).strftime('%Y-%m-%d')}\n**Members:** {', '.join(member_mentions[:10])}" + ("..." if len(members) > 10 else ""),
        discord.Color.blue()
    )
    await ctx.send(embed=embed)

@bot.command(name="clan_leave")
async def clan_leave(ctx):
    user_id = str(ctx.author.id)
    clan_id = None
    for cid, members in bot.clan_members.items():
        if user_id in members:
            clan_id = cid
            break
    if not clan_id:
        return await ctx.send("❌ You are not in a clan.")
    clan = bot.clans[clan_id]
    if clan["leader_id"] == user_id:
        return await ctx.send("❌ The leader cannot leave. Use `!clan_transfer` to give leadership, or `!clan_disband` to delete the clan.")
    bot.clan_members[clan_id].remove(user_id)
    if not bot.clan_members[clan_id]:
        del bot.clan_members[clan_id]
    role = ctx.guild.get_role(clan["role_id"])
    if role:
        await ctx.author.remove_roles(role)
    await update_clan_nickname(ctx.author, None)
    save_clan_members()
    embed = create_embed("👋 Left Clan", f"You have left **{clan['clan_name']}**. Your nickname has been restored.", discord.Color.orange())
    await ctx.send(embed=embed)

@bot.command(name="clan_kick")
async def clan_kick(ctx, member: discord.Member):
    user_id = str(ctx.author.id)
    clan_id = None
    for cid, members in bot.clan_members.items():
        if user_id in members:
            clan_id = cid
            break
    if not clan_id:
        return await ctx.send("❌ You are not in a clan.")
    clan = bot.clans[clan_id]
    if clan["leader_id"] != user_id:
        return await ctx.send("❌ Only the clan leader can kick members.")
    target_id = str(member.id)
    if target_id not in bot.clan_members.get(clan_id, []):
        return await ctx.send(f"❌ {member.mention} is not in your clan.")
    if target_id == user_id:
        return await ctx.send("❌ Use `!clan_leave` to leave yourself.")
    bot.clan_members[clan_id].remove(target_id)
    if not bot.clan_members[clan_id]:
        del bot.clan_members[clan_id]
    role = ctx.guild.get_role(clan["role_id"])
    if role:
        await member.remove_roles(role)
    await update_clan_nickname(member, None)
    save_clan_members()
    embed = create_embed("🥾 Member Kicked", f"{member.mention} has been kicked from **{clan['clan_name']}**. Their nickname has been restored.", discord.Color.red())
    await ctx.send(embed=embed)

@bot.command(name="clan_transfer")
async def clan_transfer(ctx, new_leader: discord.Member):
    user_id = str(ctx.author.id)
    clan_id = None
    for cid, members in bot.clan_members.items():
        if user_id in members:
            clan_id = cid
            break
    if not clan_id:
        return await ctx.send("❌ You are not in a clan.")
    clan = bot.clans[clan_id]
    if clan["leader_id"] != user_id:
        return await ctx.send("❌ Only the current leader can transfer leadership.")
    target_id = str(new_leader.id)
    if target_id not in bot.clan_members.get(clan_id, []):
        return await ctx.send(f"❌ {new_leader.mention} is not a member of your clan.")
    clan["leader_id"] = target_id
    save_clans()
    embed = create_embed("👑 Leadership Transferred", f"{ctx.author.mention} transferred leadership of **{clan['clan_name']}** to {new_leader.mention}.", discord.Color.gold())
    await ctx.send(embed=embed)

@bot.command(name="clan_disband")
async def clan_disband(ctx):
    user_id = str(ctx.author.id)
    clan_id = None
    for cid, members in bot.clan_members.items():
        if user_id in members:
            clan_id = cid
            break
    if not clan_id:
        return await ctx.send("❌ You are not in a clan.")
    clan = bot.clans[clan_id]
    if clan["leader_id"] != user_id:
        return await ctx.send("❌ Only the clan leader can disband the clan.")
    await ctx.send(f"⚠️ Are you sure you want to disband **{clan['clan_name']}**? This will delete the clan role and kick all members. Type `!confirm_disband` within 30 seconds.")
    def check(m):
        return m.author == ctx.author and m.content.lower() == "!confirm_disband" and m.channel == ctx.channel
    try:
        await bot.wait_for('message', timeout=30.0, check=check)
    except asyncio.TimeoutError:
        return await ctx.send("❌ Disband cancelled.")
    role = ctx.guild.get_role(clan["role_id"])
    members = bot.clan_members.get(clan_id, []).copy()
    if role:
        for member_id in members:
            member = ctx.guild.get_member(int(member_id))
            if member:
                await member.remove_roles(role)
                await update_clan_nickname(member, None)
        await role.delete()
    del bot.clans[clan_id]
    if clan_id in bot.clan_members:
        del bot.clan_members[clan_id]
    to_delete = []
    for inv_user, inv_data in bot.clan_invites.items():
        if inv_data["clan_id"] == clan_id:
            to_delete.append(inv_user)
    for inv_user in to_delete:
        del bot.clan_invites[inv_user]
    save_clans()
    save_clan_members()
    save_clan_invites()
    embed = create_embed("💀 Clan Disbanded", f"**{clan['clan_name']}** has been disbanded. All members' nicknames have been restored.", discord.Color.red())
    await ctx.send(embed=embed)

@bot.command(name="clan_list")
async def clan_list(ctx):
    if not bot.clans:
        return await ctx.send("📭 No clans have been created yet.")
    embed = create_embed("📜 Clan List", f"Total clans: {len(bot.clans)}", discord.Color.blue())
    for clan_id, data in bot.clans.items():
        leader = ctx.guild.get_member(int(data["leader_id"]))
        leader_name = leader.display_name if leader else f"<@{data['leader_id']}>"
        member_count = len(bot.clan_members.get(clan_id, []))
        embed.add_field(name=data["clan_name"], value=f"Leader: {leader_name}\nMembers: {member_count}", inline=False)
    await ctx.send(embed=embed)
    
    

# ==================== RULES COMMAND ====================
@bot.command(name="rules")
async def rules(ctx):
    """Display the server rules."""
    embed = discord.Embed(title="📜 **Ford High Server Constitution**", color=discord.Color.blue())
    embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/190/190411.png")
    rules_text = """
✅ **Article 1: Respect & Civility**
All members shall conduct themselves with dignity, respect, and courtesy toward others. 
Harassment, hate speech, discrimination, or personal attacks are strictly prohibited.

✅ **Article 2: Privacy & Security**
The sharing of personal information (doxing) is forbidden. This includes addresses, 
phone numbers, private social media, or any identifying information without consent.

✅ **Article 3: Appropriate Content**
All content must be suitable for a public forum. No NSFW/NSFL material, explicit content, 
or excessively graphic imagery is permitted.

✅ **Article 4: Spam & Self-Promotion**
Excessive messaging, advertisement, or unsolicited promotion is prohibited. 
Use designated channels for sharing content.

✅ **Article 5: Channel Purpose**
Use channels for their designated purposes. Keep discussions organized and on-topic.

✅ **Article 6: Conflict Resolution**
Address disputes privately or through official channels. Do not engage in public arguments 
or drama.

✅ **Article 7: Role Respect**
Respect the authority structure. Decisions by the Founder, co Founder, President, Vice President, 
Chief of staff and the prime minister are final in administrative matters.

✅ **Article 8: Moderation Compliance**
Comply with moderator instructions. If you disagree with a moderation action, 
appeal through proper channels (#appeals or direct message).

✅ **Article 9: Policy Suggestions**
Constructive feedback is welcome in designated channels. Follow proper procedures 
for suggesting changes.

✅ **Article 10: Account Responsibility**
You are responsible for your account's activity. Shared or compromised accounts 
remain your responsibility.

✅ **Article 11: Age Requirement**
All members must be 13+ per Discord's Terms of Service. Violation results in 
immediate removal.

✅ **Article 12: Alt Accounts**
Multiple accounts are discouraged. Using alts to evade punishment will result 
in all associated accounts being banned.

✅ **Article 13: Controversial Subject Restriction**
Discussions of religion, intense political debates, and other potentially divisive 
topics are prohibited in public channels. These discussions often lead to conflict 
and disrupt community harmony.
"""
    embed.description = rules_text
    embed.set_footer(text=f"Requested by {ctx.author.name} | Ford High")
    await ctx.send(embed=embed)

# ==================== BIRTHDAY SYSTEM ====================
@bot.command(name="setbirthday")
async def set_birthday(ctx, date: str):
    """Set your birthday (format: MM-DD or YYYY-MM-DD)."""
    try:
        if len(date) <= 5:
            month, day = map(int, date.split('-'))
            birthday = f"{datetime.datetime.now().year:04d}-{month:02d}-{day:02d}"
        else:
            birthday = date
        datetime.datetime.strptime(birthday, "%Y-%m-%d")
    except:
        return await ctx.send("❌ Invalid date format. Use `MM-DD` or `YYYY-MM-DD`.")
    
    user_id = str(ctx.author.id)
    bot.birthdays[user_id] = birthday
    save_birthdays()
    await ctx.send(f"✅ Your birthday has been set to **{birthday}**!")

@bot.command(name="birthday")
async def birthday(ctx, member: discord.Member = None):
    """Check someone's birthday."""
    target = member or ctx.author
    user_id = str(target.id)
    birthday = bot.birthdays.get(user_id)
    if not birthday:
        if member:
            return await ctx.send(f"❌ {target.display_name} hasn't set their birthday yet.")
        else:
            return await ctx.send("❌ You haven't set your birthday. Use `!setbirthday MM-DD`.")
    embed = discord.Embed(title=f"🎂 {target.display_name}'s Birthday", color=discord.Color.gold())
    embed.add_field(name="Birthday", value=birthday, inline=True)
    await ctx.send(embed=embed)

@bot.command(name="setbirthdaywish")
@commands.has_permissions(administrator=True)
async def set_birthday_wish(ctx, *, wish: str):
    """Set the birthday wish message. Admin only."""
    bot.birthday_config["wish"] = wish
    save_birthday_config()
    await ctx.send(f"✅ Birthday wish set to: **{wish}**")

@bot.command(name="setbirthdayrole")
@commands.has_permissions(administrator=True)
async def set_birthday_role(ctx, role_name: str):
    """Set the role given to members on their birthday. Admin only."""
    role = discord.utils.get(ctx.guild.roles, name=role_name)
    if not role:
        for r in ctx.guild.roles:
            if r.name.lower() == role_name.lower():
                role = r
                break
    if not role:
        return await ctx.send(f"❌ Role `{role_name}` not found.")
    bot.birthday_config["role_name"] = role_name
    save_birthday_config()
    await ctx.send(f"✅ Birthday role set to **{role_name}**.")

# ==================== BIRTHDAY CHECKER TASK ====================
@tasks.loop(hours=1)
async def check_birthdays():
    """Check for birthdays every hour using each user's timezone."""
    now = datetime.datetime.now()
    today = now.strftime("%m-%d")
    
    bot.birthdays = load_birthdays()
    config = load_birthday_config()
    
    if not hasattr(bot, 'birthday_announced'):
        bot.birthday_announced = {}
    
    for user_id, birthday in bot.birthdays.items():
        birthday_date = datetime.datetime.strptime(birthday, "%Y-%m-%d")
        birthday_md = birthday_date.strftime("%m-%d")
        
        if birthday_md == today:
            if user_id in bot.birthday_announced:
                continue
            
            tz_name = bot.user_timezones.get(user_id)
            if tz_name:
                try:
                    tz = zoneinfo.ZoneInfo(tz_name)
                    now_local = datetime.datetime.now(tz)
                    if now_local.hour < 6:
                        continue
                except:
                    pass
            
            for guild in bot.guilds:
                member = guild.get_member(int(user_id))
                if member:
                    role_name = config.get("role_name", "Birthday")
                    role = discord.utils.get(guild.roles, name=role_name)
                    if role and role not in member.roles:
                        try:
                            await member.add_roles(role, reason="Birthday!")
                        except:
                            pass
                    
                    general = discord.utils.get(guild.text_channels, name="general")
                    if not general:
                        general = guild.system_channel
                    if general:
                        wish = config.get("wish", "🎉 Happy Birthday! Have an amazing day!")
                        embed = discord.Embed(
                            title="🎂 Happy Birthday!",
                            description=f"Please wish **{member.mention}** a happy birthday!\n\n{wish}",
                            color=discord.Color.gold()
                        )
                        if member.avatar:
                            embed.set_thumbnail(url=member.avatar.url)
                        await general.send("@everyone", embed=embed)
            
            bot.birthday_announced[user_id] = today
            
            


# ==================== ELECTION SYSTEM ====================
@bot.command(name="startelection")
@commands.has_permissions(administrator=True)
async def start_election(ctx, role_name: str, entry_fee: str = "10000"):
    if ctx.guild.id in bot.elections and bot.elections[ctx.guild.id].get("active", False):
        return await ctx.send("❌ An election is already running in this server!")
    
    try:
        fee = parse_money_amount(entry_fee)
    except:
        return await ctx.send("❌ Invalid entry fee! Use a number or shorthand like 5m (million), 5b (billion).")
    
    role = discord.utils.get(ctx.guild.roles, name=role_name)
    if not role:
        for r in ctx.guild.roles:
            if r.name.lower() == role_name.lower():
                role = r
                break
    if not role:
        return await ctx.send(f"❌ Role `{role_name}` not found.")
    
    bot.elections[ctx.guild.id] = {
        "active": True,
        "role_name": role_name,
        "role_id": role.id,
        "entry_fee": fee,
        "candidates": {},
        "votes": {},
        "started_by": ctx.author.id,
        "started_at": datetime.datetime.now().isoformat(),
        "contest_deadline": None,
        "voting_deadline": None,
        "phase": "registration",
        "winner": None
    }
    save_elections()
    
    embed = create_embed(
        f"🗳️ Election Started: {role_name}",
        f"**Entry Fee:** {format_money(fee)}\n"
        f"**To contest:** `!contest` (you pay the entry fee)\n"
        f"**Registration Deadline:** 2 minutes after first contestant\n\n"
        f"Members have 2 minutes to register as candidates once the first person contests!",
        discord.Color.blue()
    )
    await ctx.send(embed=embed)

@bot.command(name="setelectionfee")
@commands.has_permissions(administrator=True)
async def set_election_fee(ctx, amount: str):
    election = bot.elections.get(ctx.guild.id)
    if not election or not election.get("active", False):
        return await ctx.send("❌ No active election in this server.")
    
    try:
        fee = parse_money_amount(amount)
    except:
        return await ctx.send("❌ Invalid amount! Use a number or shorthand like 5m (million), 5b (billion).")
    
    if fee <= 0:
        return await ctx.send("❌ Entry fee must be positive.")
    
    election["entry_fee"] = fee
    save_elections()
    await ctx.send(f"✅ Election entry fee set to {format_money(fee)}.")

@bot.command(name="contest")
async def contest(ctx):
    election = bot.elections.get(ctx.guild.id)
    if not election or not election.get("active", False):
        return await ctx.send("❌ No active election in this server.")
    
    if election["phase"] == "ended":
        return await ctx.send("❌ This election has already ended.")
    
    user_id = str(ctx.author.id)
    
    if user_id in election["candidates"]:
        return await ctx.send("❌ You are already a candidate!")
    
    fee = election.get("entry_fee", 10000)
    wallet = bot.wallets.get(user_id, 0)
    if wallet < fee:
        return await ctx.send(f"❌ You need {format_money(fee)} to enter the election.")
    
    bot.wallets[user_id] = wallet - fee
    save_economy()
    asyncio.create_task(async_save_economy())
    
    election["candidates"][user_id] = ctx.author.display_name
    election["votes"][user_id] = 0
    
    if not election["contest_deadline"]:
        deadline = datetime.datetime.now() + datetime.timedelta(minutes=2)
        election["contest_deadline"] = deadline.isoformat()
        save_elections()
        await ctx.send(f"⏰ Registration is now open! Candidates have until {deadline.strftime('%H:%M:%S')} to enter with `!contest`.")
    
    save_elections()
    await ctx.send(f"✅ {ctx.author.mention} has entered the election as a candidate!")

@bot.command(name="electionstatus")
async def election_status(ctx):
    election = bot.elections.get(ctx.guild.id)
    if not election or not election.get("active", False):
        return await ctx.send("❌ No active election in this server.")
    
    embed = discord.Embed(
        title=f"🗳️ Election Status: {election['role_name']}",
        color=discord.Color.blue()
    )
    embed.add_field(name="Phase", value=election["phase"].capitalize(), inline=True)
    embed.add_field(name="Entry Fee", value=format_money(election.get("entry_fee", 10000)), inline=True)
    embed.add_field(name="Candidates", value=str(len(election["candidates"])), inline=True)
    
    if election["phase"] == "registration":
        deadline = election.get("contest_deadline")
        if deadline:
            remaining = datetime.datetime.fromisoformat(deadline) - datetime.datetime.now()
            embed.add_field(name="Registration Closes", value=f"{max(0, remaining.seconds // 60)}m {max(0, remaining.seconds % 60)}s", inline=False)
    
    if election["phase"] == "voting":
        deadline = election.get("voting_deadline")
        if deadline:
            remaining = datetime.datetime.fromisoformat(deadline) - datetime.datetime.now()
            embed.add_field(name="Voting Closes", value=f"{max(0, remaining.seconds // 60)}m {max(0, remaining.seconds % 60)}s", inline=False)
    
    if election["candidates"]:
        candidates_list = []
        for uid, name in election["candidates"].items():
            votes = election.get("votes", {}).get(uid, 0)
            try:
                user = await bot.fetch_user(int(uid))
                mention = user.mention
            except:
                mention = f"<@{uid}>"
            candidates_list.append(f"{mention}: {votes} votes")
        embed.add_field(name="Candidates", value="\n".join(candidates_list) if candidates_list else "None", inline=False)
    
    await ctx.send(embed=embed)

@bot.command(name="vote")
async def vote(ctx, *, candidate: discord.Member = None):
    if not candidate:
        return await ctx.send("❌ Please mention the candidate you want to vote for. Example: `!vote @Username`")
    
    election = bot.elections.get(ctx.guild.id)
    if not election or not election.get("active", False):
        return await ctx.send("❌ No active election in this server.")
    
    if election["phase"] != "voting":
        return await ctx.send("❌ Voting has not started yet. Wait for the registration period to end.")
    
    if election["phase"] == "ended":
        return await ctx.send("❌ This election has already ended.")
    
    voter_id = str(ctx.author.id)
    candidate_id = str(candidate.id)
    
    if voter_id in election["candidates"]:
        return await ctx.send("❌ Candidates cannot vote for themselves or others.")
    
    if "voted_users" not in election:
        election["voted_users"] = []
    if voter_id in election["voted_users"]:
        return await ctx.send("❌ You have already voted in this election.")
    
    if candidate_id not in election["candidates"]:
        return await ctx.send(f"❌ {candidate.display_name} is not a candidate in this election.")
    
    election["votes"][candidate_id] = election["votes"].get(candidate_id, 0) + 1
    election["voted_users"].append(voter_id)
    save_elections()
    
    await ctx.send(f"🗳️ Thank you for voting, {ctx.author.mention}! Your vote for **{candidate.display_name}** has been recorded.")

@bot.command(name="endelection")
@commands.has_permissions(administrator=True)
async def end_election(ctx):
    election = bot.elections.get(ctx.guild.id)
    if not election or not election.get("active", False):
        return await ctx.send("❌ No active election in this server.")
    
    if election["phase"] == "ended":
        return await ctx.send("❌ This election has already ended.")
    
    if not election["votes"]:
        return await ctx.send("❌ No votes were cast in this election.")
    
    winner_id = max(election["votes"], key=election["votes"].get)
    winner_votes = election["votes"][winner_id]
    
    role = ctx.guild.get_role(election["role_id"])
    if role:
        try:
            winner = ctx.guild.get_member(int(winner_id))
            if winner:
                await winner.add_roles(role, reason="Elected")
                await ctx.send(f"🎉 Congratulations {winner.mention}! You have been elected as **{election['role_name']}** with {winner_votes} votes!")
            else:
                await ctx.send(f"⚠️ Could not find the winner in the server.")
        except discord.Forbidden:
            await ctx.send("⚠️ I don't have permission to assign the role.")
    else:
        await ctx.send(f"⚠️ The role `{election['role_name']}` no longer exists.")
    
    election["phase"] = "ended"
    election["winner"] = winner_id
    election["active"] = False
    save_elections()
    
    embed = create_embed(
        "🏆 Election Results",
        f"**Role:** {election['role_name']}\n"
        f"**Winner:** <@{winner_id}>\n"
        f"**Votes:** {winner_votes}\n"
        f"**Total Candidates:** {len(election['candidates'])}",
        discord.Color.gold()
    )
    
    if len(election["candidates"]) > 1:
        runner_up = None
        for uid, votes in sorted(election["votes"].items(), key=lambda x: x[1], reverse=True)[1:2]:
            if uid != winner_id:
                runner_up = uid
                break
        if runner_up:
            embed.add_field(name="Runner-up", value=f"<@{runner_up}>: {election['votes'][runner_up]} votes", inline=False)
    
    await ctx.send(embed=embed)

# ==================== AUTO-CHECK ELECTION TIMERS ====================
@tasks.loop(minutes=1)
async def check_elections():
    for guild_id, election in list(bot.elections.items()):
        if not election.get("active", False) or election.get("phase") == "ended":
            continue
        
        now = datetime.datetime.now()
        
        if election["phase"] == "registration" and election.get("contest_deadline"):
            deadline = datetime.datetime.fromisoformat(election["contest_deadline"])
            if now >= deadline:
                if len(election["candidates"]) < 2:
                    election["active"] = False
                    election["phase"] = "ended"
                    save_elections()
                    guild = bot.get_guild(guild_id)
                    if guild:
                        general = discord.utils.get(guild.text_channels, name="general") or guild.system_channel
                        if general:
                            await general.send(f"❌ Election cancelled: Not enough candidates (need at least 2).")
                    continue
                
                election["phase"] = "voting"
                voting_deadline = now + datetime.timedelta(minutes=5)
                election["voting_deadline"] = voting_deadline.isoformat()
                save_elections()
                
                guild = bot.get_guild(guild_id)
                if guild:
                    general = discord.utils.get(guild.text_channels, name="general") or guild.system_channel
                    if general:
                        candidates_str = ""
                        for uid, name in election["candidates"].items():
                            try:
                                user = await bot.fetch_user(int(uid))
                                candidates_str += f"• {user.mention}\n"
                            except:
                                candidates_str += f"• <@{uid}>\n"
                        embed = create_embed(
                            f"🗳️ Voting is Now Open!",
                            f"**Role:** {election['role_name']}\n"
                            f"**Candidates:**\n{candidates_str}\n"
                            f"**Voting Deadline:** {voting_deadline.strftime('%H:%M:%S')} (5 minutes)\n\n"
                            f"Cast your vote with `!vote @candidate`",
                            discord.Color.gold()
                        )
                        await general.send(embed=embed)
        
        if election["phase"] == "voting" and election.get("voting_deadline"):
            deadline = datetime.datetime.fromisoformat(election["voting_deadline"])
            if now >= deadline:
                guild = bot.get_guild(guild_id)
                if guild:
                    channel = discord.utils.get(guild.text_channels, name="general") or guild.system_channel
                    if channel:
                        if not election["votes"]:
                            await channel.send("❌ No votes were cast in this election.")
                            election["active"] = False
                            election["phase"] = "ended"
                            save_elections()
                            continue
                        
                        winner_id = max(election["votes"], key=election["votes"].get)
                        winner_votes = election["votes"][winner_id]
                        
                        role = guild.get_role(election["role_id"])
                        if role:
                            try:
                                winner = guild.get_member(int(winner_id))
                                if winner:
                                    await winner.add_roles(role, reason="Elected")
                                    await channel.send(f"🎉 Congratulations {winner.mention}! You have been elected as **{election['role_name']}** with {winner_votes} votes!")
                            except:
                                pass
                        
                        election["phase"] = "ended"
                        election["winner"] = winner_id
                        election["active"] = False
                        save_elections()
                        
                        embed = create_embed(
                            "🏆 Election Results",
                            f"**Role:** {election['role_name']}\n"
                            f"**Winner:** <@{winner_id}>\n"
                            f"**Votes:** {winner_votes}\n"
                            f"**Total Candidates:** {len(election['candidates'])}",
                            discord.Color.gold()
                        )
                        await channel.send(embed=embed)
                        
                        


# ==================== BACKGROUND TASKS ====================

@tasks.loop(hours=24)
async def weekly_salaries():
    """Automatic salary payment every 24 hours (weekly cycle but runs daily)."""
    now = datetime.datetime.now()
    try:
        with open(LAST_SALARY_FILE, "r") as f:
            last_data = json.load(f)
        last_time_str = last_data.get("last_salary", "2000-01-01T00:00:00")
        last_time = datetime.datetime.fromisoformat(last_time_str)
    except:
        last_time = datetime.datetime.now() - datetime.timedelta(days=7)
    
    if (now - last_time).days < 7:
        return
    
    total = 0
    count = 0
    pending_tax = {}
    for guild in bot.guilds:
        for member in guild.members:
            if not member.bot:
                user_id = str(member.id)
                salary = bot.role_salaries.get("default", 1000)
                for role in member.roles:
                    if role.name in bot.role_salaries and bot.role_salaries[role.name] > salary:
                        salary = bot.role_salaries[role.name]
                weekly = salary * 7
                tax_rate = 5
                if hasattr(bot, 'role_tax_rates'):
                    for role in member.roles:
                        if role.name in bot.role_tax_rates:
                            tax_rate = max(tax_rate, bot.role_tax_rates[role.name])
                tax = int(weekly * tax_rate / 100)
                net = weekly - tax
                bot.banks[user_id] = bot.banks.get(user_id, 0) + net
                if tax > 0:
                    pending_tax[user_id] = pending_tax.get(user_id, 0) + tax
                total += weekly
                count += 1
    
    if not hasattr(bot, 'pending_tax'):
        bot.pending_tax = {}
    for uid, tax in pending_tax.items():
        bot.pending_tax[uid] = bot.pending_tax.get(uid, 0) + tax
    save_pending_tax()
    save_economy()
    asyncio.create_task(async_save_economy())
    save_last_salary(now.isoformat())
    print(f"💰 Automatic weekly salaries paid: {count} users, total {format_money(total)}")

@tasks.loop(minutes=1)
async def check_muted_users():
    """Check for expired mutes and unmute users."""
    now = datetime.datetime.now()
    to_unmute = []
    for user_id, data in list(bot.muted_users.items()):
        unmute_at = datetime.datetime.fromisoformat(data["unmute_at"])
        if now >= unmute_at:
            to_unmute.append(user_id)
    for uid in to_unmute:
        guild = bot.get_guild(bot.muted_users[uid].get("guild_id"))
        if guild:
            member = guild.get_member(int(uid))
            if member:
                mute_role = discord.utils.get(guild.roles, name="Muted")
                if mute_role and mute_role in member.roles:
                    try:
                        await member.remove_roles(mute_role)
                        print(f"🔊 Auto-unmuted {member.name}")
                    except:
                        pass
        del bot.muted_users[uid]
    if to_unmute:
        save_data()

@tasks.loop(hours=24)
async def business_profits():
    """Automatic business profit collection for all businesses every 24 hours."""
    now = datetime.datetime.now()
    for user_id, business in bot.businesses.items():
        if business.get("last_profit"):
            last_time = datetime.datetime.fromisoformat(business["last_profit"])
            if (now - last_time).total_seconds() >= 86400:
                daily_profit = int(business["investment"] * business["profit_rate"])
                business["total_profit"] += daily_profit
                business["last_profit"] = now.isoformat()
                distribute_business_profit(user_id, daily_profit)
    save_businesses()
    save_economy()
    asyncio.create_task(async_save_economy())
    save_shares()

@tasks.loop(hours=24)
async def weekly_movie_award():
    """Weekly movie award - gives award to highest grossing movie in each server."""
    last_award_str = load_last_movie_award()
    last_award = datetime.datetime.fromisoformat(last_award_str)
    if (datetime.datetime.now() - last_award).days < 7:
        return
    
    for guild in bot.guilds:
        server_movies = [m for m in bot.movies if m.get("server_id") == guild.id]
        if not server_movies:
            continue
        top_movie = max(server_movies, key=lambda x: x["gross_earnings"])
        producer_id = str(top_movie["producer"])
        if producer_id not in bot.owned_items:
            bot.owned_items[producer_id] = {}
        if "awards" not in bot.owned_items[producer_id]:
            bot.owned_items[producer_id]["awards"] = []
        award_name = f"🏆 Ford High Best Movie Award ({top_movie['title']} - {datetime.datetime.now().strftime('%Y-%m-%d')})"
        if award_name not in bot.owned_items[producer_id]["awards"]:
            bot.owned_items[producer_id]["awards"].append(award_name)
        save_economy()
        asyncio.create_task(async_save_economy())
        general = discord.utils.get(guild.text_channels, name="general")
        if not general:
            general = guild.system_channel
        if general:
            embed = create_embed(
                "🏆 Weekly Movie Award",
                f"The highest grossing movie this week is **{top_movie['title']}** by <@{producer_id}> with {format_money(top_movie['gross_earnings'])}!\n\nCongratulations!",
                discord.Color.gold()
            )
            await general.send(embed=embed)
    
    save_last_movie_award(datetime.datetime.now().isoformat())

@tasks.loop(hours=24)
async def check_loan_defaults():
    loans = load_loans_adv()
    now = datetime.datetime.now()
    updated = False
    for uid, loan in loans.items():
        if not loan.get("repaid", False) and now > datetime.datetime.fromisoformat(loan["due_date"]):
            interest = int(loan["principal"] * loan["interest_rate"])
            wallet = bot.wallets.get(uid, 0)
            bank = bot.banks.get(uid, 0)
            if wallet + bank >= interest:
                if wallet >= interest:
                    bot.wallets[uid] = wallet - interest
                else:
                    rem = interest - wallet
                    bot.wallets[uid] = 0
                    bot.banks[uid] = bank - rem
                loan["due_date"] = (now + datetime.timedelta(days=7)).isoformat()
                try:
                    user = await bot.fetch_user(int(uid))
                    await user.send(f"⚠️ Your loan interest of {format_money(interest)} was automatically deducted. New due date: {loan['due_date']}")
                except:
                    pass
            else:
                owned = bot.owned_items.get(uid, {})
                seized = None
                for cat, items in owned.items():
                    if cat.lower() in ["vehicles", "aircraft"] and items:
                        seized_item = items[0]
                        owned[cat].remove(seized_item)
                        if not owned[cat]:
                            del owned[cat]
                        seized = seized_item
                        break
                if seized:
                    bot.owned_items[uid] = owned
                    save_economy()
                    try:
                        user = await bot.fetch_user(int(uid))
                        await user.send(f"💀 Your loan defaulted! A repo drone seized your {seized}.")
                    except:
                        pass
                    loan["repaid"] = True
                else:
                    loan["principal"] = int(loan["principal"] * 1.10)
                    loan["due_date"] = (now + datetime.timedelta(days=7)).isoformat()
                    try:
                        user = await bot.fetch_user(int(uid))
                        await user.send(f"⚠️ You have no assets to seize! Your debt increased by 10%. New amount: {format_money(loan['principal'])}")
                    except:
                        pass
            updated = True
    if updated:
        save_economy()
        asyncio.create_task(async_save_economy())
        save_loans_adv(loans)

@tasks.loop(hours=24)
async def check_tax_punishments():
    """Check if users have unpaid tax and report to mods."""
    now = datetime.datetime.now()
    for user_id, tax in list(bot.pending_tax.items()):
        if tax > 100000:
            if user_id in bot.tax_punishments and (now - datetime.datetime.fromisoformat(bot.tax_punishments[user_id])) < datetime.timedelta(days=3):
                continue
            for guild in bot.guilds:
                mod_channel = discord.utils.get(guild.text_channels, name="mod-logs") or discord.utils.get(guild.text_channels, name="staff-logs")
                if not mod_channel:
                    mod_channel = guild.system_channel
                if mod_channel:
                    try:
                        user = await bot.fetch_user(int(user_id))
                        await mod_channel.send(f"⚠️ **Tax Alert** – {user.mention} has unpaid tax of {format_money(tax)}. Please remind them to pay with `!pay_tax`.")
                        bot.tax_punishments[user_id] = now.isoformat()
                        save_tax_punishments()
                    except:
                        pass
                        
                        

# ==================== LOAN COMMANDS ====================
@bot.command(name="take_loan")
async def take_loan_adv(ctx, amount: str):
    try:
        amount_num = parse_money_amount(amount)
    except:
        return await ctx.send("❌ Invalid amount! Use a number or shorthand like 5m (million), 5b (billion), 5t (trillion).")
    if amount_num <= 0:
        return await ctx.send("❌ Amount must be positive.")
    user_id = str(ctx.author.id)
    net = bot.wallets.get(user_id, 0) + bot.banks.get(user_id, 0)
    max_loan = int(net * 0.5)
    if amount_num > max_loan:
        return await ctx.send(f"❌ Loan amount cannot exceed {format_money(max_loan)}.")
    loans = load_loans_adv()
    if user_id in loans and not loans[user_id].get("repaid", False):
        return await ctx.send("❌ You already have an active loan. Repay it first.")
    bot.wallets[user_id] = bot.wallets.get(user_id, 0) + amount_num
    due_date = datetime.datetime.now() + datetime.timedelta(days=7)
    loans[user_id] = {
        "principal": amount_num,
        "interest_rate": 0.10,
        "due_date": due_date.isoformat(),
        "repaid": False,
        "default_count": 0
    }
    save_economy()
    asyncio.create_task(async_save_economy())
    save_loans_adv(loans)
    await ctx.send(f"✅ Loan of {format_money(amount_num)} granted. You must repay {format_money(int(amount_num*1.10))} by {due_date.strftime('%Y-%m-%d')}. Use `!repay_loan <amount>`.")

@bot.command(name="repay_loan")
async def repay_loan_adv(ctx, amount: str = None):
    user_id = str(ctx.author.id)
    loans = load_loans_adv()
    if user_id not in loans or loans[user_id].get("repaid", False):
        return await ctx.send("❌ No active loan.")
    loan = loans[user_id]
    owed = int(loan["principal"] * (1 + loan["interest_rate"]))
    if amount is None:
        amount_num = owed
    else:
        try:
            amount_num = parse_money_amount(amount)
        except:
            return await ctx.send("❌ Invalid amount! Use a number or shorthand like 5m (million), 5b (billion), 5t (trillion).")
        if amount_num <= 0:
            return await ctx.send("❌ Amount must be positive.")
    wallet = bot.wallets.get(user_id, 0)
    if wallet < amount_num:
        return await ctx.send(f"❌ You need {format_money(amount_num)} to repay.")
    bot.wallets[user_id] = wallet - amount_num
    if amount_num >= owed:
        loan["repaid"] = True
        await ctx.send(f"✅ Loan fully repaid! You paid {format_money(amount_num)}.")
    else:
        remaining = owed - amount_num
        loan["principal"] = remaining // (1 + loan["interest_rate"])
        await ctx.send(f"✅ Partial repayment of {format_money(amount_num)}. Remaining debt: {format_money(remaining)}.")
    save_economy()
    asyncio.create_task(async_save_economy())
    save_loans_adv(loans)

@bot.command(name="loan_status")
async def loan_status(ctx):
    user_id = str(ctx.author.id)
    loans = load_loans_adv()
    if user_id not in loans or loans[user_id].get("repaid", False):
        return await ctx.send("✅ You have no active loan.")
    loan = loans[user_id]
    owed = int(loan["principal"] * (1 + loan["interest_rate"]))
    due = datetime.datetime.fromisoformat(loan["due_date"]).strftime("%Y-%m-%d")
    await ctx.send(f"💰 Outstanding loan: {format_money(owed)} (due {due})")

# ==================== TAX EVASION COMMANDS ====================
TAX_EVASION_FILE = "tax_evasion_hidden.json"

def load_tax_evasion():
    try:
        with open(TAX_EVASION_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_tax_evasion(data):
    with open(TAX_EVASION_FILE, "w") as f:
        json.dump(data, f, indent=2)

@bot.command(name="hide_cash")
async def hide_cash(ctx, amount: str):
    try:
        amount_num = parse_money_amount(amount)
    except:
        return await ctx.send("❌ Invalid amount! Use a number or shorthand like 5m (million), 5b (billion), 5t (trillion).")
    if amount_num <= 0:
        return await ctx.send("❌ Amount must be positive.")
    user_id = str(ctx.author.id)
    wallet = bot.wallets.get(user_id, 0)
    if wallet < amount_num:
        return await ctx.send(f"❌ You only have {format_money(wallet)}.")
    hidden = load_tax_evasion()
    if user_id not in hidden:
        hidden[user_id] = 0
    hidden[user_id] += amount_num
    bot.wallets[user_id] = wallet - amount_num
    save_economy()
    asyncio.create_task(async_save_economy())
    save_tax_evasion(hidden)
    await ctx.send(f"🕵️ You hid {format_money(amount_num)} in a secret offshore account. It will not be taxed.")

@bot.command(name="report_evasion")
async def report_evasion(ctx, suspect: discord.Member):
    reporter_id = str(ctx.author.id)
    suspect_id = str(suspect.id)
    hidden = load_tax_evasion()
    if suspect_id not in hidden or hidden[suspect_id] <= 0:
        return await ctx.send(f"❌ {suspect.mention} has no hidden cash.")
    bounty = hidden[suspect_id] // 2
    bot.wallets[reporter_id] = bot.wallets.get(reporter_id, 0) + bounty
    del hidden[suspect_id]
    save_economy()
    asyncio.create_task(async_save_economy())
    save_tax_evasion(hidden)
    await ctx.send(f"🔍 **Tax Evasion Report** 🔍\n{suspect.mention} was caught hiding {format_money(bounty*2)}! {ctx.author.mention} received a bounty of {format_money(bounty)}.")

# ==================== PENDING TAX COMMANDS ====================
@bot.command(name="pending_tax")
async def pending_tax(ctx):
    user_id = str(ctx.author.id)
    tax = bot.pending_tax.get(user_id, 0)
    embed = create_embed(f"💰 Pending Tax for {ctx.author.display_name}", 
                         f"**Tax Owed:** {format_money(tax)}\n\nUse `!pay_tax` to pay your tax.", 
                         discord.Color.orange() if tax > 0 else discord.Color.green())
    await ctx.send(embed=embed)

@bot.command(name="pay_tax")
async def pay_tax(ctx):
    """Pay your pending tax from your wallet."""
    user_id = str(ctx.author.id)
    if not hasattr(bot, 'pending_tax'):
        bot.pending_tax = {}
    tax = bot.pending_tax.get(user_id, 0)
    if tax <= 0:
        return await ctx.send("✅ You have no pending tax.")
    wallet = bot.wallets.get(user_id, 0)
    if wallet < tax:
        return await ctx.send(f"❌ You need {format_money(tax)} in your wallet to pay your tax. Please deposit money or earn more.")
    bot.wallets[user_id] = wallet - tax
    del bot.pending_tax[user_id]
    save_pending_tax()
    save_economy()
    asyncio.create_task(async_save_economy())
    embed = create_embed("✅ Tax Paid!", f"Tax of {format_money(tax)} paid. Thank you for your compliance!", discord.Color.green())
    await ctx.send(embed=embed)

# ==================== TIERED PARTY COMMANDS ====================
PARTY_DATA_FILE = "active_tiered_parties.json"

def load_tiered_parties():
    try:
        with open(PARTY_DATA_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_tiered_parties(parties):
    with open(PARTY_DATA_FILE, "w") as f:
        json.dump(parties, f, indent=2)

def get_party_tier(budget):
    if budget < 50000:
        return "cheap", "🍿-basement-hangout", "budget lounge", "flickering lights, warm soda", 30
    elif budget < 500000:
        return "vip", "🥂-red-carpet-lounge", "official afterparty", "elite catering, photographers", 60
    else:
        return "mogul", "💎-billionaires-yacht", "exclusive billionaire gala", "prestigious, extravagant", 120

@bot.command(name="start_party")
async def start_tiered_party(ctx, budget: str, party_name: str, *invited: discord.Member):
    try:
        budget_num = parse_money_amount(budget)
    except:
        return await ctx.send("❌ Invalid budget! Use a number or shorthand like 5m (million), 5b (billion), 5t (trillion).")
    if budget_num < 1000:
        return await ctx.send("❌ Minimum budget is $1,000.")
    user_id = str(ctx.author.id)
    wallet = bot.wallets.get(user_id, 0)
    if wallet < budget_num:
        return await ctx.send(f"❌ You need {format_money(budget_num)} to host a party.")
    bot.wallets[user_id] = wallet - budget_num
    save_economy()
    asyncio.create_task(async_save_economy())

    tier, channel_name, desc_prefix, vibe, duration = get_party_tier(budget_num)
    category = await ctx.guild.create_category(f"Party-{ctx.author.name}-{party_name[:10]}")
    overwrites = {
        ctx.guild.default_role: discord.PermissionOverwrite(view_channel=False),
        ctx.author: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_messages=True),
        ctx.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_messages=True)
    }
    for member in invited:
        overwrites[member] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_messages=True)
    channel = await category.create_text_channel(f"{channel_name}-{ctx.author.name[:5]}", overwrites=overwrites)
    end_time = datetime.datetime.now() + datetime.timedelta(minutes=duration)
    party_id = str(channel.id)
    parties = load_tiered_parties()
    parties[party_id] = {
        "host": user_id,
        "tier": tier,
        "budget": budget_num,
        "name": party_name,
        "channel_id": channel.id,
        "category_id": category.id,
        "end_time": end_time.isoformat(),
        "invited": [str(m.id) for m in invited],
        "budget_left": budget_num
    }
    save_tiered_parties(parties)
    embed = discord.Embed(title=f"🎉 {party_name}", color=discord.Color.gold() if tier != "cheap" else discord.Color.blue())
    embed.description = f"**{desc_prefix}**\n{vibe}\nHost: {ctx.author.mention}\n💰 Budget spent: {format_money(budget_num)}\n⏰ Duration: {duration} minutes\n"
    if tier == "cheap":
        embed.add_field(name="Available commands", value="`!scavenge` – find loose change\n`!neighbor_complaint` – random event", inline=False)
    elif tier == "vip":
        embed.add_field(name="Available commands", value="`!network` – get 15% movie salary boost\n`!toast` – share champagne (costs budget)", inline=False)
    else:
        embed.add_field(name="Available commands", value="`!gala_dice` – high-stakes dice\n`!secret_deal` – private untaxed transfer", inline=False)
    await channel.send(embed=embed)
    await ctx.send(f"✅ Party **{party_name}** started! Private channel: {channel.mention}")
    await asyncio.sleep(duration * 60)
    parties = load_tiered_parties()
    if party_id in parties:
        del parties[party_id]
        save_tiered_parties(parties)
        try:
            await channel.delete()
            await category.delete()
        except:
            pass
        await ctx.send(f"🎉 Party **{party_name}** has ended. Thanks for coming!")

# ----- Tiered party activity commands -----
@bot.command(name="scavenge")
async def scavenge(ctx):
    party_id = str(ctx.channel.id)
    parties = load_tiered_parties()
    if party_id not in parties or parties[party_id]["tier"] != "cheap":
        return await ctx.send("❌ This command is only available in a 'Cheap Motown' party channel.")
    reward = random.randint(5, 10)
    bot.wallets[str(ctx.author.id)] = bot.wallets.get(str(ctx.author.id), 0) + reward
    save_economy()
    asyncio.create_task(async_save_economy())
    await ctx.send(f"🛋️ You scavenged under the couch and found {format_money(reward)}!")

@bot.command(name="neighbor_complaint")
async def neighbor_complaint(ctx):
    party_id = str(ctx.channel.id)
    parties = load_tiered_parties()
    if party_id not in parties or parties[party_id]["tier"] != "cheap":
        return await ctx.send("❌ This command is only available in a 'Cheap Motown' party channel.")
    await ctx.send("🚨 A neighbor complains about the noise! The host has 30 seconds to pay a bribe of $500 or the party will end early.")
    def check(m):
        return m.author.id == int(parties[party_id]["host"]) and m.channel == ctx.channel and m.content.lower() in ["pay", "ignore"]
    try:
        msg = await bot.wait_for('message', timeout=30.0, check=check)
        if msg.content.lower() == "pay":
            host_id = parties[party_id]["host"]
            wallet = bot.wallets.get(host_id, 0)
            if wallet >= 500:
                bot.wallets[host_id] = wallet - 500
                save_economy()
                asyncio.create_task(async_save_economy())
                await ctx.send("💸 You paid the bribe. The party continues!")
            else:
                await ctx.send("❌ You don't have enough money! The party ends early.")
                await force_end_party(ctx, party_id)
        else:
            await ctx.send("🚔 You ignored the complaint. The police shut down the party!")
            await force_end_party(ctx, party_id)
    except asyncio.TimeoutError:
        await ctx.send("⏰ No response. The party ends early.")
        await force_end_party(ctx, party_id)

@bot.command(name="network")
async def network(ctx):
    party_id = str(ctx.channel.id)
    parties = load_tiered_parties()
    if party_id not in parties or parties[party_id]["tier"] != "vip":
        return await ctx.send("❌ This command is only available in a VIP party channel.")
    user_id = str(ctx.author.id)
    if not hasattr(bot, 'network_boosts'):
        bot.network_boosts = {}
    expiry = datetime.datetime.now() + datetime.timedelta(hours=24)
    bot.network_boosts[user_id] = expiry.isoformat()
    await ctx.send("✨ You networked! You now have a **15% boost** on your next movie salary for 24 hours.")

@bot.command(name="toast")
async def toast(ctx):
    party_id = str(ctx.channel.id)
    parties = load_tiered_parties()
    if party_id not in parties or parties[party_id]["tier"] != "vip":
        return await ctx.send("❌ This command is only available in a VIP party channel.")
    party = parties[party_id]
    cost = 5000
    if party["budget_left"] < cost:
        return await ctx.send("❌ Not enough party budget left for champagne.")
    party["budget_left"] -= cost
    save_tiered_parties(parties)
    members = ctx.channel.members
    reward = 1500
    for member in members:
        if not member.bot:
            bot.wallets[str(member.id)] = bot.wallets.get(str(member.id), 0) + reward
    save_economy()
    asyncio.create_task(async_save_economy())
    await ctx.send(f"🥂 Toast! Everyone in the party received {format_money(reward)}. Budget left: {format_money(party['budget_left'])}")

@bot.command(name="gala_dice")
async def gala_dice(ctx, bet: str):
    try:
        bet_num = parse_money_amount(bet)
    except:
        return await ctx.send("❌ Invalid bet! Use a number or shorthand like 5m (million), 5b (billion), 5t (trillion).")
    if bet_num < 100000:
        return await ctx.send("❌ Minimum bet for gala dice is $100,000.")
    party_id = str(ctx.channel.id)
    parties = load_tiered_parties()
    if party_id not in parties or parties[party_id]["tier"] != "mogul":
        return await ctx.send("❌ This command is only available in a Mogul Gala party channel.")
    user_id = str(ctx.author.id)
    wallet = bot.wallets.get(user_id, 0)
    if wallet < bet_num:
        return await ctx.send(f"❌ You need {format_money(bet_num)} to play.")
    roll = random.randint(1, 6)
    if roll >= 4:
        win = bet_num * 2
        bot.wallets[user_id] = wallet + win - bet_num
        await ctx.send(f"🎲 You rolled a {roll}! You win {format_money(win)}!")
    else:
        bot.wallets[user_id] = wallet - bet_num
        await ctx.send(f"🎲 You rolled a {roll}. You lose {format_money(bet_num)}.")
    save_economy()
    asyncio.create_task(async_save_economy())

@bot.command(name="secret_deal")
async def secret_deal(ctx, recipient: discord.Member, amount: str):
    try:
        amount_num = parse_money_amount(amount)
    except:
        return await ctx.send("❌ Invalid amount! Use a number or shorthand like 5m (million), 5b (billion), 5t (trillion).")
    if amount_num <= 0:
        return await ctx.send("❌ Amount must be positive.")
    party_id = str(ctx.channel.id)
    parties = load_tiered_parties()
    if party_id not in parties or parties[party_id]["tier"] != "mogul":
        return await ctx.send("❌ This command is only available in a Mogul Gala party channel.")
    if recipient == ctx.author:
        return await ctx.send("❌ You cannot make a secret deal with yourself.")
    sender_id = str(ctx.author.id)
    receiver_id = str(recipient.id)
    wallet = bot.wallets.get(sender_id, 0)
    if wallet < amount_num:
        return await ctx.send(f"❌ You need {format_money(amount_num)}.")
    bot.wallets[sender_id] -= amount_num
    bot.wallets[receiver_id] = bot.wallets.get(receiver_id, 0) + amount_num
    save_economy()
    asyncio.create_task(async_save_economy())
    await ctx.send(f"🤝 Secret deal completed! {format_money(amount_num)} transferred to {recipient.mention} (untaxed).")

async def force_end_party(ctx, party_id):
    parties = load_tiered_parties()
    if party_id not in parties:
        return
    party = parties[party_id]
    channel = ctx.guild.get_channel(party["channel_id"])
    category = ctx.guild.get_category(party["category_id"])
    if channel:
        await channel.delete()
    if category:
        await category.delete()
    del parties[party_id]
    save_tiered_parties(parties)
    await ctx.send("🛑 Party ended.", delete_after=5)

@bot.command(name="end_party_now")
async def end_party_now(ctx):
    party_id = str(ctx.channel.id)
    parties = load_tiered_parties()
    if party_id not in parties:
        return await ctx.send("❌ No active party in this channel.")
    party = parties[party_id]
    if str(ctx.author.id) != party["host"]:
        return await ctx.send("❌ Only the host can end the party early.")
    await force_end_party(ctx, party_id)
    
    


# ==================== ERROR HANDLER ====================
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("❌ Command not found. Use `!h`.", delete_after=10)
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission.", delete_after=10)
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing argument. Use `!h {ctx.command.name}`", delete_after=10)
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ Invalid argument. Check the command usage.", delete_after=10)
    else:
        print(f"⚠️ Error in {ctx.command}: {error}")
        await ctx.send(f"❌ An error occurred: {str(error)[:100]}", delete_after=10)

# ==================== HELP COMMAND (!h) ====================
@bot.command(name="h", aliases=["helpme"])
async def help_command(ctx, category: str = None):
    """Display the professional help menu. Use !h <category>."""
    if category is None:
        embed = discord.Embed(title="🌟 BOT HELP MENU", description="Use `!h <category>`\n\n**Categories:**", color=discord.Color.gold())
        embed.set_thumbnail(url=bot.user.avatar.url if bot.user.avatar else None)
        embed.add_field(name="💰 Economy", value="`!h economy`", inline=True)
        embed.add_field(name="🎲 Gambling", value="`!h gambling`", inline=True)
        embed.add_field(name="🏢 Business", value="`!h business`", inline=True)
        embed.add_field(name="🛒 Shop & Trading", value="`!h shop`", inline=True)
        embed.add_field(name="🏰 Clans", value="`!h clans`", inline=True)
        embed.add_field(name="🎬 Movies & Studios", value="`!h movies`", inline=True)
        embed.add_field(name="🌍 Country Guesser", value="`!h country`", inline=True)
        embed.add_field(name="🛡️ Moderation", value="`!h moderation`", inline=True)
        embed.add_field(name="⚖️ Court", value="`!h court`", inline=True)
        embed.add_field(name="🔧 Admin", value="`!h admin`", inline=True)
        embed.add_field(name="🎭 Roles", value="`!h roles`", inline=True)
        embed.add_field(name="📝 Utility", value="`!h utility`", inline=True)
        embed.set_footer(text=f"Requested by {ctx.author.name}")
        await ctx.send(embed=embed)
    elif category.lower() == "economy":
        embed = discord.Embed(title="💰 Economy Commands", color=discord.Color.green())
        embed.add_field(name="!balance / !bal", value="Check balance", inline=False)
        embed.add_field(name="!daily", value="Daily reward $10,000", inline=False)
        embed.add_field(name="!work", value="Work (1h cooldown)", inline=False)
        embed.add_field(name="!deposit / !withdraw", value="Bank transfers (use 5m, 5b, 5t)", inline=False)
        embed.add_field(name="!transfer / !pay", value="Send money (2% tax) – use 5m, 5b, 5t", inline=False)
        embed.add_field(name="!rich / !leaderboard", value="Richest members in server", inline=False)
        embed.add_field(name="!pending_tax", value="Check your pending tax", inline=False)
        embed.add_field(name="!pay_tax", value="Pay your pending tax", inline=False)
        embed.add_field(name="!next_salary", value="See when next salary is due", inline=False)
        embed.add_field(name="!invest", value="Invest more money into your business", inline=False)
        embed.add_field(name="!topbusinesses", value="View the top 10 businesses", inline=False)
        await ctx.send(embed=embed)
    elif category.lower() == "gambling":
        embed = discord.Embed(title="🎲 Gambling Commands", color=discord.Color.purple())
        embed.add_field(name="!gamble", value="45% win 1.5x (use 5m, 5b, 5t)", inline=False)
        embed.add_field(name="!coinflip", value="50/50 win 2x (use 5m, 5b, 5t)", inline=False)
        embed.add_field(name="!numbers", value="Guess two 1‑10: one match = 0.5x, two = 2x (use 5m, 5b, 5t)", inline=False)
        embed.add_field(name="!horserace", value="Bet on horse 1‑4, win 3x (use 5m, 5b, 5t)", inline=False)
        embed.add_field(name="!dice", value="Guess 1‑6, win 5x (use 5m, 5b, 5t)", inline=False)
        await ctx.send(embed=embed)
    elif category.lower() == "business":
        embed = discord.Embed(title="🏢 Business Commands", color=discord.Color.blue())
        embed.add_field(name="!createbusiness / !startbusiness", value="Start a business", inline=False)
        embed.add_field(name="!mybusiness / !mybiz", value="Check status", inline=False)
        embed.add_field(name="!collectprofit", value="Collect profits", inline=False)
        embed.add_field(name="!upgradebusiness", value="Upgrade", inline=False)
        embed.add_field(name="!closebusiness", value="Close business", inline=False)
        embed.add_field(name="!invest", value="Invest more money into your business", inline=False)
        embed.add_field(name="!topbusinesses", value="View the top 10 businesses", inline=False)
        await ctx.send(embed=embed)
    elif category.lower() == "shop":
        embed = discord.Embed(title="🛒 Shop & Trading", color=discord.Color.teal())
        embed.add_field(name="!shop / !buy", value="Browse and buy from shop (rarity: ⚪ common → 🟡 legendary)", inline=False)
        embed.add_field(name="!inventory / !inv", value="Your items (including awards)", inline=False)
        embed.add_field(name="!sellitem @user <item> <price>", value="Offer item for sale", inline=False)
        embed.add_field(name="!buyitem @user <item>", value="Accept offer", inline=False)
        embed.add_field(name="!studio_shares / !myshares", value="View your studio and business shares", inline=False)
        embed.add_field(name="!sell_share / !buyshare", value="Buy or sell shares", inline=False)
        embed.add_field(name="!shareholders <studio/business>", value="List all shareholders", inline=False)
        await ctx.send(embed=embed)
    elif category.lower() == "clans":
        embed = discord.Embed(title="🏰 Clan Commands", color=discord.Color.dark_gold())
        embed.add_field(name="!clan_create", value="Create clan ($100k)", inline=False)
        embed.add_field(name="!clan_invite / !clan_accept", value="Invite / join", inline=False)
        embed.add_field(name="!clan_info / !clan_list", value="View info", inline=False)
        embed.add_field(name="!clan_leave / !clan_kick", value="Leave or kick", inline=False)
        embed.add_field(name="!clan_transfer / !clan_disband", value="Transfer or delete", inline=False)
        await ctx.send(embed=embed)
    elif category.lower() == "movies":
        embed = discord.Embed(title="🎬 Movie & Studio Commands", color=discord.Color.magenta())
        embed.add_field(name="!create_studio <name>", value="Create your own movie studio ($50,000)", inline=False)
        embed.add_field(name="!my_studio", value="View your studio's stats", inline=False)
        embed.add_field(name="!top_studios", value="Top 10 studios by box office", inline=False)
        embed.add_field(name="!studio_hits <studio_name>", value="Show a studio's top 5 movies", inline=False)
        embed.add_field(name="!makemovie <budget> <actors_salary> <title> [@actors...]", value="Produce a movie using your studio. Actors with 5+ hits boost success rate!", inline=False)
        embed.add_field(name="!actorstats [@user]", value="View an actor's total earnings and movie count", inline=False)
        embed.add_field(name="!topactors", value="Top 10 actors by number of hit movies (score ≥ 80%)", inline=False)
        embed.add_field(name="!topmovies", value="View highest grossing films in this server", inline=False)
        embed.add_field(name="!studio_shares / !myshares", value="View your studio shares", inline=False)
        embed.add_field(name="!sell_share / !buyshare", value="Buy or sell studio shares", inline=False)
        await ctx.send(embed=embed)
    elif category.lower() == "country":
        embed = discord.Embed(title="🌍 Country Guesser Game", color=discord.Color.teal())
        embed.add_field(name="!startguess <continent> <rounds>", value="Start a game. Continents: africa, asia, europe, north_america, south_america, oceania, random. Rounds: 1-30.", inline=False)
        embed.add_field(name="!endguess", value="Force end the current game", inline=False)
        embed.add_field(name="Just type the country name!", value="During a game, simply type the country name to guess. No command prefix needed.", inline=False)
        embed.add_field(name="!countryscore [@user]", value="Show your total points", inline=False)
        embed.add_field(name="!countrylb", value="Show global leaderboard", inline=False)
        await ctx.send(embed=embed)
    elif category.lower() == "moderation":
        embed = discord.Embed(title="🛡️ Moderation Commands", color=discord.Color.red())
        embed.add_field(name="!warn / !warnings", value="Warn system", inline=False)
        embed.add_field(name="!mute <user> <duration> [reason]", value="Mute users (5s, 5m, 5h formats)", inline=False)
        embed.add_field(name="!um", value="Unmute", inline=False)
        embed.add_field(name="!k / !b", value="Kick/ban (respects role hierarchy)", inline=False)
        embed.add_field(name="!clear / !purge", value="Delete messages", inline=False)
        embed.add_field(name="!q / !uq / !quarantinelist", value="Quarantine system (respects hierarchy)", inline=False)
        embed.add_field(name="!addword / !removeword / !wordlist", value="Auto-mod word filter (staff only)", inline=False)
        embed.add_field(name="!setautomod / !removeautomod / !automodlist", value="Set custom actions (warn, mute, ban) for words", inline=False)
        embed.add_field(name="!modlogs", value="View auto‑mod deletion history (admin)", inline=False)
        embed.add_field(name="!staffstats [@user]", value="View moderation stats", inline=False)
        embed.add_field(name="!setspam / !spamconfig", value="Configure spam detection (staff)", inline=False)
        embed.add_field(name="!settz <timezone>", value="Set your timezone", inline=False)
        embed.add_field(name="!tz [@user]", value="Show current time", inline=False)
        await ctx.send(embed=embed)
    elif category.lower() == "court":
        embed = discord.Embed(title="⚖️ Court Commands", color=discord.Color.orange())
        embed.add_field(name="!sue @user <reason>", value="File lawsuit", inline=False)
        embed.add_field(name="!guilty @user <amount>", value="Judge: fine defendant (admin)", inline=False)
        embed.add_field(name="!dismiss @user", value="Dismiss case (admin)", inline=False)
        await ctx.send(embed=embed)
    elif category.lower() == "admin":
        embed = discord.Embed(title="🔧 Admin Commands", color=discord.Color.dark_red())
        embed.add_field(name="!givemoney / !setbalance / !addmoney", value="Manage money (use 5m, 5b, 5t for !addmoney)", inline=False)
        embed.add_field(name="!addshopitem / !removeitem / !editshopitem", value="Manage shop (with rarity)", inline=False)
        embed.add_field(name="!setsalary / !salarylist / !paysalary", value="Manage salaries", inline=False)
        embed.add_field(name="!nick @user <newname>", value="Change nickname (staff)", inline=False)
        embed.add_field(name="!forceaward", value="Manually run weekly movie award check", inline=False)
        embed.add_field(name="!modlogs", value="View auto-mod history", inline=False)
        embed.add_field(name="!migrate_automod", value="Convert old banned words to new rule system", inline=False)
        embed.add_field(name="!tax", value="Set tax percentage for a role", inline=False)
        embed.add_field(name="!say", value="Make bot say a message in #general", inline=False)
        embed.add_field(name="!next_salary", value="Check time until next automatic salary payment", inline=False)
        embed.add_field(name="!setspam / !spamconfig", value="Configure spam detection", inline=False)
        embed.add_field(name="!startelection / !endelection", value="Start/end an election", inline=False)
        embed.add_field(name="!setelectionfee", value="Set entry fee for election", inline=False)
        embed.add_field(name="!roleicon / !removeicon", value="Add/remove role icon", inline=False)
        embed.add_field(name="!roleposition", value="Change role hierarchy position", inline=False)
        embed.add_field(name="!setbirthdayrole", value="Set the birthday role", inline=False)
        embed.add_field(name="!setbirthdaywish", value="Set the birthday wish message", inline=False)
        await ctx.send(embed=embed)
    elif category.lower() == "roles":
        embed = discord.Embed(title="🎭 Role Management", color=discord.Color.purple())
        embed.add_field(name="!cr / !createrole <name> [color]", value="Create role (staff)", inline=False)
        embed.add_field(name="!ar / !addrole @user <role>", value="Add role (staff)", inline=False)
        embed.add_field(name="!rr / !removerole @user <role>", value="Remove role (staff)", inline=False)
        embed.add_field(name="!rolemembers <role_name>", value="List members with a role", inline=False)
        embed.add_field(name="!roleicon / !removeicon", value="Add/remove role icon (admin)", inline=False)
        embed.add_field(name="!roleposition", value="Change role hierarchy position (admin)", inline=False)
        await ctx.send(embed=embed)
    elif category.lower() == "utility":
        embed = discord.Embed(title="📝 Utility Commands", color=discord.Color.blue())
        embed.add_field(name="!ping", value="Latency", inline=False)
        embed.add_field(name="!afk [reason]", value="Set AFK", inline=False)
        embed.add_field(name="!s", value="Last deleted message (shows auto-mod deletions)", inline=False)
        embed.add_field(name="!uptime", value="Bot uptime", inline=False)
        embed.add_field(name="!rules", value="Show server rules", inline=False)
        embed.add_field(name="!avatar / !av", value="Show user's profile picture", inline=False)
        embed.add_field(name="!fly / !invite_passenger", value="Fly your private jet (5 min)", inline=False)
        embed.add_field(name="!race", value="Race another car owner", inline=False)
        embed.add_field(name="!drive", value="Go for a random drive (requires car)", inline=False)
        embed.add_field(name="!host_party / !join_party / !end_party", value="Mansion/island party system", inline=False)
        embed.add_field(name="!play_with_pet", value="Interact with your pet", inline=False)
        embed.add_field(name="!settz <timezone>", value="Set your timezone", inline=False)
        embed.add_field(name="!tz [@user]", value="Show current time", inline=False)
        embed.add_field(name="!pay_tax", value="Pay your pending tax", inline=False)
        embed.add_field(name="!pending_tax", value="Check your pending tax", inline=False)
        embed.add_field(name="!loan_status", value="Check your outstanding loan", inline=False)
        embed.add_field(name="!next_salary", value="Check when next salary is due", inline=False)
        embed.add_field(name="!setbirthday <MM-DD>", value="Set your birthday", inline=False)
        embed.add_field(name="!birthday [@user]", value="Check someone's birthday", inline=False)
        embed.add_field(name="!start_party <budget> <name> [@invites...]", value="Start a tiered party", inline=False)
        embed.add_field(name="!prefixless <role>", value="Add role to prefixless access", inline=False)
        embed.add_field(name="!rp <role>", value="Remove prefixless access", inline=False)
        embed.add_field(name="!prefixlesslist", value="List prefixless roles", inline=False)
        await ctx.send(embed=embed)
    else:
        await ctx.send(f"❌ Unknown category `{category}`. Use `!h`.", delete_after=10)

# ==================== MAIN FUNCTION ====================
def main():
    print("=" * 50)
    print("🤖 DISCORD BOT STARTING ON RENDER WITH SUPABASE")
    print("=" * 50)
    token = os.environ.get('DISCORD_TOKEN') or os.environ.get('DISCORD_BOT_TOKEN')
    if not token:
        print("❌ No token found! Set DISCORD_TOKEN environment variable.")
        return
    try:
        bot.run(token)
    except Exception as e:
        print(f"❌ Failed to start: {e}")

if __name__ == "__main__":
    main()
