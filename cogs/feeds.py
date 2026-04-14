import discord
from discord.ext import commands
from discord import app_commands
from discord.ext import tasks
from db import get_db
import aiohttp, os, feedparser

RSSHUB = os.getenv("RSSHUB_URL", "https://rsshub.app")
TWITCH_CLIENT_ID     = os.getenv("TWITCH_CLIENT_ID")
TWITCH_CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")

class Feeds(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.twitch_token = None
        self.check_tiktok.start()
        self.check_twitch.start()

    def cog_unload(self):
        self.check_tiktok.cancel()
        self.check_twitch.cancel()

    # ── TikTok ────────────────────────────────────────────────────────────────
    @tasks.loop(minutes=10)
    async def check_tiktok(self):
        with get_db() as db:
            feeds = db.execute("SELECT * FROM tiktok_feeds").fetchall()
        for feed in feeds:
            guild = self.bot.get_guild(feed["guild_id"])
            if not guild: continue
            channel = guild.get_channel(feed["channel_id"])
            if not channel: continue
            try:
                parsed = feedparser.parse(f"{RSSHUB}/tiktok/user/@{feed['username']}")
                if not parsed.entries: continue
                latest = parsed.entries[0]
                latest_id = latest.get("id", latest.get("link",""))
                if latest_id == feed["last_id"]: continue
                with get_db() as db:
                    db.execute("UPDATE tiktok_feeds SET last_id=? WHERE guild_id=? AND username=?",
                               (latest_id, feed["guild_id"], feed["username"]))
                embed = discord.Embed(
                    title=f"{feed['username']} posted on TikTok!",
                    description=latest.get("summary","")[:300],
                    url=latest.get("link",""),
                    color=0x010101
                )
                embed.set_footer(text=latest.get("published",""))
                content = f"<@&{feed['role_id']}>" if feed["role_id"] else ""
                await channel.send(content=content, embed=embed)
            except Exception as e:
                print(f"TikTok error ({feed['username']}): {e}")

    @check_tiktok.before_loop
    async def before_tiktok(self): await self.bot.wait_until_ready()

    @commands.hybrid_command(name="addtiktok", description="Track a TikTok account")
    @app_commands.describe(username="TikTok username (without @)", channel="Alert channel", role="Role to ping (optional)")
    @commands.has_permissions(manage_guild=True)
    async def addtiktok(self, ctx, username: str, channel: discord.TextChannel, role: discord.Role = None):
        username = username.lstrip("@")
        with get_db() as db:
            db.execute("INSERT OR REPLACE INTO tiktok_feeds VALUES (?,?,?,?,?)",
                       (str(ctx.guild.id), username, channel.id, role.id if role else None, None))
        await ctx.send(f"Now tracking TikTok `@{username}` in {channel.mention}.")

    @commands.hybrid_command(name="removetiktok", description="Stop tracking a TikTok account")
    @app_commands.describe(username="TikTok username")
    @commands.has_permissions(manage_guild=True)
    async def removetiktok(self, ctx, username: str):
        with get_db() as db:
            db.execute("DELETE FROM tiktok_feeds WHERE guild_id=? AND username=?", (str(ctx.guild.id), username.lstrip("@")))
        await ctx.send(f"Stopped tracking `@{username}`.")

    @commands.hybrid_command(name="tiktoks", description="List tracked TikTok accounts")
    async def tiktoks(self, ctx):
        with get_db() as db:
            rows = db.execute("SELECT * FROM tiktok_feeds WHERE guild_id=?", (str(ctx.guild.id),)).fetchall()
        if not rows: await ctx.send("No TikTok accounts tracked."); return
        embed = discord.Embed(title="Tracked TikTok Accounts", color=0x010101)
        for row in rows:
            ch = ctx.guild.get_channel(row["channel_id"])
            embed.add_field(name=f"@{row['username']}", value=ch.mention if ch else "unknown channel", inline=True)
        await ctx.send(embed=embed)

    # ── Twitch ────────────────────────────────────────────────────────────────
    async def get_twitch_token(self):
        if not TWITCH_CLIENT_ID or not TWITCH_CLIENT_SECRET: return None
        async with aiohttp.ClientSession() as s:
            async with s.post("https://id.twitch.tv/oauth2/token", params={
                "client_id": TWITCH_CLIENT_ID,
                "client_secret": TWITCH_CLIENT_SECRET,
                "grant_type": "client_credentials"
            }) as r:
                data = await r.json()
                return data.get("access_token")

    async def is_live(self, username):
        if not self.twitch_token: self.twitch_token = await self.get_twitch_token()
        if not self.twitch_token: return None
        async with aiohttp.ClientSession() as s:
            async with s.get(f"https://api.twitch.tv/helix/streams?user_login={username}",
                             headers={"Client-ID": TWITCH_CLIENT_ID, "Authorization": f"Bearer {self.twitch_token}"}) as r:
                data = await r.json()
                streams = data.get("data", [])
                return streams[0] if streams else None

    @tasks.loop(minutes=5)
    async def check_twitch(self):
        if not TWITCH_CLIENT_ID: return
        with get_db() as db:
            feeds = db.execute("SELECT * FROM twitch_feeds").fetchall()
        for feed in feeds:
            guild = self.bot.get_guild(feed["guild_id"])
            if not guild: continue
            channel = guild.get_channel(feed["channel_id"])
            if not channel: continue
            try:
                stream = await self.is_live(feed["username"])
                was_live = bool(feed["is_live"])
                if stream and not was_live:
                    with get_db() as db:
                        db.execute("UPDATE twitch_feeds SET is_live=1 WHERE guild_id=? AND username=?",
                                   (feed["guild_id"], feed["username"]))
                    embed = discord.Embed(
                        title=f"{feed['username']} is LIVE on Twitch!",
                        description=stream.get("title",""),
                        url=f"https://twitch.tv/{feed['username']}",
                        color=0x9146FF
                    )
                    embed.add_field(name="Game", value=stream.get("game_name","Unknown"), inline=True)
                    embed.add_field(name="Viewers", value=str(stream.get("viewer_count",0)), inline=True)
                    if stream.get("thumbnail_url"):
                        embed.set_image(url=stream["thumbnail_url"].replace("{width}","320").replace("{height}","180"))
                    content = f"<@&{feed['role_id']}>" if feed["role_id"] else ""
                    await channel.send(content=content, embed=embed)
                elif not stream and was_live:
                    with get_db() as db:
                        db.execute("UPDATE twitch_feeds SET is_live=0 WHERE guild_id=? AND username=?",
                                   (feed["guild_id"], feed["username"]))
            except Exception as e:
                print(f"Twitch error ({feed['username']}): {e}")

    @check_twitch.before_loop
    async def before_twitch(self): await self.bot.wait_until_ready()

    @commands.hybrid_command(name="addtwitch", description="Track a Twitch streamer")
    @app_commands.describe(username="Twitch username", channel="Alert channel", role="Role to ping (optional)")
    @commands.has_permissions(manage_guild=True)
    async def addtwitch(self, ctx, username: str, channel: discord.TextChannel, role: discord.Role = None):
        if not TWITCH_CLIENT_ID:
            await ctx.send("Twitch not configured. Add `TWITCH_CLIENT_ID` and `TWITCH_CLIENT_SECRET` to environment."); return
        with get_db() as db:
            db.execute("INSERT OR REPLACE INTO twitch_feeds VALUES (?,?,?,?,?)",
                       (str(ctx.guild.id), username.lower(), channel.id, role.id if role else None, 0))
        await ctx.send(f"Now tracking Twitch `{username}` in {channel.mention}.")

    @commands.hybrid_command(name="removetwitch", description="Stop tracking a Twitch streamer")
    @app_commands.describe(username="Twitch username")
    @commands.has_permissions(manage_guild=True)
    async def removetwitch(self, ctx, username: str):
        with get_db() as db:
            db.execute("DELETE FROM twitch_feeds WHERE guild_id=? AND username=?", (str(ctx.guild.id), username.lower()))
        await ctx.send(f"Stopped tracking `{username}`.")

async def setup(bot): await bot.add_cog(Feeds(bot))
