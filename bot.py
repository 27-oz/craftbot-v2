import discord
from discord.ext import commands, tasks
from discord import app_commands
import os, itertools, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from dotenv import load_dotenv
from db import init_db, USE_POSTGRES

load_dotenv()

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

COGS = [
    "cogs.moderation",
    "cogs.leveling",
    "cogs.economy",
    "cogs.minecraft",
    "cogs.fun",
    "cogs.feeds",
    "cogs.ai",
    "cogs.starboard",
]

STATUSES = [
    (discord.ActivityType.playing,   "Minecraft | /help"),
    (discord.ActivityType.watching,  "over the server"),
    (discord.ActivityType.listening, "/ask"),
    (discord.ActivityType.playing,   "with {members} members"),
    (discord.ActivityType.watching,  "for rule breakers"),
]

# ── health check server (keeps Render awake) ─────────────────────────────────
class Health(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"OK")
    def log_message(self, *a): pass

threading.Thread(
    target=lambda: HTTPServer(("0.0.0.0", 8080), Health).serve_forever(),
    daemon=True
).start()

# ── startup ───────────────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    await init_db()
    print(f"CraftBot online as {bot.user}")
    for cog in COGS:
        try:
            await bot.load_extension(cog)
            print(f"  + {cog}")
        except Exception as e:
            print(f"  ! {cog}: {e}")
    try:
        synced = await bot.tree.sync()
        print(f"  Synced {len(synced)} slash commands")
    except Exception as e:
        print(f"  Sync failed: {e}")
    status_cycle.start()

# ── cycling status ────────────────────────────────────────────────────────────
_cycle = itertools.cycle(STATUSES)

@tasks.loop(seconds=30)
async def status_cycle():
    atype, text = next(_cycle)
    text = text.replace("{members}", str(sum(g.member_count for g in bot.guilds)))
    await bot.change_presence(activity=discord.Activity(type=atype, name=text))

# ── error handler ─────────────────────────────────────────────────────────────
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound): return
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("You don't have permission to do that.", ephemeral=True)
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"Missing argument: `{error.param.name}`.")
    else:
        await ctx.send(f"Error: {error}")

# ── /help ─────────────────────────────────────────────────────────────────────
@bot.hybrid_command(name="help", description="Show all commands")
@app_commands.describe(category="Category to view")
async def help_cmd(ctx, category: str = None):
    categories = {
        "mod": ("Moderation", [
            "/warn @user [reason]", "/warnings @user", "/clearwarnings @user",
            "/kick @user [reason]", "/ban @user [reason]", "/unban <id>",
            "/tempban @user <duration> [reason]", "/mute @user [reason]",
            "/unmute @user", "/purge <amount>", "/lock [#channel]", "/unlock [#channel]",
            "/slowmode <seconds>", "/setlog #channel"
        ]),
        "levels": ("Leveling", [
            "/rank [@user]", "/leaderboard", "/perks",
            "/setxp @user <amount>", "/addxp @user <amount>",
            "/xpboost <mult> <duration>", "/xpboostend", "/xpblacklist #channel"
        ]),
        "economy": ("Economy", [
            "/balance [@user]", "/daily", "/transfer @user <amount>",
            "/richest", "/shop", "/buy <id>",
            "/additem <id> <price> <name>", "/removeitem <id>",
            "/givecoins @user <amount>", "/takecoins @user <amount>"
        ]),
        "minecraft": ("Minecraft", [
            "/skin <username>", "/uuid <username>", "/wiki <term>",
            "/mcstatus <address>", "/tip", "/events",
            "/addevent <date> <time> <name>", "/removeevent <name>"
        ]),
        "fun": ("Fun", [
            "/8ball <question>", "/dice [sides]", "/coinflip",
            "/rps <choice>", "/joke", "/meme",
            "/markov", "/mock @user"
        ]),
        "feeds": ("Social Feeds", [
            "/addtiktok <user> #channel [@role]", "/removetiktok <user>", "/tiktoks",
            "/addtwitch <user> #channel [@role]", "/removetwitch <user>"
        ]),
        "ai": ("AI", [
            "/ask <question> [model]", "/setai <model>", "/aimodels"
        ]),
        "starboard": ("Starboard", [
            "/setstarboard #channel"
        ]),
    }
    if category and category.lower() in categories:
        title, cmds = categories[category.lower()]
        embed = discord.Embed(title=f"{title} Commands", color=0x4CAF50)
        embed.description = "\n".join(f"`{c}`" for c in cmds)
        embed.set_footer(text="CraftBot v2.0")
        await ctx.send(embed=embed)
        return
    embed = discord.Embed(title="CraftBot v2.0 — Commands", description="Use `/help <category>` for details.", color=0x4CAF50)
    for key, (title, cmds) in categories.items():
        embed.add_field(name=f"`/help {key}` — {title}", value=f"{len(cmds)} commands", inline=False)
    embed.set_footer(text="CraftBot v2.0 — Minecraft community bot")
    await ctx.send(embed=embed)

bot.run(os.getenv("DISCORD_TOKEN"))
