import discord
from discord.ext import commands
from discord import app_commands
import db
from datetime import datetime
import aiohttp, random, urllib.parse

TIPS = [
    "Torches prevent mob spawning — place them every 12 blocks in your mines.",
    "Phantoms spawn if you haven't slept in 3+ nights.",
    "Netherite is found below Y=15. Use beds to mine it (carefully!).",
    "Name a sheep 'jeb_' to make it cycle through all wool colours.",
    "Holding a map in your off-hand lets you navigate while walking.",
    "Sprint-jumping uses less hunger than regular sprinting.",
    "F3 shows your coordinates — note your base coords!",
    "Dolphins lead you to underwater ruins if you feed them fish.",
    "Elytra + Fireworks = infinite flight. Stock up on rockets!",
    "Blue ice makes boat highways much faster.",
    "Scaffolding lets you build up quickly — break the bottom to clear it all.",
    "Fishing during rain increases your catch rate!",
    "Aqua Affinity on your helmet lets you mine at normal speed underwater.",
    "Ancient cities are in deep dark biomes. Watch for wardens!",
    "A water bucket lets you survive any fall — place it just before you land.",
]

class Minecraft(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="skin", description="View a Minecraft player's skin")
    @app_commands.describe(username="Minecraft username")
    async def skin(self, ctx, username: str):
        async with aiohttp.ClientSession() as s:
            async with s.get(f"https://api.mojang.com/users/profiles/minecraft/{username}") as r:
                if r.status == 404: await ctx.send(f"Player `{username}` not found."); return
                if r.status != 200: await ctx.send("Couldn't reach Mojang API."); return
                profile = await r.json()
        uuid, name = profile["id"], profile["name"]
        embed = discord.Embed(title=f"{name}'s Skin", color=0x4CAF50)
        embed.set_image(url=f"https://visage.surgeplay.com/full/256/{uuid}")
        embed.set_thumbnail(url=f"https://visage.surgeplay.com/face/64/{uuid}")
        embed.add_field(name="UUID", value=uuid)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="uuid", description="Look up a Minecraft player's UUID")
    @app_commands.describe(username="Minecraft username")
    async def uuid(self, ctx, username: str):
        async with aiohttp.ClientSession() as s:
            async with s.get(f"https://api.mojang.com/users/profiles/minecraft/{username}") as r:
                if r.status == 404: await ctx.send(f"Player `{username}` not found."); return
                profile = await r.json()
        uuid = profile["id"]
        fmt = f"{uuid[:8]}-{uuid[8:12]}-{uuid[12:16]}-{uuid[16:20]}-{uuid[20:]}"
        embed = discord.Embed(title=f"UUID: {profile['name']}", color=0x2196F3)
        embed.set_thumbnail(url=f"https://visage.surgeplay.com/face/64/{uuid}")
        embed.add_field(name="Raw", value=uuid, inline=False)
        embed.add_field(name="Formatted", value=fmt, inline=False)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="wiki", description="Search the Minecraft Wiki")
    @app_commands.describe(term="What to look up")
    async def wiki(self, ctx, *, term: str):
        url = f"https://minecraft.wiki/w/{urllib.parse.quote(term.replace(' ','_'))}"
        api = f"https://minecraft.wiki/api.php?action=query&titles={urllib.parse.quote(term)}&prop=extracts&exintro=true&explaintext=true&format=json"
        async with aiohttp.ClientSession() as s:
            async with s.get(api, timeout=aiohttp.ClientTimeout(total=8)) as r:
                if r.status != 200: await ctx.send(f"Couldn't reach the wiki. Try: {url}"); return
                data = await r.json()
        page = next(iter(data["query"]["pages"].values()))
        if "missing" in page: await ctx.send(f"No article found for `{term}`. Try: {url}"); return
        extract = page.get("extract", "")
        summary = "\n\n".join(p for p in extract.split("\n") if p.strip())[:500]
        embed = discord.Embed(title=page.get("title", term), description=summary + "...", url=url, color=0x4CAF50)
        embed.set_footer(text="Minecraft Wiki — click title for full article")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="mcstatus", description="Check if a Minecraft server is online")
    @app_commands.describe(address="Server address e.g. play.example.net")
    async def mcstatus(self, ctx, address: str):
        host, port = address, 25565
        if ":" in address:
            host, port = address.rsplit(":", 1); port = int(port)
        async with aiohttp.ClientSession() as s:
            async with s.get(f"https://api.mcsrvstat.us/3/{host}:{port}", timeout=aiohttp.ClientTimeout(total=8)) as r:
                data = await r.json()
        if not data.get("online"):
            await ctx.send(embed=discord.Embed(title=f"{host} is OFFLINE", color=0xF44336)); return
        players = data.get("players", {})
        embed = discord.Embed(title=f"{host} is ONLINE", color=0x4CAF50)
        embed.add_field(name="Players", value=f"{players.get('online',0)}/{players.get('max',0)}", inline=True)
        embed.add_field(name="Version", value=data.get("version","?"), inline=True)
        motd = data.get("motd",{}).get("clean",[""])[0]
        if motd: embed.add_field(name="MOTD", value=motd, inline=False)
        player_list = players.get("list", [])
        if player_list:
            names = ", ".join(p.get("name",p) if isinstance(p,dict) else p for p in player_list[:10])
            embed.add_field(name="Online Now", value=names, inline=False)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="tip", description="Get a random Minecraft tip")
    async def tip(self, ctx):
        embed = discord.Embed(title="Minecraft Tip", description=random.choice(TIPS), color=0xFFEB3B)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="events", description="Show upcoming server events")
    async def events(self, ctx):
        now = datetime.utcnow().isoformat()
        rows = await db.fetchall("SELECT * FROM events WHERE guild_id=? AND event_time>? ORDER BY event_time LIMIT 10",
                          (str(ctx.guild.id), now))
        if not rows: await ctx.send("No upcoming events! Admins can add them with `/addevent`."); return
        embed = discord.Embed(title="Upcoming Events", color=0x9C27B0)
        for row in rows:
            dt = datetime.fromisoformat(row["event_time"])
            diff = (dt - datetime.utcnow()).total_seconds()
            days, hours = int(diff//86400), int((diff%86400)//3600)
            countdown = f"in {days}d {hours}h" if days else f"in {hours}h"
            embed.add_field(
                name=f"{row['name']} — {countdown}",
                value=f"{row['description'] or ''}\n{dt.strftime('%b %d, %Y at %H:%M UTC')}",
                inline=False
            )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="addevent", description="Add a server event")
    @app_commands.describe(date="YYYY-MM-DD", time="HH:MM (UTC)", name="Event name", description="Description")
    @commands.has_permissions(manage_guild=True)
    async def addevent(self, ctx, date: str, time: str, name: str, description: str = ""):
        try: dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
        except ValueError: await ctx.send("Invalid date/time. Use YYYY-MM-DD HH:MM"); return
        await db.execute("INSERT INTO events (guild_id,name,description,event_time) VALUES (?,?,?,?)",
                   (str(ctx.guild.id), name, description, dt.isoformat()))
        await ctx.send(f"Event **{name}** added for {dt.strftime('%b %d, %Y at %H:%M UTC')}!")

    @commands.hybrid_command(name="removeevent", description="Remove an event by name")
    @app_commands.describe(name="Event name to remove")
    @commands.has_permissions(manage_guild=True)
    async def removeevent(self, ctx, *, name: str):
        await db.execute("DELETE FROM events WHERE guild_id=? AND name=?", (str(ctx.guild.id), name))
        await ctx.send(f"Removed event `{name}`.")

async def setup(bot): await bot.add_cog(Minecraft(bot))
