import asyncpg
import os
import json
import datetime
import socket  # added for IPv4 forcing

class Database:
    def __init__(self):
        self.pool = None
        self.connected = False

    async def connect(self):
        """Connect to Supabase using IPv4 only (bypass IPv6 issues)."""
        database_url = os.getenv('SUPABASE_URL')
        if not database_url:
            print("⚠️  SUPABASE_URL not set – database features disabled.")
            return False

        try:
            # --- Force IPv4 by overriding DNS resolution ---
            original_getaddrinfo = socket.getaddrinfo

            def getaddrinfo_ipv4_only(host, port, family=0, type=0, proto=0, flags=0):
                # Override to use IPv4 (AF_INET) only
                return original_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)

            # Apply the override
            socket.getaddrinfo = getaddrinfo_ipv4_only

            # Create connection pool
            self.pool = await asyncpg.create_pool(
                database_url,
                min_size=1,
                max_size=5,
                command_timeout=60
            )

            # Restore original function (important!)
            socket.getaddrinfo = original_getaddrinfo

            self.connected = True
            print("✅ Connected to Supabase PostgreSQL (IPv4 forced).")
            await self.create_tables()
            return True

        except Exception as e:
            # Restore original even on error
            if 'original_getaddrinfo' in locals():
                socket.getaddrinfo = original_getaddrinfo
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
        """Upsert economy data."""
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
                # Also map channel -> user for quick lookup
                if guild not in channels:
                    channels[guild] = {}
                channels[guild][str(row['channel_id'])] = user
        return quarantined, channels

    async def save_quarantine(self, quarantined_dict):
        """Save quarantine data."""
        if not self.connected:
            return
        async with self.pool.acquire() as conn:
            # Clear and reinsert (simple approach)
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

    async def close(self):
        if self.pool:
            await self.pool.close()