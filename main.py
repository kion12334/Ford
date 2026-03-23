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

print("🚀 Starting Discord Bot on Render with Supabase...")
print("=" * 50)

# Bot setup with all necessary intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix='!', intents=intents)

print("✅ Bot initialized")

# File paths for data storage (JSON fallback)
DATA_FILE = "bot_data.json"
ECONOMY_FILE = "economy_data.json"
SHOP_FILE = "shop_items.json"
ROLE_SALARIES_FILE = "role_salaries.json"
COUNTRIES_FILE = "countries.json"
COUNTRY_SCORES_FILE = "country_scores.json"
QUARANTINE_FILE = "quarantine_data.json"
BUSINESS_FILE = "business_data.json"
LAST_SALARY_FILE = "last_salary.json"
LAST_BUSINESS_PROFIT_FILE = "last_business_profit.json"

# ===== HELPER FUNCTIONS =====
def format_money(amount):
    """Format money with commas"""
    return f"${amount:,}"

def create_embed(title, description, color=discord.Color.blue()):
    """Create a discord embed"""
    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=datetime.datetime.now()
    )
    return embed

def has_staff_permission(member):
    """Check if member has staff permissions"""
    if member.guild_permissions.administrator:
        return True
    
    staff_roles = ["Admin", "Moderator", "Staff"]
    for role in member.roles:
        if role.name in staff_roles:
            return True
    return False

# ===== SUPABASE DATABASE CLASS (Integrated) =====
class Database:
    def __init__(self):
        self.pool = None
        self.connected = False

    async def connect(self):
        """Connect to Supabase using SUPABASE_URL environment variable."""
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
        """Create necessary tables if they don't exist."""
        async with self.pool.acquire() as conn:
            # Economy table
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
            # Warnings table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS warnings (
                    user_id BIGINT,
                    guild_id BIGINT,
                    count INTEGER DEFAULT 0,
                    PRIMARY KEY (user_id, guild_id)
                )
            ''')
            # Quarantine table
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
            # Country scores table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS country_scores (
                    user_id BIGINT PRIMARY KEY,
                    score INTEGER DEFAULT 0
                )
            ''')
            # Shop items table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS shop_items (
                    category TEXT,
                    item_name TEXT,
                    price INTEGER,
                    description TEXT,
                    emoji TEXT,
                    PRIMARY KEY (category, item_name)
                )
            ''')
            # Role salaries table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS role_salaries (
                    role_name TEXT PRIMARY KEY,
                    salary INTEGER
                )
            ''')
            print("✅ Database tables verified/created.")

    # --- Economy methods ---
    async def load_economy(self):
        """Load all economy data into dictionaries."""
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
        """Upsert economy data into database."""
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

    # --- Warnings methods ---
    async def load_warnings(self):
        """Load all warnings into a nested dict {guild_id: {user_id: count}}."""
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
        """Save warnings to database."""
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

    # --- Quarantine methods ---
    async def load_quarantine(self):
        """Load quarantine data."""
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
        """Save quarantine data."""
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

    # --- Country scores methods ---
    async def load_country_scores(self):
        """Load country game scores."""
        scores = {}
        async with self.pool.acquire() as conn:
            rows = await conn.fetch('SELECT * FROM country_scores')
            for row in rows:
                scores[str(row['user_id'])] = row['score']
        return scores

    async def save_country_scores(self, scores_dict):
        """Save country scores."""
        if not self.connected:
            return
        async with self.pool.acquire() as conn:
            for uid, score in scores_dict.items():
                await conn.execute('''
                    INSERT INTO country_scores (user_id, score)
                    VALUES ($1, $2)
                    ON CONFLICT (user_id) DO UPDATE SET score = EXCLUDED.score
                ''', int(uid), score)

    # --- Shop items methods ---
    async def load_shop_items(self):
        """Load all shop items from database into the same format as JSON."""
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
                    "emoji": row['emoji'] or "🛍️"
                })
        return items

    async def save_shop_items(self, items_dict):
        """Upsert shop items into database."""
        if not self.connected:
            return
        async with self.pool.acquire() as conn:
            await conn.execute('DELETE FROM shop_items')
            for category, item_list in items_dict.items():
                for item in item_list:
                    await conn.execute('''
                        INSERT INTO shop_items (category, item_name, price, description, emoji)
                        VALUES ($1, $2, $3, $4, $5)
                    ''', category, item['name'], item['price'],
                        item.get('description', ''), item.get('emoji', '🛍️'))

    # --- Role salaries methods ---
    async def load_role_salaries(self):
        """Load role salaries from database."""
        salaries = {"default": 1000}
        async with self.pool.acquire() as conn:
            rows = await conn.fetch('SELECT * FROM role_salaries')
            for row in rows:
                salaries[row['role_name']] = row['salary']
        return salaries

    async def save_role_salaries(self, salaries_dict):
        """Save role salaries to database."""
        if not self.connected:
            return
        async with self.pool.acquire() as conn:
            await conn.execute('DELETE FROM role_salaries')
            for role, salary in salaries_dict.items():
                await conn.execute('''
                    INSERT INTO role_salaries (role_name, salary) VALUES ($1, $2)
                ''', role, salary)

    async def close(self):
        if self.pool:
            await self.pool.close()

# Global database instance
db = Database() 
# ===== DATA LOADING FUNCTIONS (JSON fallback) =====
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
        return {
            "wallets": {},
            "banks": {},
            "last_daily": {},
            "last_work": {},
            "owned_items": {},
            "businesses": {}
        }

def load_shop():
    try:
        with open(SHOP_FILE, "r") as f:
            return json.load(f)
    except:
        return {"roles": [], "vehicles": [], "properties": [], "aircraft": {}, "yachts": []}

def load_role_salaries():
    try:
        with open(ROLE_SALARIES_FILE, "r") as f:
            return json.load(f)
    except:
        return {"default": 1000, "Admin": 5000, "Moderator": 3000}

def load_countries():
    try:
        with open(COUNTRIES_FILE, "r") as f:
            return json.load(f)
    except:
        return {"Europe": [], "Africa": []}

def load_country_scores():
    try:
        with open(COUNTRY_SCORES_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

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

# ===== DATA SAVING FUNCTIONS (JSON) =====
def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump({
            "afk_users": bot.afk_users,
            "warnings": bot.warnings,
            "muted_users": bot.muted_users
        }, f, indent=2)

def save_economy():
    with open(ECONOMY_FILE, "w") as f:
        json.dump({
            "wallets": bot.wallets,
            "banks": bot.banks,
            "last_daily": bot.last_daily,
            "last_work": bot.last_work,
            "owned_items": bot.owned_items,
            "businesses": bot.businesses
        }, f, indent=2)

def save_country_scores():
    with open(COUNTRY_SCORES_FILE, "w") as f:
        json.dump(bot.country_scores, f, indent=2)

def save_quarantine():
    with open(QUARANTINE_FILE, "w") as f:
        json.dump({
            "quarantined_users": bot.quarantined_users,
            "quarantine_channels": bot.quarantine_channels
        }, f, indent=2)

def save_businesses():
    with open(BUSINESS_FILE, "w") as f:
        json.dump({
            "businesses": bot.businesses,
            "business_types": bot.business_types
        }, f, indent=2)

def save_last_salary(last_salary_time):
    with open(LAST_SALARY_FILE, "w") as f:
        json.dump({
            "last_salary": last_salary_time,
            "saved_at": datetime.datetime.now().isoformat()
        }, f, indent=2)

def save_last_business_profit(last_profit_time):
    with open(LAST_BUSINESS_PROFIT_FILE, "w") as f:
        json.dump({
            "last_business_profit": last_profit_time,
            "saved_at": datetime.datetime.now().isoformat()
        }, f, indent=2)

# ===== ASYNC DATABASE SAVE WRAPPERS =====
async def async_save_economy():
    if db.connected:
        await db.save_economy(
            bot.wallets, bot.banks, bot.last_daily, bot.last_work,
            bot.owned_items, bot.businesses
        )

async def async_save_warnings():
    if db.connected:
        await db.save_warnings(bot.warnings)

async def async_save_quarantine():
    if db.connected:
        await db.save_quarantine(bot.quarantined_users)

async def async_save_country_scores():
    if db.connected:
        await db.save_country_scores(bot.country_scores)

async def async_save_shop_items():
    if db.connected:
        await db.save_shop_items(bot.shop_items)

async def async_save_role_salaries():
    if db.connected:
        await db.save_role_salaries(bot.role_salaries)

print("📊 Loading data...")

# Load initial data from JSON
data = load_data()
economy = load_economy()
shop_items = load_shop()
role_salaries = load_role_salaries()
countries = load_countries()
country_scores = load_country_scores()
quarantine_data = load_quarantine()
business_data = load_businesses()
last_salary_data = load_last_salary()
last_business_profit_data = load_last_business_profit()

if 'RAILWAY_ENVIRONMENT' in os.environ:
    print("⚠️  WARNING: Running on Railway - JSON data may reset on restart!")
    print("💡 Tip: Data is saved to Supabase if SUPABASE_URL is set.")

# Initialize bot variables from JSON (will be overwritten by DB if connected)
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
bot.countries = countries
bot.country_scores = country_scores
bot.quarantined_users = quarantine_data.get("quarantined_users", {})
bot.quarantine_channels = quarantine_data.get("quarantine_channels", {})
bot.business_types = business_data.get("business_types", {})
bot.active_games = {}
bot.start_time = datetime.datetime.now()

print("✅ Data loaded successfully!")

# ===== HTTP KEEP-ALIVE SERVER =====
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
# ===== BOT EVENTS =====

@bot.event
async def on_ready():
    """When bot connects successfully"""
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

        scores = await db.load_country_scores()
        if scores:
            bot.country_scores = scores
            print("✅ Loaded country scores from Supabase.")

        shop_items_db = await db.load_shop_items()
        if shop_items_db:
            bot.shop_items = shop_items_db
            print("✅ Loaded shop items from Supabase.")

        role_salaries_db = await db.load_role_salaries()
        if role_salaries_db:
            bot.role_salaries = role_salaries_db
            print("✅ Loaded role salaries from Supabase.")

    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="!help for commands"
        )
    )

    if not daily_salaries.is_running():
        daily_salaries.start()
        print("💰 Daily salaries task started")

    if not check_muted_users.is_running():
        check_muted_users.start()
        print("🔇 Mute check task started")

    if not business_profits.is_running():
        business_profits.start()
        print("🏢 Business profits task started")

    print("🎉 Bot is ready and running 24/7!")

