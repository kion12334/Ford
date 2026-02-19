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
from database import Database
print("🚀 Starting Discord Bot on Railway...")
print("=" * 50)

# Bot setup with all necessary intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix='!', intents=intents)

print("✅ Bot initialized")

# File paths for data storage
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

# Helper functions for formatting
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

# Data loading functions
def load_data():
    """Load bot data"""
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except:
        return {"afk_users": {}, "warnings": {}, "muted_users": {}}

def load_economy():
    """Load economy data"""
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
    """Load shop items"""
    try:
        with open(SHOP_FILE, "r") as f:
            return json.load(f)
    except: 
        return {"roles": [], "vehicles": [], "properties": [], "aircraft": {}, "yachts": []}

def load_role_salaries():
    """Load role salaries"""
    try:
        with open(ROLE_SALARIES_FILE, "r") as f:
            return json.load(f)
    except:
        return {"default": 1000, "Admin": 5000, "Moderator": 3000}

def load_countries():
    """Load countries data"""
    try:
        with open(COUNTRIES_FILE, "r") as f:
            return json.load(f)
    except:
        return {"Europe": [], "Africa": []}

def load_country_scores():
    """Load country game scores"""
    try:
        with open(COUNTRY_SCORES_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def load_quarantine():
    """Load quarantine data"""
    try:
        with open(QUARANTINE_FILE, "r") as f:
            return json.load(f)
    except:
        return {"quarantined_users": {}, "quarantine_channels": {}}

def load_businesses():
    """Load business data"""
    try:
        with open(BUSINESS_FILE, "r") as f:
            return json.load(f)
    except:
        return {"businesses": {}, "business_types": {}}

def load_last_salary():
    """Load last salary time"""
    try:
        with open(LAST_SALARY_FILE, "r") as f:
            return json.load(f)
    except:
        return {"last_salary": "2000-01-01T00:00:00"}

def load_last_business_profit():
    """Load last business profit time"""
    try:
        with open(LAST_BUSINESS_PROFIT_FILE, "r") as f:
            return json.load(f)
    except:
        return {"last_business_profit": "2000-01-01T00:00:00"}

# Data saving functions
def save_data():
    """Save bot data"""
    with open(DATA_FILE, "w") as f:
        json.dump({
            "afk_users": bot.afk_users,
            "warnings": bot.warnings,
            "muted_users": bot.muted_users
        }, f, indent=2)

def save_economy():
    """Save economy data"""
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
    """Save country scores"""
    with open(COUNTRY_SCORES_FILE, "w") as f:
        json.dump(bot.country_scores, f, indent=2)

def save_quarantine():
    """Save quarantine data"""
    with open(QUARANTINE_FILE, "w") as f:
        json.dump({
            "quarantined_users": bot.quarantined_users,
            "quarantine_channels": bot.quarantine_channels
        }, f, indent=2)

def save_businesses():
    """Save business data"""
    with open(BUSINESS_FILE, "w") as f:
        json.dump({
            "businesses": bot.businesses,
            "business_types": bot.business_types
        }, f, indent=2)

def save_last_salary(last_salary_time):
    """Save last salary time"""
    with open(LAST_SALARY_FILE, "w") as f:
        json.dump({
            "last_salary": last_salary_time,
            "saved_at": datetime.datetime.now().isoformat()
        }, f, indent=2)

def save_last_business_profit(last_profit_time):
    """Save last business profit time"""
    with open(LAST_BUSINESS_PROFIT_FILE, "w") as f:
        json.dump({
            "last_business_profit": last_profit_time,
            "saved_at": datetime.datetime.now().isoformat()
        }, f, indent=2)

print("📊 Loading data...")

# Load initial data
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

# WARNING about Railway data persistence
if 'RAILWAY_ENVIRONMENT' in os.environ:
    print("⚠️  WARNING: Running on Railway - JSON data may reset on restart!")
    print("💡 Tip: Data is saved to files, but consider adding database for production")

# Initialize bot variables
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
# ===== BOT EVENTS =====

@bot.event
async def on_ready():
    """When bot connects successfully"""
    print(f'✅ Logged in as {bot.user.name}')
    print(f'🆔 Bot ID: {bot.user.id}')
    print(f'🔗 Connected to {len(bot.guilds)} servers')
    print(f'🏢 Host: Railway')
    
    # Set bot status
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="!help for commands"
        )
    )
    
    # Start background tasks
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
        # Find welcome channel
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

