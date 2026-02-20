import asyncpg
import os
import json
import datetime

class Database:
    def __init__(self):
        self.pool = None

    async def connect(self):
        """Connect to Supabase using the connection URL from environment."""
        database_url = os.getenv('SUPABASE_URL')
        if not database_url:
            print("❌ SUPABASE_URL not set – database disabled.")
            return False
        try:
            self.pool = await asyncpg.create_pool(database_url, min_size=1, max_size=5)
            print("✅ Connected to Supabase PostgreSQL.")
            return True
        except Exception as e:
            print(f"⚠️ Database connection failed: {e}")
            return False

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
        async with self.pool.acquire() as conn:
            for uid, wallet in wallets.items():
                bank = banks.get(uid, 0)
                ld = last_daily.get(uid)
                lw = 