@bot.event
async def on_member_join(member):
    """Welcome new members"""
    try:
        channel = discord.utils.get(member.guild.text_channels, name="welcome")
        if not channel:
            channel = discord.utils.get(member.guild.text_channels, name="general")
        if not channel:
            channel = member.guild.system_channel

        if channel:
            embed = create_embed(
                "Welcome",
                f"Welcome {member.mention} to {member.guild.name}!",
                discord.Color.green()
            )
            embed.add_field(name="Member Count", value=f"{member.guild.member_count}", inline=True)

            if member.avatar:
                embed.set_thumbnail(url=member.avatar.url)
            await channel.send(embed=embed)
    except Exception as e:
        print(f"Welcome error: {e}")

@bot.event
async def on_message(message):
    """Handle all messages"""
    if message.author.bot:
        return await bot.process_commands(message)

    user_id = str(message.author.id)
    guild_id = str(message.guild.id)

    # AFK system
    if user_id in bot.afk_users and not message.content.startswith('!'):
        info = bot.afk_users.pop(user_id)
        try:
            time_afk = (datetime.datetime.now() - datetime.datetime.fromisoformat(info["time"])).seconds // 60
            await message.channel.send(
                f"👋 Welcome back {message.author.mention}! You were AFK for {time_afk} minutes.",
                delete_after=5
            )
            save_data()
            asyncio.create_task(async_save_warnings())
        except:
            pass

    # Check if user is quarantined
    if guild_id in bot.quarantined_users and user_id in bot.quarantined_users[guild_id]:
        quarantine_info = bot.quarantined_users[guild_id][user_id]
        quarantine_channel_id = quarantine_info.get("channel_id")

        if str(message.channel.id) != str(quarantine_channel_id):
            try:
                await message.delete()
                await message.author.send(f"⚠️ You are quarantined! You can only talk in the quarantine channel.")
            except:
                pass
            return

    # Country game handling
    if guild_id in bot.active_games and bot.active_games[guild_id].get("active", False):
        game = bot.active_games[guild_id]
        if "current_country" not in game or game.get("paused", False):
            return await bot.process_commands(message)

        if not message.content.startswith('!'):
            await handle_country_guess(message, game, user_id)
            return

    await bot.process_commands(message)
  # ===== COUNTRY GAME FUNCTIONS =====

async def handle_country_guess(message, game, user_id):
    """Handle country game guesses"""
    country = game["current_country"]
    guess = message.content.strip().lower()
    game_type = game.get("game_type", "flag")

    correct = False

    if game_type == "flag":
        if guess in [country["country"].lower(), country["capital"].lower()]:
            correct = True
    else:
        if guess == country["capital"].lower():
            correct = True

    if correct:
        if "winners" not in game:
            game["winners"] = []

        if user_id in game["winners"]:
            return

        game["winners"].append(user_id)
        position = len(game["winners"])

        if position == 1:
            points = 3
            medal = "🥇"
        elif position == 2:
            points = 2
            medal = "🥈"
        elif position == 3:
            points = 1
            medal = "🥉"
        else:
            points = 0
            medal = "🎯"

        bot.country_scores[user_id] = bot.country_scores.get(user_id, 0) + points
        save_country_scores()
        asyncio.create_task(async_save_country_scores())

        if game_type == "flag":
            title = f"{medal} Correct! {country['flag']}"
            answer_info = f"**Country:** {country['country']}\n**Capital:** {country['capital']}"
        else:
            title = f"{medal} Correct!"
            answer_info = f"**Capital of {country['country']}:** {country['capital']}"

        embed = create_embed(
            title,
            f"**{message.author.mention} guessed {position}{'st' if position==1 else 'nd' if position==2 else 'rd' if position==3 else 'th'}!**\n"
            f"{answer_info}\n"
            f"**Points:** +{points}",
            discord.Color.green() if position <= 3 else discord.Color.blue()
        )
        await message.channel.send(embed=embed)

        if "timer" in game and not game["timer"].done():
            game["timer"].cancel()

        await asyncio.sleep(3)
        await next_country_round(message.guild)

async def next_country_round(guild):
    """Start next round of country game, check round limit"""
    guild_id = str(guild.id)
    if guild_id not in bot.active_games:
        return

    game = bot.active_games[guild_id]

    if game["rounds"] != -1 and game["round_count"] >= game["rounds"]:
        channel = guild.get_channel(game["channel_id"])
        if channel:
            embed = create_embed(
                "🏁 Game Over",
                f"The game has finished after **{game['rounds']}** rounds!\n"
                f"Use `!startcountrygame` to play again.",
                discord.Color.green()
            )
            await channel.send(embed=embed)
        del bot.active_games[guild_id]
        return

    continent = game["continent"]
    countries = bot.countries.get(continent, [])
    if not countries:
        return

    country = random.choice(countries)
    game["current_country"] = country
    game["winners"] = []
    game["round_count"] += 1

    channel = guild.get_channel(game["channel_id"])
    if not channel:
        return

    if game["game_type"] == "flag":
        flag_display = country.get('flag', '🏳️')
        embed = create_embed(
            f"🇺🇳 Round {game['round_count']} Started!",
            f"**Guess the country or capital!**\n"
            f"**Flag:** {flag_display}",
            discord.Color.blue()
        )
    else:
        embed = create_embed(
            f"🏛️ Round {game['round_count']} Started!",
            f"**What is the capital of:** {country['country']}?",
            discord.Color.blue()
        )

    await channel.send(embed=embed)

    async def timeout():
        await asyncio.sleep(60)
        if guild_id in bot.active_games and "winners" in bot.active_games[guild_id]:
            if len(bot.active_games[guild_id]["winners"]) == 0:
                embed = create_embed(
                    "⏰ Time's Up!",
                    f"**Correct answer:** {country['country']} - {country['capital']}",
                    discord.Color.orange()
                )
                await channel.send(embed=embed)
                await asyncio.sleep(3)
                await next_country_round(guild)

    game["timer"] = asyncio.create_task(timeout())
  # ===== BASIC COMMANDS =====

@bot.command(name="ping")
async def ping(ctx):
    """Check bot latency"""
    latency = round(bot.latency * 1000)
    embed = create_embed(
        "🏓 Pong!",
        f"**Latency:** {latency}ms\n**Status:** Online ✅\n**Host:** Render",
        discord.Color.green()
    )
    await ctx.send(embed=embed)

@bot.command(name="afk")
async def afk(ctx, *, reason="No reason"):
    """Set AFK status"""
    user_id = str(ctx.author.id)
    bot.afk_users[user_id] = {
        "reason": reason,
        "time": datetime.datetime.now().isoformat()
    }
    save_data()
    embed = create_embed(
        "⏸️ AFK Set",
        f"{ctx.author.mention} is now AFK\n**Reason:** {reason}",
        discord.Color.blue()
    )
    await ctx.send(embed=embed, delete_after=10)

@bot.command(name="mute")
@commands.has_permissions(manage_messages=True)
async def mute(ctx, member: discord.Member, minutes: int = 10, *, reason="No reason"):
    """Mute a user for specified minutes"""
    if member.guild_permissions.administrator:
        embed = create_embed("❌ Error", "Cannot mute an administrator.", discord.Color.red())
        await ctx.send(embed=embed)
        return

    mute_role = discord.utils.get(ctx.guild.roles, name="Muted")
    if not mute_role:
        try:
            mute_role = await ctx.guild.create_role(
                name="Muted",
                color=discord.Color.dark_gray(),
                reason="Mute role for bot"
            )
            for channel in ctx.guild.channels:
                try:
                    await channel.set_permissions(mute_role,
                                                send_messages=False,
                                                speak=False,
                                                add_reactions=False)
                except:
                    pass
        except discord.Forbidden:
            embed = create_embed("❌ Error", "I don't have permission to create roles.", discord.Color.red())
            await ctx.send(embed=embed)
            return

    await member.add_roles(mute_role, reason=f"Muted by {ctx.author}: {reason}")

    unmute_time = datetime.datetime.now() + datetime.timedelta(minutes=minutes)
    bot.muted_users[str(member.id)] = {
        "unmute_at": unmute_time.isoformat(),
        "reason": reason,
        "guild_id": ctx.guild.id
    }
    save_data()

    embed = create_embed(
        "🔇 User Muted",
        f"**User:** {member.mention}\n"
        f"**Duration:** {minutes} minutes\n"
        f"**Reason:** {reason}\n"
        f"**Until:** {unmute_time.strftime('%H:%M:%S')}",
        discord.Color.orange()
    )
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

@bot.command(name="unmute")
@commands.has_permissions(manage_messages=True)
async def unmute(ctx, member: discord.Member):
    """Unmute a user"""
    mute_role = discord.utils.get(ctx.guild.roles, name="Muted")
    if not mute_role or mute_role not in member.roles:
        embed = create_embed("❌ Error", "This user is not muted.", discord.Color.red())
        await ctx.send(embed=embed)
        return

    await member.remove_roles(mute_role)

    if str(member.id) in bot.muted_users:
        del bot.muted_users[str(member.id)]
        save_data()

    embed = create_embed(
        "🔊 User Unmuted",
        f"{member.mention} has been unmuted by {ctx.author.mention}",
        discord.Color.green()
    )
    await ctx.send(embed=embed)

