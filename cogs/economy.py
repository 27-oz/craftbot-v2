import discord
from discord.ext import commands
from discord import app_commands
import db
from datetime import datetime, timedelta
import random

DAILY_REWARD = 100
CHAT_COINS = (1, 5)
CHAT_COOLDOWN = 60

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.chat_cooldowns = {}

    async def _ensure(self, guild_id, user_id):
        await db.execute("INSERT OR IGNORE INTO economy (guild_id,user_id) VALUES (?,?)", (str(guild_id), str(user_id)))

    async def _get(self, guild_id, user_id):
        await self._ensure(guild_id, user_id)
        return await db.fetchone("SELECT * FROM economy WHERE guild_id=? AND user_id=?", (str(guild_id), str(user_id)))

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild: return
        uid = message.author.id
        now = datetime.utcnow()
        if uid in self.chat_cooldowns and (now - self.chat_cooldowns[uid]).total_seconds() < CHAT_COOLDOWN: return
        self.chat_cooldowns[uid] = now
        await self._ensure(message.guild.id, uid)
        await db.execute("UPDATE economy SET coins=coins+? WHERE guild_id=? AND user_id=?",
                   (random.randint(*CHAT_COINS), str(message.guild.id), str(uid)))

    @commands.hybrid_command(name="balance", aliases=["bal","coins"], description="Check your coin balance")
    @app_commands.describe(member="Member to check (defaults to you)")
    async def balance(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        row = await self._get(ctx.guild.id, member.id)
        embed = discord.Embed(title=f"{member.display_name}'s Balance", description=f"**{row['coins']:,}** coins", color=0xFFD700)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="daily", description="Claim your daily coin reward")
    async def daily(self, ctx):
        row = await self._get(ctx.guild.id, ctx.author.id)
        if row["last_daily"]:
            next_claim = datetime.fromisoformat(row["last_daily"]) + timedelta(days=1)
            if datetime.utcnow() < next_claim:
                remaining = next_claim - datetime.utcnow()
                h, r = divmod(int(remaining.total_seconds()), 3600)
                await ctx.send(f"Come back in **{h}h {r//60}m** for your daily!"); return
        await db.execute("UPDATE economy SET coins=coins+?,last_daily=? WHERE guild_id=? AND user_id=?",
                   (DAILY_REWARD, datetime.utcnow().isoformat(), str(ctx.guild.id), str(ctx.author.id)))
        await ctx.send(f"{ctx.author.mention} claimed **{DAILY_REWARD} coins**!")

    @commands.hybrid_command(name="transfer", description="Transfer coins to another member")
    @app_commands.describe(member="Recipient", amount="Amount to send")
    async def transfer(self, ctx, member: discord.Member, amount: int):
        if amount <= 0: await ctx.send("Amount must be positive."); return
        if member == ctx.author: await ctx.send("You can't transfer to yourself."); return
        row = await self._get(ctx.guild.id, ctx.author.id)
        if row["coins"] < amount: await ctx.send(f"Not enough coins. You have **{row['coins']:,}**."); return
        await self._ensure(ctx.guild.id, member.id)
        await db.execute("UPDATE economy SET coins=coins-? WHERE guild_id=? AND user_id=?", (amount, str(ctx.guild.id), str(ctx.author.id)))
        await db.execute("UPDATE economy SET coins=coins+? WHERE guild_id=? AND user_id=?", (amount, str(ctx.guild.id), str(member.id)))
        await ctx.send(f"Transferred **{amount:,} coins** to {member.mention}!")

    @commands.hybrid_command(name="richest", description="Show the richest members")
    async def richest(self, ctx):
        rows = await db.fetchall("SELECT user_id,coins FROM economy WHERE guild_id=? ORDER BY coins DESC LIMIT 10", (str(ctx.guild.id),))
        if not rows: await ctx.send("No economy data yet."); return
        embed = discord.Embed(title="Richest Members", color=0xFFD700)
        lines = []
        for i, row in enumerate(rows, 1):
            m = ctx.guild.get_member(int(row["user_id"]))
            lines.append(f"{i}. **{m.display_name if m else 'Unknown'}** — {row['coins']:,} coins")
        embed.description = "\n".join(lines)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="shop", description="Browse the shop")
    async def shop(self, ctx):
        items = await db.fetchall("SELECT * FROM shop WHERE guild_id=?", (str(ctx.guild.id),))
        if not items: await ctx.send("The shop is empty! Admins can add items with `/additem`."); return
        embed = discord.Embed(title="Shop", color=0x4CAF50)
        for item in items:
            stock = f"{item['stock_remaining']} left" if item["stock"] and item["stock"] > 0 else "Unlimited"
            cd = f" | {item['cooldown_hours']}h cooldown" if item["cooldown_hours"] > 0 else ""
            embed.add_field(
                name=f"`{item['item_id']}` — {item['name']} — {item['price']:,} coins",
                value=f"{item['description']}\n{stock}{cd}",
                inline=False
            )
        embed.set_footer(text="Use /buy <id> to purchase")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="buy", description="Buy an item from the shop")
    @app_commands.describe(item_id="The item ID from /shop")
    async def buy(self, ctx, item_id: str):
        gid, uid = str(ctx.guild.id), str(ctx.author.id)
        item = await db.fetchone("SELECT * FROM shop WHERE guild_id=? AND item_id=?", (gid, item_id.lower()))
        if not item: await ctx.send(f"Item `{item_id}` not found. Use `/shop` to see available items."); return
        if item["stock"] and item["stock"] > 0 and item["stock_remaining"] <= 0:
            await ctx.send("That item is out of stock!"); return
        if item["cooldown_hours"] > 0:
            last = await db.fetchone("SELECT purchased_at FROM shop_purchases WHERE guild_id=? AND item_id=? AND user_id=? ORDER BY purchased_at DESC LIMIT 1",
                              (gid, item_id.lower(), uid))
            if last:
                next_buy = datetime.fromisoformat(last["purchased_at"]) + timedelta(hours=item["cooldown_hours"])
                if datetime.utcnow() < next_buy:
                    h = int((next_buy - datetime.utcnow()).total_seconds() // 3600)
                    await ctx.send(f"You can buy this again in **{h}h**."); return
        row = await self._get(ctx.guild.id, ctx.author.id)
        if row["coins"] < item["price"]:
            await ctx.send(f"Not enough coins! You need **{item['price']:,}**."); return
        await db.execute("UPDATE economy SET coins=coins-? WHERE guild_id=? AND user_id=?", (item["price"], gid, uid))
        await db.execute("INSERT INTO shop_purchases VALUES (?,?,?,?)", (gid, item_id.lower(), uid, datetime.utcnow().isoformat()))
        if item["stock"] and item["stock"] > 0:
            await db.execute("UPDATE shop SET stock_remaining=stock_remaining-1 WHERE guild_id=? AND item_id=?", (gid, item_id.lower()))
        if item["role_id"]:
            role = ctx.guild.get_role(item["role_id"])
            if role:
                try: await ctx.author.add_roles(role)
                except: pass
        await ctx.send(f"You bought **{item['name']}** for **{item['price']:,} coins**!")

    @commands.hybrid_command(name="additem", description="Add an item to the shop")
    @app_commands.describe(item_id="Short ID", price="Coin price", name="Display name",
                           description="Description", role="Role to give",
                           stock="Max purchases (0=unlimited)", cooldown_hours="Hours before re-purchase")
    @commands.has_permissions(manage_guild=True)
    async def additem(self, ctx, item_id: str, price: int, name: str,
                      description: str = "A shop item.",
                      role: discord.Role = None,
                      stock: int = 0,
                      cooldown_hours: int = 0):
        await db.execute("INSERT OR REPLACE INTO shop VALUES (?,?,?,?,?,?,?,?,?)",
                   (str(ctx.guild.id), item_id.lower(), name, price, description,
                    role.id if role else None, stock, stock if stock > 0 else None, cooldown_hours))
        await ctx.send(f"Added **{name}** (`{item_id.lower()}`) to the shop for **{price:,} coins**.")

    @commands.hybrid_command(name="removeitem", description="Remove a shop item")
    @app_commands.describe(item_id="The item ID to remove")
    @commands.has_permissions(manage_guild=True)
    async def removeitem(self, ctx, item_id: str):
        await db.execute("DELETE FROM shop WHERE guild_id=? AND item_id=?", (str(ctx.guild.id), item_id.lower()))
        await ctx.send(f"Removed `{item_id}` from the shop.")

    @commands.hybrid_command(name="givecoins", description="Give coins to a member")
    @app_commands.describe(member="The member", amount="Amount")
    @commands.has_permissions(manage_guild=True)
    async def givecoins(self, ctx, member: discord.Member, amount: int):
        await self._ensure(ctx.guild.id, member.id)
        await db.execute("UPDATE economy SET coins=coins+? WHERE guild_id=? AND user_id=?", (amount, str(ctx.guild.id), str(member.id)))
        await ctx.send(f"Gave **{amount:,} coins** to {member.mention}.")

    @commands.hybrid_command(name="takecoins", description="Take coins from a member")
    @app_commands.describe(member="The member", amount="Amount")
    @commands.has_permissions(manage_guild=True)
    async def takecoins(self, ctx, member: discord.Member, amount: int):
        await self._ensure(ctx.guild.id, member.id)
        await db.execute("UPDATE economy SET coins=MAX(0,coins-?) WHERE guild_id=? AND user_id=?", (amount, str(ctx.guild.id), str(member.id)))
        await ctx.send(f"Took **{amount:,} coins** from {member.mention}.")

async def setup(bot): await bot.add_cog(Economy(bot))