# ===== COUNTRY GAME FUNCTIONS =====

async def handle_country_guess(message, game, user_id):
    """Handle country game guesses"""
    country = game["current_country"]
    guess = message.content.strip().lower()
    game_type = game.get("game_type", "flag")
    
    correct = False
    
    if game_type == "flag":
        # Guess country or capital from flag
        if guess in [country["country"].lower(), country["capital"].lower()]:
            correct = True
    else:  # capital game
        # Only accept capital as answer
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
        
        # Update scores
        bot.country_scores[user_id] = bot.country_scores.get(user_id, 0) + points
        save_country_scores()
        
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
        
        # Cancel timer
        if "timer" in game and not game["timer"].done():
            game["timer"].cancel()
        
        # Next round after delay
        await asyncio.sleep(3)
        await next_country_round(message.guild)

async def next_country_round(guild):
    """Start next round of country game"""
    guild_id = str(guild.id)
    if guild_id not in bot.active_games:
        return
    
    game = bot.active_games[guild_id]
    continent = game["continent"]
    
    # Pick random country
    countries = bot.countries.get(continent, [])
    if not countries:
        return
    
    country = random.choice(countries)
    game["current_country"] = country
    game["winners"] = []
    
    channel = guild.get_channel(game["channel_id"])
    if not channel:
        return
    
    # Send round based on game type
    if game["game_type"] == "flag":
        embed = create_embed(
            f"🇺🇳 Round Started!",
            f"**Guess the country or capital!**\n"
            f"**Flag:** {country['flag']}",
            discord.Color.blue()
        )
    else:  # capital game
        embed = create_embed(
            f"🏛️ Capital Guessing!",
            f"**What is the capital of:** {country['country']}?",
            discord.Color.blue()
        )
    
    await channel.send(embed=embed)
    
    # Set timer for auto-next round (60 seconds)
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
        except:
            pass
    
    # Check if user is quarantined
    if guild_id in bot.quarantined_users and user_id in bot.quarantined_users[guild_id]:
        # Check if message is in quarantine channel
        quarantine_info = bot.quarantined_users[guild_id][user_id]
        quarantine_channel_id = quarantine_info.get("channel_id")
        
        if str(message.channel.id) != str(quarantine_channel_id):
            # Delete message and warn
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
    
    # Process commands
    await bot.process_commands(message)

# ===== BASIC COMMANDS =====