@bot.command(name="kick")
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason="No reason"):
    """Kick a user from the server"""
    if member.guild_permissions.administrator:
        embed = create_embed("❌ Error", "Cannot kick an administrator.", discord.Color.red())
        await ctx.send(embed=embed)
        return

    try:
        await member.kick(reason=f"{ctx.author}: {reason}")
        embed = create_embed(
            "👢 User Kicked",
            f"**User:** {member.mention}\n"
            f"**Reason:** {reason}\n"
            f"**By:** {ctx.author.mention}",
            discord.Color.orange()
        )
        await ctx.send(embed=embed)
    except discord.Forbidden:
        embed = create_embed("❌ Error", "I don't have permission to kick this user.", discord.Color.red())
        await ctx.send(embed=embed)

@bot.command(name="ban")
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason="No reason"):
    """Ban a user from the server"""
    if member.guild_permissions.administrator:
        embed = create_embed("❌ Error", "Cannot ban an administrator.", discord.Color.red())
        await ctx.send(embed=embed)
        return

    try:
        await member.ban(reason=f"{ctx.author}: {reason}")
        embed = create_embed(
            "🔨 User Banned",
            f"**User:** {member.mention}\n"
            f"**Reason:** {reason}\n"
            f"**By:** {ctx.author.mention}",
            discord.Color.red()
        )
        await ctx.send(embed=embed)
    except discord.Forbidden:
        embed = create_embed("❌ Error", "I don't have permission to ban this user.", discord.Color.red())
        await ctx.send(embed=embed)

@bot.command(name="clear", aliases=["purge"])
@commands.has_permissions(manage_messages=True)
async def clear(ctx, amount: int = 10):
    """Clear messages from a channel"""
    if amount < 1 or amount > 100:
        embed = create_embed("❌ Error", "Amount must be between 1 and 100.", discord.Color.red())
        await ctx.send(embed=embed, delete_after=5)
        return

    try:
        deleted = await ctx.channel.purge(limit=amount + 1)
        embed = create_embed(
            "🧹 Messages Cleared",
            f"Cleared **{len(deleted)-1}** messages",
            discord.Color.green()
        )
        msg = await ctx.send(embed=embed)
        await asyncio.sleep(3)
        await msg.delete()
    except discord.Forbidden:
        embed = create_embed("❌ Error", "I don't have permission to delete messages.", discord.Color.red())
        await ctx.send(embed=embed, delete_after=5)
      # ===== WARNING SYSTEM =====

@bot.command(name="warn")
@commands.has_permissions(manage_messages=True)
async def warn(ctx, member: discord.Member, *, reason="No reason"):
    """Warn a user"""
    if member.guild_permissions.administrator:
        embed = create_embed("❌ Error", "Cannot warn an administrator.", discord.Color.red())
        await ctx.send(embed=embed)
        return

    user_id = str(member.id)
    guild_id = str(ctx.guild.id)
    if guild_id not in bot.warnings:
        bot.warnings[guild_id] = {}
    bot.warnings[guild_id][user_id] = bot.warnings[guild_id].get(user_id, 0) + 1
    save_data()
    asyncio.create_task(async_save_warnings())

    embed = create_embed(
        "⚠️ User Warned",
        f"**User:** {member.mention}\n"
        f"**Reason:** {reason}\n"
        f"**Total Warnings:** {bot.warnings[guild_id][user_id]}\n"
        f"**By:** {ctx.author.mention}",
        discord.Color.orange()
    )
    await ctx.send(embed=embed)

@bot.command(name="warnings")
async def warnings(ctx, member: discord.Member = None):
    """Check warnings for a user"""
    target = member or ctx.author
    user_id = str(target.id)
    guild_id = str(ctx.guild.id)
    count = bot.warnings.get(guild_id, {}).get(user_id, 0)

    embed = create_embed(
        f"📊 Warnings for {target.name}",
        f"**Total Warnings:** {count}\n"
        f"**User:** {target.mention}",
        discord.Color.blue() if count == 0 else discord.Color.orange() if count < 3 else discord.Color.red()
    )
    await ctx.send(embed=embed)
  # ===== ECONOMY COMMANDS =====

@bot.command(name="balance", aliases=["bal", "money"])
async def balance(ctx, member: discord.Member = None):
    """Check your balance or another user's balance"""
    target = member or ctx.author
    user_id = str(target.id)

    wallet = bot.wallets.get(user_id, 0)
    bank = bot.banks.get(user_id, 0)
    total = wallet + bank

    embed = create_embed(
        f"💰 {target.name}'s Balance",
        f"**Wallet:** {format_money(wallet)}\n"
        f"**Bank:** {format_money(bank)}\n"
        f"**Total:** {format_money(total)}",
        discord.Color.gold()
    )

    if member:
        embed.set_footer(text=f"Requested by {ctx.author.name}")

    await ctx.send(embed=embed)