@bot.command(name="ping")
async def ping(ctx):
    """Check bot latency"""
    latency = round(bot.latency * 1000)
    embed = create_embed(
        "🏓 Pong!",
        f"**Latency:** {latency}ms\n**Status:** Online ✅\n**Host:** Railway",
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
    
    # Get or create mute role
    mute_role = discord.utils.get(ctx.guild.roles, name="Muted")
    if not mute_role:
        try:
            mute_role = await ctx.guild.create_role(
                name="Muted", 
                color=discord.Color.dark_gray(),
                reason="Mute role for bot"
            )
            # Set permissions
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
    
    # Add mute role
    await member.add_roles(mute_role, reason=f"Muted by {ctx.author}: {reason}")
    
    # Store mute info
    unmute_time = datetime.datetime.now() + datetime.timedelta(minutes=minutes)
    bot.muted_users[str(member.id)] = {
        "unmute_at": unmute_time.isoformat(),
        "reason": reason,
        "guild_id": ctx.guild.id
    }
    save_data()
    
    # Create embed
    embed = create_embed(
        "🔇 User Muted",
        f"**User:** {member.mention}\n"
        f"**Duration:** {minutes} minutes\n"
        f"**Reason:** {reason}\n"
        f"**Until:** {unmute_time.strftime('%H:%M:%S')}",
        discord.Color.orange()
    )
    await ctx.send(embed=embed)
    
    # Auto unmute task
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
    
    # Remove from muted list
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
    bot.warnings[user_id] = bot.warnings.get(user_id, 0) + 1
    save_data()
    
    embed = create_embed(
        "⚠️ User Warned",
        f"**User:** {member.mention}\n"
        f"**Reason:** {reason}\n"
        f"**Total Warnings:** {bot.warnings[user_id]}\n"
        f"**By:** {ctx.author.mention}",
        discord.Color.orange()
    )
    await ctx.send(embed=embed)

@bot.command(name="warnings")
async def warnings(ctx, member: discord.Member = None):
    """Check warnings for a user"""
    target = member or ctx.author
    user_id = str(target.id)
    count = bot.warnings.get(user_id, 0)
    
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
    
    # Check if already claimed today
    last_claim = bot.last_daily.get(user_id)
    if last_claim:
        last_time = datetime.datetime.fromisoformat(last_claim)
        time_since = datetime.datetime.now() - last_time
        
        if time_since.total_seconds() < 86400:  # 24 hours
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
    
    amount = 10000  # $10,000 daily
    
    # Give money
    bot.wallets[user_id] = bot.wallets.get(user_id, 0) + amount
    bot.last_daily[user_id] = datetime.datetime.now().isoformat()
    save_economy()
    
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
    
    # Check cooldown (1 hour)
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
    
    # Random work amount
    amount = random.randint(5000, 20000)
    
    # Give money
    bot.wallets[user_id] = bot.wallets.get(user_id, 0) + amount
    bot.last_work[user_id] = datetime.datetime.now().isoformat()
    save_economy()
    
    # Random work messages
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
    
    # Deposit
    bot.wallets[user_id] = wallet - amount_num
    bot.banks[user_id] = bot.banks.get(user_id, 0) + amount_num
    save_economy()
    
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
    
    # Withdraw
    bot.banks[user_id] = bank - amount_num
    bot.wallets[user_id] = bot.wallets.get(user_id, 0) + amount_num
    save_economy()
    
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
    
    # Transfer (2% tax)
    tax = int(amount * 0.02)
    transfer_amount = amount - tax
    
    bot.wallets[sender_id] = sender_wallet - amount
    bot.wallets[receiver_id] = bot.wallets.get(receiver_id, 0) + transfer_amount
    save_economy()
    
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
    
    # 45% chance to win
    if random.random() < 0.45:
        win_amount = int(amount * 1.5)  # Win 1.5x
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
    # Validate choice
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
    
    # 50/50 coin flip
    coin_result = random.choice(["heads", "tails"])
    coin_emoji = "🪙" if coin_result == "heads" else "🪙"
    result_emoji = "💎" if coin_result == "heads" else "🪙"
    
    # Check if user won
    win = user_choice == coin_result
    
    # Animated coin flip message
    embed = create_embed(
        f"{choice_emoji} Coin Flip!",
        f"**Your bet:** {format_money(amount)} on **{user_choice}**\n"
        f"**Flipping coin...**",
        discord.Color.blue()
    )
    
    message = await ctx.send(embed=embed)
    
    # Animation delay
    await asyncio.sleep(1.5)
    
    if win:
        # Win: double your money (2x)
        win_amount = amount * 2
        bot.wallets[user_id] = wallet + win_amount
        result_text = f"**{result_emoji} It's {coin_result}! You won {format_money(win_amount)}!**"
        color = discord.Color.green()
        profit = win_amount - amount
        title = f"🎉 {result_emoji} You Win!"
    else:
        # Lose: lose your bet
        bot.wallets[user_id] = wallet - amount
        result_text = f"**{result_emoji} It's {coin_result}! You lost {format_money(amount)}.**"
        color = discord.Color.red()
        profit = -amount
        title = f"💸 {result_emoji} You Lose"
    
    save_economy()
    
    # Update embed with result
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
    
    # Check if user already has a business
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
    
    # Create business
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
    
    # Deduct investment
    bot.wallets[user_id] = wallet - investment
    save_economy()
    
    # Calculate daily profit
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
    
    # Calculate time since last profit
    last_profit_text = "Never"
    if business["last_profit"]:
        last_time = datetime.datetime.fromisoformat(business["last_profit"])
        time_since = datetime.datetime.now() - last_time
        hours_since = int(time_since.total_seconds() // 3600)
        last_profit_text = f"{hours_since} hours ago"
    
    # Calculate next profit
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
    
    # Check if 24 hours have passed since last profit
    if business["last_profit"]:
        last_time = datetime.datetime.fromisoformat(business["last_profit"])
        time_since = datetime.datetime.now() - last_time
        
        if time_since.total_seconds() < 86400:  # 24 hours
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
    
    # Calculate profit
    daily_profit = int(business["investment"] * business["profit_rate"])
    business["total_profit"] += daily_profit
    business["last_profit"] = datetime.datetime.now().isoformat()
    
    # Give money to user
    bot.wallets[user_id] = bot.wallets.get(user_id, 0) + daily_profit
    save_economy()
    
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
    
    # Calculate upgrade cost
    upgrade_cost = business["investment"] * 0.5  # 50% of current investment
    wallet = bot.wallets.get(user_id, 0)
    
    if wallet < upgrade_cost:
        embed = create_embed(
            "❌ Insufficient Funds",
            f"Upgrade costs {format_money(int(upgrade_cost))} but you only have {format_money(wallet)}!",
            discord.Color.red()
        )
        await ctx.send(embed=embed)
        return
    
    # Upgrade business
    business["level"] += 1
    business["investment"] += int(upgrade_cost)
    business["profit_rate"] += 0.02  # Increase profit rate by 2%
    
    # Deduct money
    bot.wallets[user_id] = wallet - int(upgrade_cost)
    save_economy()
    
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
    refund = business["investment"] // 2  # 50% refund
    
    # Give refund
    bot.wallets[user_id] = bot.wallets.get(user_id, 0) + refund
    
    # Remove business
    del bot.businesses[user_id]
    save_economy()
    
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
        # Show all categories
        categories_text = ""
        for cat in bot.shop_items:
            if bot.shop_items[cat]:  # Only show categories with items
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
    
    # Find the item
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
    
    # Handle special categories
    if category == "roles":
        role_name = item["name"]
        role = discord.utils.get(ctx.guild.roles, name=role_name)
        
        if not role:
            # Create the role if it doesn't exist
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
        
        # Check if user already has the role
        if role in ctx.author.roles:
            embed = create_embed(
                "❌ Already Owned",
                f"You already have the **{role_name}** role!",
                discord.Color.orange()
            )
            await ctx.send(embed=embed)
            return
        
        # Give the role
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
    
    # Deduct money
    bot.wallets[user_id] = wallet - item["price"]
    
    # Add to owned items
    if user_id not in bot.owned_items:
        bot.owned_items[user_id] = {}
    
    if category not in bot.owned_items[user_id]:
        bot.owned_items[user_id][category] = []
    
    bot.owned_items[user_id][category].append(item["name"])
    
    # Save economy data
    save_economy()
    
    # Send confirmation
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
        
        # Try to mention the user
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
    
    # Show current user's position
    current_user_id = str(ctx.author.id)
    current_wallet = bot.wallets.get(current_user_id, 0)
    current_bank = bot.banks.get(current_user_id, 0)
    current_total = current_wallet + current_bank
    
    # Find rank
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
async def startcountrygame(ctx, game_type: str, continent: str):
    """Start a country guessing game (flag or capital)"""
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
    
    # Initialize game
    bot.active_games[guild_id] = {
        "active": True,
        "game_type": game_type,
        "continent": continent,
        "winners": [],
        "paused": False,
        "channel_id": ctx.channel.id
    }
    
    # Start first round
    await next_country_round(ctx.guild)
    
    embed = create_embed(
        "🏁 Country Game Started!",
        f"**Type:** {'Flag Guessing' if game_type == 'flag' else 'Capital Guessing'}\n"
        f"**Continent:** {continent}\n"
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
    
    # Cancel timer if exists
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
    
    # Sort scores
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

@bot.command(name="quarantine", aliases=["q"])
@commands.has_permissions(manage_messages=True)
async def quarantine(ctx, member: discord.Member, *, reason="No reason provided"):
    """Quarantine a user to a separate channel"""
    if member.guild_permissions.administrator:
        embed = create_embed("❌ Error", "Cannot quarantine an administrator.", discord.Color.red())
        await ctx.send(embed=embed)
        return

    guild_id = str(ctx.guild.id)
    user_id = str(member.id)

    # Check if already quarantined
    if guild_id in bot.quarantined_users and user_id in bot.quarantined_users[guild_id]:
        embed = create_embed("❌ Error", f"{member.mention} is already quarantined!", discord.Color.red())
        await ctx.send(embed=embed)
        return

    # Get or create quarantine category
    quarantine_category = discord.utils.get(ctx.guild.categories, name="Quarantine")
    if not quarantine_category:
        try:
            quarantine_category = await ctx.guild.create_category(
                name="Quarantine",
                reason="Quarantine system"
            )
            # Set permissions – only staff can view
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

    # Create quarantine channel for this user
    channel_name = f"quarantine-{member.name.lower()}"
    try:
        # Delete old channel if exists
        existing_channel = discord.utils.get(quarantine_category.channels, name=channel_name)
        if existing_channel:
            await existing_channel.delete()

        # Base overwrites
        overwrites = {
            ctx.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_messages=True),
            ctx.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_messages=True)
        }

        # Add staff permissions
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

    # Store quarantine info
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

    # Send quarantine message
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

    # Send message to quarantine channel
    quarantine_embed = create_embed(
        "🦠 You have been quarantined",
        f"You have been placed in quarantine by {ctx.author.mention}\n"
        f"**Reason:** {reason}\n\n"
        f"You can only communicate in this channel until a staff member releases you.\n"
        f"Please follow the server rules and await further instructions.",
        discord.Color.orange()
    )
    await quarantine_channel.send(f"{member.mention}", embed=quarantine_embed)

@bot.command(name="unquarantine", aliases=["uq"])
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

    # Delete quarantine channel
    if channel_id:
        try:
            channel = ctx.guild.get_channel(int(channel_id))
            if channel:
                await channel.delete(reason=f"Unquarantine {member.name}")

                # Remove from quarantine_channels
                if str(channel_id) in bot.quarantine_channels.get(guild_id, {}):
                    del bot.quarantine_channels[guild_id][str(channel_id)]
        except:
            pass

    # Remove user from quarantined list
    del bot.quarantined_users[guild_id][user_id]

    # Clean up if empty
    if not bot.quarantined_users[guild_id]:
        del bot.quarantined_users[guild_id]

    save_quarantine()

    embed = create_embed(
        "✅ User Released",
        f"{member.mention} has been released from quarantine by {ctx.author.mention}\n"
        f"They can now participate in regular channels.",
        discord.Color.green()
    )
    await ctx.send(embed=embed)

    # Try to DM the user
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
        
        # Create category if it doesn't exist
        if category not in bot.shop_items:
            bot.shop_items[category] = []
        
        # Check if item already exists
        for item in bot.shop_items[category]:
            if item["name"].lower() == name.lower():
                await ctx.send(f"❌ Item '{name}' already exists in {category} category!")
                return
        
        # Create new item
        new_item = {
            "name": name,
            "price": price,
            "description": description,
            "emoji": "🛍️"
        }
        
        # Add to shop
        bot.shop_items[category].append(new_item)
        
        # Save to file
        with open(SHOP_FILE, "w") as f:
            json.dump(bot.shop_items, f, indent=2)
        
        # Send success message
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
        
        # Find the item
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
        
        # Save to file
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
        
        # Check if role exists in the server
        role = discord.utils.get(ctx.guild.roles, name=role_name)
        if not role:
            # Try case-insensitive search
            for r in ctx.guild.roles:
                if r.name.lower() == role_name.lower():
                    role = r
                    break
        
        if not role:
            await ctx.send(f"❌ Role **{role_name}** not found in this server!")
            return
        
        # Set the salary using EXACT role name from Discord
        exact_role_name = role.name
        bot.role_salaries[exact_role_name] = amount
        
        # Save to file
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
        
        # Create embed
        embed = discord.Embed(
            title="💰 Role Salaries",
            description="Daily salaries paid to bank accounts",
            color=discord.Color.gold()
        )
        
        # Show default salary
        default_salary = bot.role_salaries.get("default", 1000)
        embed.add_field(
            name="👤 Default (no special role)",
            value=format_money(default_salary),
            inline=False
        )
        
        # Get non-default salaries
        other_salaries = []
        for role, salary in bot.role_salaries.items():
            if role != "default":
                other_salaries.append((role, salary))
        
        if other_salaries:
            # Sort by salary (highest first)
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
# ===== MANUAL SALARY PAYMENT COMMAND =====

@bot.command(name="paysalary", aliases=["paysalaries", "salarypay", "forcepay"])
@commands.has_permissions(administrator=True)
async def paysalary(ctx):
    """Manually pay daily salaries to all users (Admin only)"""
    await ctx.send("💰 Processing manual salary payment...")
    
    salaries_given = 0
    total_amount = 0
    salary_details = {}
    
    # Process all guilds and members
    for guild in bot.guilds:
        for member in guild.members:
            if not member.bot:
                user_id = str(member.id)
                salary = bot.role_salaries.get("default", 1000)
                highest_role_name = "Default"
                
                # Check member's roles for higher salaries
                for role in member.roles:
                    if role.name in bot.role_salaries:
                        role_salary = bot.role_salaries[role.name]
                        if role_salary > salary:
                            salary = role_salary
                            highest_role_name = role.name
                
                # Give salary to bank
                bot.banks[user_id] = bot.banks.get(user_id, 0) + salary
                salaries_given += 1
                total_amount += salary
                
                # Track details for summary
                if highest_role_name not in salary_details:
                    salary_details[highest_role_name] = {"count": 0, "total": 0}
                salary_details[highest_role_name]["count"] += 1
                salary_details[highest_role_name]["total"] += salary
    
    save_economy()
    
    # Update last salary time
    with open(LAST_SALARY_FILE, "w") as f:
        json.dump({
            "last_salary": datetime.datetime.now().isoformat(),
            "salaries_given": salaries_given,
            "total_amount": total_amount,
            "date": datetime.datetime.now().strftime("%Y-%m-%d"),
            "paid_by": str(ctx.author.id),
            "manual_payment": True
        }, f, indent=2)
    
    # Create detailed embed
    embed = create_embed(
        "💰 Manual Salary Payment Complete",
        f"**Total Paid:** {format_money(total_amount)}\n"
        f"**Users Paid:** {salaries_given}\n"
        f"**Time:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        discord.Color.green()
    )
    
    # Add breakdown by role
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

@tasks.loop(minutes=60)  # Check every hour
async def daily_salaries():
    """Give daily salaries, checking if 24 hours have passed"""
    # Load last salary time
    try:
        with open(LAST_SALARY_FILE, "r") as f:
            last_salary_data = json.load(f)
        last_salary_time = datetime.datetime.fromisoformat(last_salary_data.get("last_salary", "2000-01-01T00:00:00"))
    except:
        last_salary_time = datetime.datetime.now() - datetime.timedelta(days=1)  # Default to yesterday
    
    # Check if 24 hours have passed
    time_since_last = datetime.datetime.now() - last_salary_time
    
    if time_since_last.total_seconds() >= 86400:  # 24 hours
        print("💰 24 hours passed, processing daily salaries...")
        
        salaries_given = 0
        total_amount = 0
        
        for guild in bot.guilds:
            for member in guild.members:
                if not member.bot:
                    user_id = str(member.id)
                    salary = bot.role_salaries.get("default", 1000)
                    
                    # Check member's roles for higher salaries
                    for role in member.roles:
                        if role.name in bot.role_salaries:
                            role_salary = bot.role_salaries[role.name]
                            if role_salary > salary:
                                salary = role_salary
                    
                    # Give salary to bank
                    bot.banks[user_id] = bot.banks.get(user_id, 0) + salary
                    salaries_given += 1
                    total_amount += salary
        
        save_economy()
        
        # Save when we last gave salaries
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
        if minutes_left % 30 == 0:  # Log every 30 minutes to avoid spam
            print(f"⏳ Next salary in {hours_left}h {minutes_left}m")

@tasks.loop(hours=12)  # Check every 12 hours
async def business_profits():
    """Generate business profits every 24 hours (persistent timer)"""
    # Load last business profit time
    try:
        with open(LAST_BUSINESS_PROFIT_FILE, "r") as f:
            last_profit_data = json.load(f)
        last_profit_time = datetime.datetime.fromisoformat(last_profit_data.get("last_business_profit", "2000-01-01T00:00:00"))
    except:
        last_profit_time = datetime.datetime.now() - datetime.timedelta(days=1)
    
    # Check if 24 hours have passed
    time_since_last = datetime.datetime.now() - last_profit_time
    
    if time_since_last.total_seconds() >= 86400:  # 24 hours
        print("🏢 24 hours passed, generating business profits...")
        
        profits_generated = 0
        total_profits = 0
        
        for user_id, business in bot.businesses.items():
            # Calculate profit
            daily_profit = int(business["investment"] * business["profit_rate"])
            business["total_profit"] += daily_profit
            business["last_profit"] = datetime.datetime.now().isoformat()
            profits_generated += 1
            total_profits += daily_profit
        
        if profits_generated > 0:
            save_economy()
            print(f"✅ Business profits generated! ${format_money(total_profits)} for {profits_generated} businesses")
        
        # Save when we last generated profits
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
        if minutes_left % 60 == 0:  # Log every hour
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
                
                # Remove from muted list
                del bot.muted_users[user_id]
        except:
            # Remove invalid entries
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
        # Log unexpected errors
        print(f"⚠️ Unexpected error in command {ctx.command}: {type(error).__name__}: {error}")

# ===== MAIN FUNCTION =====

def main():
    """Main function to run the bot on Railway"""
    print("=" * 50)
    print("🤖 DISCORD BOT STARTING ON RAILWAY")
    print("=" * 50)
    
    # Debug info
    print(f"📊 Python Version: {sys.version.split()[0]}")
    print(f"📁 Working Directory: {os.getcwd()}")
    
    # Get bot token from Railway environment variables
    token = os.environ.get('DISCORD_TOKEN')
    
    # Try alternative names
    if not token:
        token = os.environ.get('DISCORD_BOT_TOKEN')
    
    if not token:
        print("❌ ERROR: No Discord bot token found!")
        print("\n💡 HOW TO FIX ON RAILWAY:")
        print("1. Go to railway.app → Your project")
        print("2. Click 'Variables' tab")
        print("3. Add new variable:")
        print("   - Key: DISCORD_TOKEN")
        print("   - Value: your_bot_token_from_discord_dev_portal")
        print("4. Click 'Add' then 'Redeploy'")
        print("\n🔗 Get token from: https://discord.com/developers/applications")
        return
    
    print(f"✅ Token found ({len(token)} characters)")
    print("🚀 Starting bot connection...")
    print("=" * 50)
    
    try:
        bot.run(token)
    except discord.LoginFailure:
        print("❌ LOGIN FAILED: Invalid bot token!")
        print("Please check your token in Railway Variables")
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