@bot.command(name="daily")
async def daily(ctx):
    """Claim daily money"""
    user_id = str(ctx.author.id)

    last_claim = bot.last_daily.get(user_id)
    if last_claim:
        last_time = datetime.datetime.fromisoformat(last_claim)
        time_since = datetime.datetime.now() - last_time

        if time_since.total_seconds() < 86400:
            hours_left = 23 - int(time_since.seconds // 3600)
            minutes_left = 59 - int((time_since.seconds % 3600) // 60)

            embed = create_embed(
                "⏳ Daily Reward Cooldown",
                f"You already claimed your daily today!\n"
                f"Come back in **{hours_left}h {minutes_left}m**",
                discord.Color.orange()
            )
            await ctx.send(embed=embed)
            return

    amount = 10000
    bot.wallets[user_id] = bot.wallets.get(user_id, 0) + amount
    bot.last_daily[user_id] = datetime.datetime.now().isoformat()
    save_economy()
    asyncio.create_task(async_save_economy())

    embed = create_embed(
        "💰 Daily Reward Claimed!",
        f"You claimed **{format_money(amount)}**!\n"
        f"**New Balance:** {format_money(bot.wallets[user_id])}",
        discord.Color.green()
    )
    await ctx.send(embed=embed)

@bot.command(name="work")
async def work(ctx):
    """Work to earn money (1 hour cooldown)"""
    user_id = str(ctx.author.id)

    last_work = bot.last_work.get(user_id)
    if last_work:
        last_time = datetime.datetime.fromisoformat(last_work)
        time_since = datetime.datetime.now() - last_time

        if time_since.total_seconds() < 3600:
            minutes_left = 59 - int((time_since.seconds % 3600) // 60)
            seconds_left = 59 - (time_since.seconds % 60)

            embed = create_embed(
                "⏳ Work Cooldown",
                f"You can work again in **{minutes_left}m {seconds_left}s**",
                discord.Color.orange()
            )
            await ctx.send(embed=embed)
            return

    amount = random.randint(5000, 20000)
    bot.wallets[user_id] = bot.wallets.get(user_id, 0) + amount
    bot.last_work[user_id] = datetime.datetime.now().isoformat()
    save_economy()
    asyncio.create_task(async_save_economy())

    jobs = [
        "worked at a coffee shop ☕",
        "fixed some computers 💻",
        "delivered packages 📦",
        "did some freelance work 💼",
        "worked as a cashier 🏪",
        "did some gardening 🌱",
        "fixed cars at a garage 🚗",
        "did some construction work 🏗️"
    ]

    job = random.choice(jobs)

    embed = create_embed(
        "💼 Work Complete!",
        f"You {job} and earned **{format_money(amount)}**!\n"
        f"**New Balance:** {format_money(bot.wallets[user_id])}",
        discord.Color.green()
    )
    await ctx.send(embed=embed)

@bot.command(name="deposit", aliases=["dep"])
async def deposit(ctx, amount: str):
    """Deposit money to bank"""
    user_id = str(ctx.author.id)
    wallet = bot.wallets.get(user_id, 0)

    if amount.lower() == "all":
        amount_num = wallet
    else:
        try:
            amount_num = int(amount)
            if amount_num <= 0:
                embed = create_embed("❌ Error", "Amount must be positive!", discord.Color.red())
                await ctx.send(embed=embed)
                return
        except ValueError:
            embed = create_embed("❌ Error", "Invalid amount! Use a number or 'all'.", discord.Color.red())
            await ctx.send(embed=embed)
            return

    if wallet < amount_num:
        embed = create_embed(
            "❌ Error",
            f"You only have **{format_money(wallet)}** in your wallet!",
            discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    bot.wallets[user_id] = wallet - amount_num
    bot.banks[user_id] = bot.banks.get(user_id, 0) + amount_num
    save_economy()
    asyncio.create_task(async_save_economy())

    embed = create_embed(
        "🏦 Deposit Successful",
        f"Deposited **{format_money(amount_num)}** to your bank!\n"
        f"**New Wallet:** {format_money(bot.wallets[user_id])}\n"
        f"**New Bank:** {format_money(bot.banks[user_id])}",
        discord.Color.green()
    )
    await ctx.send(embed=embed)

@bot.command(name="withdraw", aliases=["with"])
async def withdraw(ctx, amount: str):
    """Withdraw money from bank"""
    user_id = str(ctx.author.id)
    bank = bot.banks.get(user_id, 0)

    if amount.lower() == "all":
        amount_num = bank
    else:
        try:
            amount_num = int(amount)
            if amount_num <= 0:
                embed = create_embed("❌ Error", "Amount must be positive!", discord.Color.red())
                await ctx.send(embed=embed)
                return
        except ValueError:
            embed = create_embed("❌ Error", "Invalid amount! Use a number or 'all'.", discord.Color.red())
            await ctx.send(embed=embed)
            return

    if bank < amount_num:
        embed = create_embed(
            "❌ Error",
            f"You only have **{format_money(bank)}** in your bank!",
            discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    bot.banks[user_id] = bank - amount_num
    bot.wallets[user_id] = bot.wallets.get(user_id, 0) + amount_num
    save_economy()
    asyncio.create_task(async_save_economy())

    embed = create_embed(
        "💵 Withdrawal Successful",
        f"Withdrew **{format_money(amount_num)}** from your bank!\n"
        f"**New Wallet:** {format_money(bot.wallets[user_id])}\n"
        f"**New Bank:** {format_money(bot.banks[user_id])}",
        discord.Color.green()
    )
    await ctx.send(embed=embed)

@bot.command(name="transfer", aliases=["pay"])
async def transfer(ctx, member: discord.Member, amount: int):
    """Transfer money to another user"""
    if amount <= 0:
        embed = create_embed("❌ Error", "Amount must be positive!", discord.Color.red())
        await ctx.send(embed=embed)
        return

    if member.id == ctx.author.id:
        embed = create_embed("❌ Error", "You can't transfer to yourself!", discord.Color.red())
        await ctx.send(embed=embed)
        return

    if member.bot:
        embed = create_embed("❌ Error", "You can't transfer to bots!", discord.Color.red())
        await ctx.send(embed=embed)
        return

    sender_id = str(ctx.author.id)
    receiver_id = str(member.id)

    sender_wallet = bot.wallets.get(sender_id, 0)
    if sender_wallet < amount:
        embed = create_embed(
            "❌ Error",
            f"You only have **{format_money(sender_wallet)}** in your wallet!",
            discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    tax = int(amount * 0.02)
    transfer_amount = amount - tax

    bot.wallets[sender_id] = sender_wallet - amount
    bot.wallets[receiver_id] = bot.wallets.get(receiver_id, 0) + transfer_amount
    save_economy()
    asyncio.create_task(async_save_economy())

    embed = create_embed(
        "💸 Transfer Successful",
        f"**From:** {ctx.author.mention}\n"
        f"**To:** {member.mention}\n"
        f"**Amount:** {format_money(transfer_amount)}\n"
        f"**Tax (2%):** {format_money(tax)}\n"
        f"**Total Sent:** {format_money(amount)}\n\n"
        f"**Your New Balance:** {format_money(bot.wallets[sender_id])}",
        discord.Color.green()
    )
    await ctx.send(embed=embed)
  # ===== GAMBLING COMMANDS =====

@bot.command(name="gamble")
async def gamble(ctx, amount: int):
    """
    Gamble your money (45% chance to win 1.5x)
    """
    if amount <= 0:
        embed = create_embed("❌ Error", "Amount must be positive!", discord.Color.red())
        await ctx.send(embed=embed)
        return

    user_id = str(ctx.author.id)
    wallet = bot.wallets.get(user_id, 0)

    if wallet < amount:
        embed = create_embed(
            "❌ Error",
            f"You only have **{format_money(wallet)}** in your wallet!",
            discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    if random.random() < 0.45:
        win_amount = int(amount * 1.5)
        bot.wallets[user_id] = wallet + win_amount
        result = f"🎰 **You won {format_money(win_amount)}!**"
        color = discord.Color.green()
        profit = win_amount - amount
        title = "🎲 Gambling Win!"
    else:
        bot.wallets[user_id] = wallet - amount
        result = f"🎰 **You lost {format_money(amount)}!**"
        color = discord.Color.red()
        profit = -amount
        title = "🎲 Gambling Loss"

    save_economy()
    asyncio.create_task(async_save_economy())

    embed = create_embed(
        title,
        f"{result}\n"
        f"**Profit/Loss:** {format_money(profit)}\n"
        f"**New Balance:** {format_money(bot.wallets[user_id])}\n"
        f"**Chance:** 45% to win 1.5x",
        color
    )
    await ctx.send(embed=embed)

@bot.command(name="coinflip", aliases=["cf", "flip"])
async def coinflip(ctx, choice: str, amount: int):
    """
    Heads or Tails gambling (50/50 chance)
    Usage: !coinflip <heads/tails> <amount>
    """
    choice = choice.lower()
    if choice in ["h", "head", "heads"]:
        user_choice = "heads"
        choice_emoji = "🪙"
    elif choice in ["t", "tail", "tails"]:
        user_choice = "tails"
        choice_emoji = "🪙"
    else:
        embed = create_embed(
            "❌ Invalid Choice",
            "Choose **heads** or **tails**!\n"
            "**Examples:**\n"
            "• `!coinflip heads 1000`\n"
            "• `!coinflip tails 5000`\n"
            "• `!cf h 2000` (h = heads, t = tails)",
            discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    if amount <= 0:
        embed = create_embed("❌ Error", "Amount must be positive!", discord.Color.red())
        await ctx.send(embed=embed)
        return

    user_id = str(ctx.author.id)
    wallet = bot.wallets.get(user_id, 0)

    if wallet < amount:
        embed = create_embed(
            "❌ Insufficient Funds",
            f"You only have **{format_money(wallet)}** in your wallet!\n"
            f"You need **{format_money(amount)}** to play.",
            discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    coin_result = random.choice(["heads", "tails"])
    coin_emoji = "🪙" if coin_result == "heads" else "🪙"
    result_emoji = "💎" if coin_result == "heads" else "🪙"

    win = user_choice == coin_result

    embed = create_embed(
        f"{choice_emoji} Coin Flip!",
        f"**Your bet:** {format_money(amount)} on **{user_choice}**\n"
        f"**Flipping coin...**",
        discord.Color.blue()
    )

    message = await ctx.send(embed=embed)
    await asyncio.sleep(1.5)

    if win:
        win_amount = amount * 2
        bot.wallets[user_id] = wallet + win_amount
        result_text = f"**{result_emoji} It's {coin_result}! You won {format_money(win_amount)}!**"
        color = discord.Color.green()
        profit = win_amount - amount
        title = f"🎉 {result_emoji} You Win!"
    else:
        bot.wallets[user_id] = wallet - amount
        result_text = f"**{result_emoji} It's {coin_result}! You lost {format_money(amount)}.**"
        color = discord.Color.red()
        profit = -amount
        title = f"💸 {result_emoji} You Lose"

    save_economy()
    asyncio.create_task(async_save_economy())

    embed = create_embed(
        title,
        f"{result_text}\n\n"
        f"**Your Choice:** {user_choice}\n"
        f"**Coin Result:** {coin_result}\n"
        f"**Bet Amount:** {format_money(amount)}\n"
        f"**Profit/Loss:** {format_money(profit)}\n"
        f"**New Balance:** {format_money(bot.wallets[user_id])}",
        color
    )

    await message.edit(embed=embed)
  # ===== BUSINESS SYSTEM =====

@bot.command(name="createbusiness", aliases=["startbusiness"])
async def createbusiness(ctx, business_type: str, business_name: str, investment: int):
    """
    Start your own business!
    Types: cafe, shop, factory, farm, tech, restaurant
    Example: !createbusiness cafe "Coffee Corner" 50000
    """
    user_id = str(ctx.author.id)
    wallet = bot.wallets.get(user_id, 0)

    if investment < 10000:
        embed = create_embed(
            "❌ Investment Too Low",
            "Minimum investment is $10,000!\n"
            "Business types and their minimum investments:\n"
            "• Cafe: $10,000\n• Shop: $20,000\n• Factory: $50,000\n"
            "• Farm: $30,000\n• Tech: $100,000\n• Restaurant: $40,000",
            discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    if wallet < investment:
        embed = create_embed(
            "❌ Insufficient Funds",
            f"You need {format_money(investment)} but only have {format_money(wallet)}!",
            discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    if user_id in bot.businesses:
        embed = create_embed(
            "❌ Business Limit",
            "You already own a business! You can only own one business at a time.",
            discord.Color.red()
        )
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
            f"Available types: {', '.join(valid_types.keys())}\n"
            "Example: `!createbusiness cafe \"Coffee Corner\" 50000`",
            discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    type_info = valid_types[business_type]
    if investment < type_info["min"]:
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
        "investment": investment,
        "profit_rate": type_info["profit"],
        "created_at": datetime.datetime.now().isoformat(),
        "last_profit": None,
        "total_profit": 0,
        "level": 1,
        "emoji": type_info["emoji"]
    }

    bot.wallets[user_id] = wallet - investment
    save_economy()
    asyncio.create_task(async_save_economy())

    daily_profit = int(investment * type_info["profit"])

    embed = create_embed(
        f"🏢 Business Created! {type_info['emoji']}",
        f"**Business Name:** {business_name}\n"
        f"**Type:** {business_type.title()}\n"
        f"**Investment:** {format_money(investment)}\n"
        f"**Daily Profit:** {format_money(daily_profit)}\n"
        f"**Profit Rate:** {type_info['profit']*100}%\n"
        f"**Level:** 1\n\n"
        f"Your business will generate profits every 24 hours!\n"
        f"Use `!mybusiness` to check your business status.",
        discord.Color.green()
    )
    await ctx.send(embed=embed)

@bot.command(name="mybusiness", aliases=["business", "mybiz"])
async def mybusiness(ctx):
    """Check your business status"""
    user_id = str(ctx.author.id)

    if user_id not in bot.businesses:
        embed = create_embed(
            "🏢 No Business",
            "You don't own a business yet!\n"
            "Start one with `!createbusiness <type> <name> <investment>`\n\n"
            "**Available Types:**\n"
            "• `cafe` - Coffee shop (min: $10,000)\n"
            "• `shop` - Retail store (min: $20,000)\n"
            "• `factory` - Manufacturing (min: $50,000)\n"
            "• `farm` - Agriculture (min: $30,000)\n"
            "• `tech` - Technology (min: $100,000)\n"
            "• `restaurant` - Food service (min: $40,000)",
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
        f"**Type:** {business['type'].title()}\n"
        f"**Level:** {business['level']}\n"
        f"**Investment:** {format_money(business['investment'])}\n"
        f"**Daily Profit:** {format_money(daily_profit)}\n"
        f"**Total Profits:** {format_money(business['total_profit'])}\n"
        f"**Last Profit:** {last_profit_text}\n"
        f"**Next Profit In:** ~{next_profit_in} hours\n\n"
        f"**Commands:**\n"
        f"• `!upgradebusiness` - Upgrade your business\n"
        f"• `!collectprofit` - Collect your profits\n"
        f"• `!closebusiness` - Close your business",
        discord.Color.gold()
    )
    await ctx.send(embed=embed)

@bot.command(name="collectprofit")
async def collectprofit(ctx):
    """Collect your business profits"""
    user_id = str(ctx.author.id)

    if user_id not in bot.businesses:
        embed = create_embed("❌ No Business", "You don't own a business!", discord.Color.red())
        await ctx.send(embed=embed)
        return

    business = bot.businesses[user_id]

    if business["last_profit"]:
        last_time = datetime.datetime.fromisoformat(business["last_profit"])
        time_since = datetime.datetime.now() - last_time

        if time_since.total_seconds() < 86400:
            hours_left = 23 - int(time_since.seconds // 3600)
            minutes_left = 59 - int((time_since.seconds % 3600) // 60)

            embed = create_embed(
                "⏳ Profit Not Ready",
                f"Your business needs more time to generate profits!\n"
                f"Come back in **{hours_left}h {minutes_left}m**",
                discord.Color.orange()
            )
            await ctx.send(embed=embed)
            return

    daily_profit = int(business["investment"] * business["profit_rate"])
    business["total_profit"] += daily_profit
    business["last_profit"] = datetime.datetime.now().isoformat()

    bot.wallets[user_id] = bot.wallets.get(user_id, 0) + daily_profit
    save_economy()
    asyncio.create_task(async_save_economy())

    embed = create_embed(
        f"💰 Profit Collected! {business['emoji']}",
        f"**Business:** {business['name']}\n"
        f"**Profit Collected:** {format_money(daily_profit)}\n"
        f"**Total Profits:** {format_money(business['total_profit'])}\n"
        f"**New Balance:** {format_money(bot.wallets[user_id])}\n\n"
        f"Your business will generate more profits in 24 hours!",
        discord.Color.green()
    )
    await ctx.send(embed=embed)

@bot.command(name="upgradebusiness")
async def upgradebusiness(ctx):
    """Upgrade your business to increase profits"""
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

    new_daily_profit = int(business["investment"] * business["profit_rate"])

    embed = create_embed(
        f"⬆️ Business Upgraded! {business['emoji']}",
        f"**Business:** {business['name']}\n"
        f"**New Level:** {business['level']}\n"
        f"**New Investment:** {format_money(business['investment'])}\n"
        f"**New Daily Profit:** {format_money(new_daily_profit)}\n"
        f"**Upgrade Cost:** {format_money(int(upgrade_cost))}\n\n"
        f"Your business is now more profitable!",
        discord.Color.green()
    )
    await ctx.send(embed=embed)

@bot.command(name="closebusiness")
async def closebusiness(ctx):
    """Close your business and get back your investment"""
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

    embed = create_embed(
        f"🏢 Business Closed",
        f"**Business:** {business['name']}\n"
        f"**Refund Received:** {format_money(refund)}\n"
        f"**Total Profits Made:** {format_money(business['total_profit'])}\n"
        f"**New Balance:** {format_money(bot.wallets[user_id])}\n\n"
        f"You can start a new business anytime with `!createbusiness`",
        discord.Color.orange()
    )
    await ctx.send(embed=embed)
  # ===== SHOP SYSTEM =====

@bot.command(name="shop")
async def shop(ctx, category: str = None):
    """Browse the shop"""
    if not category:
        categories_text = ""
        for cat in bot.shop_items:
            if bot.shop_items[cat]:
                item_count = len(bot.shop_items[cat])
                categories_text += f"• `!shop {cat}` - {item_count} item{'s' if item_count != 1 else ''}\n"

        embed = create_embed(
            "🛒 Shop - Categories",
            f"**Available Categories:**\n{categories_text}\n"
            f"**How to buy:** `!buy <category> <item_name>`\n"
            f"**Example:** `!buy roles VIP`\n\n"
            f"**Your Balance:** {format_money(bot.wallets.get(str(ctx.author.id), 0))}",
            discord.Color.blue()
        )
        await ctx.send(embed=embed)
        return

    category = category.lower()
    if category not in bot.shop_items or not bot.shop_items[category]:
        embed = create_embed(
            "❌ Shop Error",
            f"No items in **{category}** category yet!\n"
            f"Admins can add items with `!addshopitem {category} <name> <price> <description>`",
            discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    items = bot.shop_items[category]

    embed = create_embed(
        f"🛒 {category.title()} Shop",
        f"Use `!buy {category} <item_name>` to purchase\n"
        f"**Your Balance:** {format_money(bot.wallets.get(str(ctx.author.id), 0))}",
        discord.Color.blue()
    )

    for i, item in enumerate(items, 1):
        emoji = item.get("emoji", "📦")
        price = item['price']
        name = item['name']
        desc = item.get('description', 'No description')

        embed.add_field(
            name=f"{emoji} {i}. {name} - {format_money(price)}",
            value=f"{desc}",
            inline=False
        )

    await ctx.send(embed=embed)

@bot.command(name="buy")
async def buy(ctx, category: str = None, *, item_name: str = None):
    """Buy an item from the shop"""
    if not category or not item_name:
        embed = create_embed(
            "❌ Usage Error",
            "**Usage:** `!buy <category> <item_name>`\n"
            "**Example:** `!buy roles VIP`\n\n"
            "Use `!shop` to see available categories and items.",
            discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    category = category.lower()
    if category not in bot.shop_items:
        embed = create_embed(
            "❌ Shop Error",
            f"Category **{category}** not found!\n"
            f"Use `!shop` to see available categories.",
            discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    item = None
    for shop_item in bot.shop_items[category]:
        if shop_item["name"].lower() == item_name.lower():
            item = shop_item
            break

    if not item:
        embed = create_embed(
            "❌ Shop Error",
            f"Item **{item_name}** not found in {category} category!\n"
            f"Use `!shop {category}` to see available items.",
            discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    user_id = str(ctx.author.id)
    wallet = bot.wallets.get(user_id, 0)

    if wallet < item["price"]:
        embed = create_embed(
            "❌ Insufficient Funds",
            f"You need **{format_money(item['price'])}** but only have **{format_money(wallet)}**!\n"
            f"Use `!work` or `!daily` to earn more money.",
            discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    if category == "roles":
        role_name = item["name"]
        role = discord.utils.get(ctx.guild.roles, name=role_name)

        if not role:
            try:
                role = await ctx.guild.create_role(
                    name=role_name,
                    color=discord.Color.gold(),
                    reason="Purchased from shop"
                )
            except discord.Forbidden:
                embed = create_embed(
                    "❌ Permission Error",
                    "I don't have permission to create roles!",
                    discord.Color.red()
                )
                await ctx.send(embed=embed)
                return

        if role in ctx.author.roles:
            embed = create_embed(
                "❌ Already Owned",
                f"You already have the **{role_name}** role!",
                discord.Color.orange()
            )
            await ctx.send(embed=embed)
            return

        try:
            await ctx.author.add_roles(role)
        except discord.Forbidden:
            embed = create_embed(
                "❌ Permission Error",
                "I don't have permission to give you this role!",
                discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

    bot.wallets[user_id] = wallet - item["price"]

    if user_id not in bot.owned_items:
        bot.owned_items[user_id] = {}

    if category not in bot.owned_items[user_id]:
        bot.owned_items[user_id][category] = []

    bot.owned_items[user_id][category].append(item["name"])

    save_economy()
    asyncio.create_task(async_save_economy())

    embed = create_embed(
        "✅ Purchase Successful!",
        f"You bought **{item['name']}** for **{format_money(item['price'])}**!",
        discord.Color.green()
    )

    if category == "roles":
        embed.add_field(
            name="🎭 Role Added",
            value=f"You now have the **{item['name']}** role!",
            inline=False
        )

    embed.add_field(
        name="💰 New Balance",
        value=f"**{format_money(bot.wallets[user_id])}**",
        inline=False
    )

    await ctx.send(embed=embed)

@bot.command(name="inventory", aliases=["inv", "items"])
async def inventory(ctx, member: discord.Member = None):
    """Check your inventory or another user's inventory"""
    target = member or ctx.author
    user_id = str(target.id)

    if user_id not in bot.owned_items or not bot.owned_items[user_id]:
        embed = create_embed(
            f"📦 {target.name}'s Inventory",
            f"{target.name} doesn't own any items yet!\n"
            f"Visit the shop with `!shop` to buy items.",
            discord.Color.blue()
        )
        await ctx.send(embed=embed)
        return

    total_items = sum(len(items) for items in bot.owned_items[user_id].values())

    embed = create_embed(
        f"📦 {target.name}'s Inventory",
        f"**Total Items:** {total_items}",
        discord.Color.blue()
    )

    for category, items in bot.owned_items[user_id].items():
        if items:
            items_text = "\n".join([f"• {item}" for item in items[:10]])
            if len(items) > 10:
                items_text += f"\n• ... and {len(items)-10} more"

            embed.add_field(
                name=f"{category.title()} ({len(items)})",
                value=items_text,
                inline=False
            )

    if member:
        embed.set_footer(text=f"Requested by {ctx.author.name}")

    await ctx.send(embed=embed)

@bot.command(name="rich", aliases=["leaderboard", "top", "lb"])
async def rich(ctx):
    """Show richest users"""
    users = []
    for user_id, wallet in bot.wallets.items():
        bank = bot.banks.get(user_id, 0)
        total = wallet + bank
        if total > 0:
            try:
                user = await bot.fetch_user(int(user_id))
                users.append((user.name, total, user_id))
            except:
                continue

    users.sort(key=lambda x: x[1], reverse=True)

    if not users:
        embed = create_embed(
            "🏆 Richest Users",
            "No one has any money yet! Use `!daily` or `!work` to get started.",
            discord.Color.gold()
        )
        await ctx.send(embed=embed)
        return

    embed = create_embed(
        "🏆 Richest Users",
        "Total wealth (wallet + bank)",
        discord.Color.gold()
    )

    for i, (name, money, user_id) in enumerate(users[:10], 1):
        medal = ""
        if i == 1: medal = "🥇"
        elif i == 2: medal = "🥈"
        elif i == 3: medal = "🥉"

        try:
            member = ctx.guild.get_member(int(user_id))
            if member:
                display_name = f"{member.mention}"
            else:
                display_name = name
        except:
            display_name = name

        embed.add_field(
            name=f"{medal} {i}. {display_name}",
            value=f"**{format_money(money)}**",
            inline=False
        )

    current_user_id = str(ctx.author.id)
    current_wallet = bot.wallets.get(current_user_id, 0)
    current_bank = bot.banks.get(current_user_id, 0)
    current_total = current_wallet + current_bank

    rank = None
    for i, (_, money, uid) in enumerate(users, 1):
        if uid == current_user_id:
            rank = i
            break

    if rank:
        embed.set_footer(
            text=f"Your rank: #{rank} with {format_money(current_total)}"
        )
    else:
        embed.set_footer(
            text=f"You're not on the leaderboard yet! Use !daily to get started"
        )

    await ctx.send(embed=embed)
  # ===== COUNTRY GAME COMMANDS =====

@bot.command(name="startcountrygame")
@commands.has_permissions(manage_messages=True)
async def startcountrygame(ctx, game_type: str, continent: str, rounds: int = -1):
    """
    Start a country guessing game (flag or capital)
    Usage: !startcountrygame <flag/capital> <continent> [rounds]
    - rounds: number of rounds to play (default = infinite, -1)
    """
    guild_id = str(ctx.guild.id)

    if guild_id in bot.active_games and bot.active_games[guild_id].get("active", False):
        await ctx.send("❌ A game is already running! Use `!stopcountrygame` first.")
        return

    if continent not in bot.countries:
        await ctx.send(f"❌ Continent not available. Choose from: {', '.join(bot.countries.keys())}")
        return

    if game_type not in ["flag", "capital"]:
        await ctx.send("❌ Game type must be 'flag' or 'capital'")
        return

    if rounds == 0:
        await ctx.send("❌ Number of rounds must be greater than 0 (or -1 for infinite).")
        return
    if rounds < -1:
        await ctx.send("❌ Invalid round count. Use -1 for infinite or a positive number.")
        return

    bot.active_games[guild_id] = {
        "active": True,
        "game_type": game_type,
        "continent": continent,
        "rounds": rounds,
        "round_count": 0,
        "winners": [],
        "paused": False,
        "channel_id": ctx.channel.id
    }

    await next_country_round(ctx.guild)

    round_info = f"**Rounds:** {'Infinite' if rounds == -1 else rounds}"
    embed = create_embed(
        "🏁 Country Game Started!",
        f"**Type:** {'Flag Guessing' if game_type == 'flag' else 'Capital Guessing'}\n"
        f"**Continent:** {continent}\n"
        f"{round_info}\n"
        f"**Rules:** Guess the {'country or capital from flag' if game_type == 'flag' else 'capital of the country'}\n"
        f"**Points:** 🥇 3pts 🥈 2pts 🥉 1pt",
        discord.Color.blue()
    )
    await ctx.send(embed=embed)

@bot.command(name="pausegame")
@commands.has_permissions(manage_messages=True)
async def pausegame(ctx):
    """Pause the current country game"""
    guild_id = str(ctx.guild.id)

    if guild_id not in bot.active_games or not bot.active_games[guild_id].get("active", False):
        await ctx.send("❌ No active game to pause!")
        return

    bot.active_games[guild_id]["paused"] = True
    await ctx.send("⏸️ Game paused! Use `!resumegame` to continue.")

@bot.command(name="resumegame")
@commands.has_permissions(manage_messages=True)
async def resumegame(ctx):
    """Resume paused country game"""
    guild_id = str(ctx.guild.id)

    if guild_id not in bot.active_games:
        await ctx.send("❌ No game to resume!")
        return

    if not bot.active_games[guild_id].get("paused", False):
        await ctx.send("❌ Game is not paused!")
        return

    bot.active_games[guild_id]["paused"] = False
    await ctx.send("▶️ Game resumed!")
    await next_country_round(ctx.guild)

@bot.command(name="stopcountrygame")
@commands.has_permissions(manage_messages=True)
async def stopcountrygame(ctx):
    """Stop the country game"""
    guild_id = str(ctx.guild.id)

    if guild_id not in bot.active_games or not bot.active_games[guild_id].get("active", False):
        await ctx.send("❌ No active game to stop!")
        return

    if "timer" in bot.active_games[guild_id]:
        bot.active_games[guild_id]["timer"].cancel()

    del bot.active_games[guild_id]

    embed = create_embed(
        "🛑 Game Stopped",
        "The country guessing game has been stopped.",
        discord.Color.red()
    )
    await ctx.send(embed=embed)

@bot.command(name="countryleaderboard", aliases=["countrylb", "countryscores"])
async def countryleaderboard(ctx):
    """Show country game leaderboard"""
    if not bot.country_scores:
        await ctx.send("📊 No country game scores yet! Start a game with `!startcountrygame`")
        return

    sorted_scores = sorted(bot.country_scores.items(), key=lambda x: x[1], reverse=True)

    embed = create_embed(
        "🏆 Country Game Leaderboard",
        "Top players in flag/capital guessing",
        discord.Color.gold()
    )

    for i, (user_id, score) in enumerate(sorted_scores[:10], 1):
        try:
            user = await bot.fetch_user(int(user_id))
            name = user.name
        except:
            name = f"User {user_id}"

        medal = ""
        if i == 1: medal = "🥇"
        elif i == 2: medal = "🥈"
        elif i == 3: medal = "🥉"

        embed.add_field(
            name=f"{medal} {i}. {name}",
            value=f"**{score} points**",
            inline=False
        )

    await ctx.send(embed=embed)
  # ===== QUARANTINE SYSTEM =====

@bot.command(name="q")  # Changed from "quarantine" to "q"
@commands.has_permissions(manage_messages=True)
async def quarantine(ctx, member: discord.Member, *, reason="No reason provided"):
    """Quarantine a user to a separate channel"""
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
            quarantine_category = await ctx.guild.create_category(
                name="Quarantine",
                reason="Quarantine system"
            )
            staff_role_names = [
                "president",
                "vice president",
                "prime minister",
                "Chief of staff",
                "Attorney general",
                "LEGENDARY",
                "Hall of famers",
                "Admin",
                "Mod",
                "sergeant"
            ]
            for role in ctx.guild.roles:
                if role.name in staff_role_names or role.permissions.administrator:
                    await quarantine_category.set_permissions(role, view_channel=True, send_messages=True, read_messages=True)
                else:
                    await quarantine_category.set_permissions(role, view_channel=False)
        except discord.Forbidden:
            embed = create_embed("❌ Error", "I don't have permission to create categories!", discord.Color.red())
            await ctx.send(embed=embed)
            return

    channel_name = f"quarantine-{member.name.lower()}"
    try:
        existing_channel = discord.utils.get(quarantine_category.channels, name=channel_name)
        if existing_channel:
            await existing_channel.delete()

        overwrites = {
            ctx.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_messages=True),
            ctx.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_messages=True)
        }

        staff_role_names = [
            "president",
            "vice president",
            "prime minister",
            "Chief of staff",
            "Attorney general",
            "LEGENDARY",
            "Hall of famers",
            "Admin",
            "Mod",
            "sergeant"
        ]
        for role in ctx.guild.roles:
            if role.name in staff_role_names or role.permissions.administrator:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_messages=True)

        quarantine_channel = await ctx.guild.create_text_channel(
            name=channel_name,
            category=quarantine_category,
            overwrites=overwrites,
            reason=f"Quarantine for {member.name}"
        )
    except discord.Forbidden:
        embed = create_embed("❌ Error", "I don't have permission to create channels!", discord.Color.red())
        await ctx.send(embed=embed)
        return

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
        f"**User:** {member.mention}\n"
        f"**Reason:** {reason}\n"
        f"**By:** {ctx.author.mention}\n"
        f"**Channel:** {quarantine_channel.mention}\n\n"
        f"The user can only talk in the quarantine channel until released.",
        discord.Color.orange()
    )
    await ctx.send(embed=embed)

    quarantine_embed = create_embed(
        "🦠 You have been quarantined",
        f"You have been placed in quarantine by {ctx.author.mention}\n"
        f"**Reason:** {reason}\n\n"
        f"You can only communicate in this channel until a staff member releases you.\n"
        f"Please follow the server rules and await further instructions.",
        discord.Color.orange()
    )
    await quarantine_channel.send(f"{member.mention}", embed=quarantine_embed)

@bot.command(name="uq")  # Changed from "unquarantine" to "uq"
@commands.has_permissions(manage_messages=True)
async def unquarantine(ctx, member: discord.Member):
    """Release a user from quarantine"""
    guild_id = str(ctx.guild.id)
    user_id = str(member.id)

    if guild_id not in bot.quarantined_users or user_id not in bot.quarantined_users[guild_id]:
        embed = create_embed("❌ Error", f"{member.mention} is not quarantined!", discord.Color.red())
        await ctx.send(embed=embed)
        return

    quarantine_info = bot.quarantined_users[guild_id][user_id]
    channel_id = quarantine_info.get("channel_id")

    if channel_id:
        try:
            channel = ctx.guild.get_channel(int(channel_id))
            if channel:
                await channel.delete(reason=f"Unquarantine {member.name}")

                if str(channel_id) in bot.quarantine_channels.get(guild_id, {}):
                    del bot.quarantine_channels[guild_id][str(channel_id)]
        except:
            pass

    del bot.quarantined_users[guild_id][user_id]

    if not bot.quarantined_users[guild_id]:
        del bot.quarantined_users[guild_id]

    save_quarantine()
    asyncio.create_task(async_save_quarantine())

    embed = create_embed(
        "✅ User Released",
        f"{member.mention} has been released from quarantine by {ctx.author.mention}\n"
        f"They can now participate in regular channels.",
        discord.Color.green()
    )
    await ctx.send(embed=embed)

    try:
        await member.send(f"🎉 You have been released from quarantine in {ctx.guild.name}!")
    except:
        pass

@bot.command(name="quarantinelist", aliases=["qlist"])
@commands.has_permissions(manage_messages=True)
async def quarantinelist(ctx):
    """List all quarantined users"""
    guild_id = str(ctx.guild.id)

    if guild_id not in bot.quarantined_users or not bot.quarantined_users[guild_id]:
        embed = create_embed("🦠 Quarantine List", "No users are currently quarantined.", discord.Color.blue())
        await ctx.send(embed=embed)
        return

    embed = create_embed(
        "🦠 Quarantined Users",
        f"Total: {len(bot.quarantined_users[guild_id])}",
        discord.Color.orange()
    )

    for user_id, info in bot.quarantined_users[guild_id].items():
        try:
            user = await bot.fetch_user(int(user_id))
            quarantined_by = await bot.fetch_user(int(info["quarantined_by"])) if info.get("quarantined_by") else "Unknown"
            quarantined_at = datetime.datetime.fromisoformat(info["quarantined_at"]).strftime("%Y-%m-%d %H:%M")

            embed.add_field(
                name=f"👤 {user.name}",
                value=f"**Reason:** {info['reason']}\n"
                      f"**By:** {quarantined_by.name}\n"
                      f"**Since:** {quarantined_at}",
                inline=False
            )
        except:
            continue

    await ctx.send(embed=embed)
  # ===== ADMIN COMMANDS =====

@bot.command(name="givemoney")
@commands.has_permissions(administrator=True)
async def givemoney(ctx, member: discord.Member, amount: int):
    """Give money to a user (Admin only)"""
    if amount <= 0:
        embed = create_embed("❌ Error", "Amount must be positive!", discord.Color.red())
        await ctx.send(embed=embed)
        return

    user_id = str(member.id)
    bot.wallets[user_id] = bot.wallets.get(user_id, 0) + amount
    save_economy()
    asyncio.create_task(async_save_economy())

    embed = create_embed(
        "✅ Money Given",
        f"Gave **{format_money(amount)}** to {member.mention}\n"
        f"**Their New Balance:** {format_money(bot.wallets[user_id])}",
        discord.Color.green()
    )
    embed.set_footer(text=f"Given by {ctx.author.name}")
    await ctx.send(embed=embed)

@bot.command(name="setbalance")
@commands.has_permissions(administrator=True)
async def setbalance(ctx, member: discord.Member, amount: int):
    """Set a user's balance (Admin only)"""
    if amount < 0:
        embed = create_embed("❌ Error", "Amount cannot be negative!", discord.Color.red())
        await ctx.send(embed=embed)
        return

    user_id = str(member.id)
    bot.wallets[user_id] = amount
    save_economy()
    asyncio.create_task(async_save_economy())

    embed = create_embed(
        "✅ Balance Set",
        f"Set {member.mention}'s wallet to **{format_money(amount)}**",
        discord.Color.green()
    )
    embed.set_footer(text=f"Set by {ctx.author.name}")
    await ctx.send(embed=embed)

@bot.command(name="addmoney")
@commands.has_permissions(administrator=True)
async def addmoney(ctx, amount: int):
    """Add money to your own wallet (Admin only)"""
    if amount <= 0:
        embed = create_embed("❌ Error", "Amount must be positive!", discord.Color.red())
        await ctx.send(embed=embed)
        return

    user_id = str(ctx.author.id)
    bot.wallets[user_id] = bot.wallets.get(user_id, 0) + amount
    save_economy()
    asyncio.create_task(async_save_economy())

    embed = create_embed(
        "✅ Money Added",
        f"Added **{format_money(amount)}** to your wallet!\n"
        f"**New Balance:** {format_money(bot.wallets[user_id])}",
        discord.Color.green()
    )
    await ctx.send(embed=embed)

@bot.command(name="addshopitem")
@commands.has_permissions(administrator=True)
async def addshopitem(ctx, category: str, name: str, price: int, *, description: str = ""):
    """Add item to shop (Admin only) - Use quotes for names with spaces!"""
    try:
        if price <= 0:
            await ctx.send("❌ Price must be greater than 0!")
            return

        category = category.lower()

        if category not in bot.shop_items:
            bot.shop_items[category] = []

        for item in bot.shop_items[category]:
            if item["name"].lower() == name.lower():
                await ctx.send(f"❌ Item '{name}' already exists in {category} category!")
                return

        new_item = {
            "name": name,
            "price": price,
            "description": description,
            "emoji": "🛍️"
        }

        bot.shop_items[category].append(new_item)

        asyncio.create_task(async_save_shop_items())
        with open(SHOP_FILE, "w") as f:
            json.dump(bot.shop_items, f, indent=2)

        embed = create_embed(
            "✅ Shop Item Added",
            f"**Item:** {name}\n"
            f"**Category:** {category}\n"
            f"**Price:** {format_money(price)}\n"
            f"**Description:** {description if description else 'No description'}\n\n"
            f"Use `!shop {category}` to view it!",
            discord.Color.green()
        )
        await ctx.send(embed=embed)

    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")

@bot.command(name="editshopitem", aliases=["edititem"])
@commands.has_permissions(administrator=True)
async def editshopitem(ctx, category: str, item_name: str, new_price: int, *, new_description: str):
    """Edit an item's price and description (Admin only)"""
    try:
        category = category.lower()

        found = False
        for item in bot.shop_items.get(category, []):
            if item["name"].lower() == item_name.lower():
                old_price = item["price"]
                old_desc = item.get("description", "No description")
                item["price"] = new_price
                item["description"] = new_description
                found = True
                break

        if not found:
            await ctx.send(f"❌ Item **{item_name}** not found in {category} category!")
            return

        asyncio.create_task(async_save_shop_items())
        with open(SHOP_FILE, "w") as f:
            json.dump(bot.shop_items, f, indent=2)

        embed = create_embed(
            "✅ Item Updated",
            f"**Item:** {item_name}\n"
            f"**Category:** {category}\n\n"
            f"**Old Price:** {format_money(old_price)}\n"
            f"**New Price:** {format_money(new_price)}\n\n"
            f"**Old Description:** {old_desc}\n"
            f"**New Description:** {new_description}",
            discord.Color.green()
        )
        await ctx.send(embed=embed)

    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")

@bot.command(name="setsalary")
@commands.has_permissions(administrator=True)
async def setsalary(ctx, role_name: str, amount: int):
    """Set daily salary for a role (Admin only)"""
    try:
        if amount < 0:
            await ctx.send("❌ Salary cannot be negative!")
            return

        role = discord.utils.get(ctx.guild.roles, name=role_name)
        if not role:
            for r in ctx.guild.roles:
                if r.name.lower() == role_name.lower():
                    role = r
                    break

        if not role:
            await ctx.send(f"❌ Role **{role_name}** not found in this server!")
            return

        exact_role_name = role.name
        bot.role_salaries[exact_role_name] = amount

        asyncio.create_task(async_save_role_salaries())
        with open(ROLE_SALARIES_FILE, "w") as f:
            json.dump(bot.role_salaries, f, indent=2)

        embed = create_embed(
            "✅ Salary Set",
            f"**Role:** {exact_role_name}\n"
            f"**Daily Salary:** {format_money(amount)}\n"
            f"**Role ID:** {role.id}\n\n"
            f"Users with the **{exact_role_name}** role will receive this amount daily in their bank.",
            discord.Color.green()
        )

        await ctx.send(embed=embed)

    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")

@bot.command(name="salarylist")
async def salarylist(ctx):
    """View all role salaries"""
    try:
        if not bot.role_salaries:
            await ctx.send("No role salaries set yet!")
            return

        embed = discord.Embed(
            title="💰 Role Salaries",
            description="Daily salaries paid to bank accounts",
            color=discord.Color.gold()
        )

        default_salary = bot.role_salaries.get("default", 1000)
        embed.add_field(
            name="👤 Default (no special role)",
            value=format_money(default_salary),
            inline=False
        )

        other_salaries = []
        for role, salary in bot.role_salaries.items():
            if role != "default":
                other_salaries.append((role, salary))

        if other_salaries:
            other_salaries.sort(key=lambda x: x[1], reverse=True)

            for role_name, salary in other_salaries:
                embed.add_field(
                    name=f"👑 {role_name}",
                    value=format_money(salary),
                    inline=True
                )

        embed.set_footer(text=f"Total special roles: {len(other_salaries)}")
        await ctx.send(embed=embed)

    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")

@bot.command(name="uptime")
async def uptime(ctx):
    """Check how long the bot has been online"""
    if not hasattr(bot, 'start_time'):
        bot.start_time = datetime.datetime.now()

    delta = datetime.datetime.now() - bot.start_time
    hours = delta.seconds // 3600
    minutes = (delta.seconds % 3600) // 60
    seconds = delta.seconds % 60

    embed = discord.Embed(
        title="🕐 Bot Uptime Stats",
        color=discord.Color.green()
    )

    embed.add_field(
        name="⏰ Online For",
        value=f"**{hours}h {minutes}m {seconds}s**",
        inline=True
    )

    embed.add_field(
        name="🔄 Since",
        value=f"{bot.start_time.strftime('%Y-%m-%d %H:%M:%S')}",
        inline=True
    )

    embed.set_footer(text=f"Requested by {ctx.author.name}")
    await ctx.send(embed=embed)

@bot.command(name="paysalary", aliases=["paysalaries", "salarypay", "forcepay"])
@commands.has_permissions(administrator=True)
async def paysalary(ctx):
    """Manually pay daily salaries to all users (Admin only)"""
    await ctx.send("💰 Processing manual salary payment...")

    salaries_given = 0
    total_amount = 0
    salary_details = {}

    for guild in bot.guilds:
        for member in guild.members:
            if not member.bot:
                user_id = str(member.id)
                salary = bot.role_salaries.get("default", 1000)
                highest_role_name = "Default"

                for role in member.roles:
                    if role.name in bot.role_salaries:
                        role_salary = bot.role_salaries[role.name]
                        if role_salary > salary:
                            salary = role_salary
                            highest_role_name = role.name

                bot.banks[user_id] = bot.banks.get(user_id, 0) + salary
                salaries_given += 1
                total_amount += salary

                if highest_role_name not in salary_details:
                    salary_details[highest_role_name] = {"count": 0, "total": 0}
                salary_details[highest_role_name]["count"] += 1
                salary_details[highest_role_name]["total"] += salary

    save_economy()
    asyncio.create_task(async_save_economy())

    with open(LAST_SALARY_FILE, "w") as f:
        json.dump({
            "last_salary": datetime.datetime.now().isoformat(),
            "salaries_given": salaries_given,
            "total_amount": total_amount,
            "date": datetime.datetime.now().strftime("%Y-%m-%d"),
            "paid_by": str(ctx.author.id),
            "manual_payment": True
        }, f, indent=2)

    embed = create_embed(
        "💰 Manual Salary Payment Complete",
        f"**Total Paid:** {format_money(total_amount)}\n"
        f"**Users Paid:** {salaries_given}\n"
        f"**Time:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        discord.Color.green()
    )

    if salary_details:
        breakdown_text = ""
        for role_name, data in salary_details.items():
            avg = data["total"] // data["count"]
            breakdown_text += f"**{role_name}:** {data['count']} users × {format_money(avg)} = {format_money(data['total'])}\n"

        embed.add_field(
            name="📊 Breakdown by Role",
            value=breakdown_text,
            inline=False
        )

    embed.set_footer(text=f"Paid by {ctx.author.name}")

    await ctx.send(embed=embed)
    print(f"✅ Manual salary payment by {ctx.author.name}: ${format_money(total_amount)} to {salaries_given} users")

# ===== BACKGROUND TASKS =====

@tasks.loop(minutes=60)
async def daily_salaries():
    """Give daily salaries, checking if 24 hours have passed"""
    try:
        with open(LAST_SALARY_FILE, "r") as f:
            last_salary_data = json.load(f)
        last_salary_time = datetime.datetime.fromisoformat(last_salary_data.get("last_salary", "2000-01-01T00:00:00"))
    except:
        last_salary_time = datetime.datetime.now() - datetime.timedelta(days=1)

    time_since_last = datetime.datetime.now() - last_salary_time

    if time_since_last.total_seconds() >= 86400:
        print("💰 24 hours passed, processing daily salaries...")

        salaries_given = 0
        total_amount = 0

        for guild in bot.guilds:
            for member in guild.members:
                if not member.bot:
                    user_id = str(member.id)
                    salary = bot.role_salaries.get("default", 1000)

                    for role in member.roles:
                        if role.name in bot.role_salaries:
                            role_salary = bot.role_salaries[role.name]
                            if role_salary > salary:
                                salary = role_salary

                    bot.banks[user_id] = bot.banks.get(user_id, 0) + salary
                    salaries_given += 1
                    total_amount += salary

        save_economy()
        asyncio.create_task(async_save_economy())

        with open(LAST_SALARY_FILE, "w") as f:
            json.dump({
                "last_salary": datetime.datetime.now().isoformat(),
                "salaries_given": salaries_given,
                "total_amount": total_amount,
                "date": datetime.datetime.now().strftime("%Y-%m-%d")
            }, f, indent=2)

        print(f"✅ Daily salaries processed! ${format_money(total_amount)} given to {salaries_given} users")
    else:
        hours_left = 23 - int(time_since_last.seconds // 3600)
        minutes_left = 59 - int((time_since_last.seconds % 3600) // 60)
        if minutes_left % 30 == 0:
            print(f"⏳ Next salary in {hours_left}h {minutes_left}m")

@tasks.loop(hours=12)
async def business_profits():
    """Generate business profits every 24 hours (persistent timer)"""
    try:
        with open(LAST_BUSINESS_PROFIT_FILE, "r") as f:
            last_profit_data = json.load(f)
        last_profit_time = datetime.datetime.fromisoformat(last_profit_data.get("last_business_profit", "2000-01-01T00:00:00"))
    except:
        last_profit_time = datetime.datetime.now() - datetime.timedelta(days=1)

    time_since_last = datetime.datetime.now() - last_profit_time

    if time_since_last.total_seconds() >= 86400:
        print("🏢 24 hours passed, generating business profits...")

        profits_generated = 0
        total_profits = 0

        for user_id, business in bot.businesses.items():
            daily_profit = int(business["investment"] * business["profit_rate"])
            business["total_profit"] += daily_profit
            business["last_profit"] = datetime.datetime.now().isoformat()
            profits_generated += 1
            total_profits += daily_profit

        if profits_generated > 0:
            save_economy()
            asyncio.create_task(async_save_economy())
            print(f"✅ Business profits generated! ${format_money(total_profits)} for {profits_generated} businesses")

        with open(LAST_BUSINESS_PROFIT_FILE, "w") as f:
            json.dump({
                "last_business_profit": datetime.datetime.now().isoformat(),
                "businesses_count": profits_generated,
                "total_profits": total_profits,
                "date": datetime.datetime.now().strftime("%Y-%m-%d")
            }, f, indent=2)
    else:
        hours_left = 23 - int(time_since_last.seconds // 3600)
        minutes_left = 59 - int((time_since_last.seconds % 3600) // 60)
        if minutes_left % 60 == 0:
            print(f"⏳ Next business profits in {hours_left}h {minutes_left}m")

@tasks.loop(minutes=1)
async def check_muted_users():
    """Check for muted users to unmute"""
    now = datetime.datetime.now()
    unmuted_count = 0

    for user_id, data in list(bot.muted_users.items()):
        try:
            unmute_at = datetime.datetime.fromisoformat(data["unmute_at"])

            if now >= unmute_at:
                try:
                    guild = bot.get_guild(data["guild_id"])
                    if guild:
                        member = guild.get_member(int(user_id))
                        if member:
                            mute_role = discord.utils.get(guild.roles, name="Muted")
                            if mute_role and mute_role in member.roles:
                                await member.remove_roles(mute_role)
                                unmuted_count += 1
                except:
                    pass

                del bot.muted_users[user_id]
        except:
            del bot.muted_users[user_id]

    if unmuted_count > 0:
        save_data()
        print(f"🔇 Automatically unmuted {unmuted_count} users")
      # ===== ERROR HANDLING =====

@bot.event
async def on_command_error(ctx, error):
    """Handle command errors"""
    if isinstance(error, commands.CommandNotFound):
        embed = create_embed(
            "❌ Command Not Found",
            f"Command not found! Use `!help` to see all commands.",
            discord.Color.red()
        )
        await ctx.send(embed=embed, delete_after=10)

    elif isinstance(error, commands.MissingPermissions):
        embed = create_embed(
            "❌ Permission Denied",
            f"You don't have permission to use this command!",
            discord.Color.red()
        )
        await ctx.send(embed=embed, delete_after=10)

    elif isinstance(error, commands.MissingRequiredArgument):
        embed = create_embed(
            "❌ Missing Argument",
            f"Missing required argument!\n"
            f"Use `!help {ctx.command.name}` for proper usage.",
            discord.Color.red()
        )
        await ctx.send(embed=embed, delete_after=10)

    elif isinstance(error, commands.BadArgument):
        embed = create_embed(
            "❌ Invalid Argument",
            f"Invalid argument provided!\n"
            f"Error: {str(error)}",
            discord.Color.red()
        )
        await ctx.send(embed=embed, delete_after=10)

    else:
        print(f"⚠️ Unexpected error in command {ctx.command}: {type(error).__name__}: {error}")

# ===== MAIN FUNCTION =====

def main():
    """Main function to run the bot on Render"""
    print("=" * 50)
    print("🤖 DISCORD BOT STARTING ON RENDER WITH SUPABASE")
    print("=" * 50)

    print(f"📊 Python Version: {sys.version.split()[0]}")
    print(f"📁 Working Directory: {os.getcwd()}")

    token = os.environ.get('DISCORD_TOKEN')

    if not token:
        token = os.environ.get('DISCORD_BOT_TOKEN')

    if not token:
        print("❌ ERROR: No Discord bot token found!")
        print("\n💡 HOW TO FIX ON RENDER:")
        print("1. Go to render.com → Your project")
        print("2. Click 'Environment' tab")
        print("3. Add new variable:")
        print("   - Key: DISCORD_TOKEN")
        print("   - Value: your_bot_token_from_discord_dev_portal")
        print("4. Click 'Save' then 'Manual Deploy'")
        print("\n🔗 Get token from: https://discord.com/developers/applications")
        return

    print(f"✅ Token found ({len(token)} characters)")
    print("🚀 Starting bot connection...")
    print("=" * 50)

    try:
        bot.run(token)
    except discord.LoginFailure:
        print("❌ LOGIN FAILED: Invalid bot token!")
        print("Please check your token in Render Environment Variables")
    except discord.PrivilegedIntentsRequired:
        print("❌ PRIVILEGED INTENTS REQUIRED!")
        print("Enable these in Discord Developer Portal:")
        print("1. PRESENCE INTENT")
        print("2. SERVER MEMBERS INTENT")
        print("3. MESSAGE CONTENT INTENT")
    except Exception as e:
        print(f"❌ Error starting bot: {type(e).__name__}: {e}")

# Run the bot
if __name__ == "__main__":
    main()
