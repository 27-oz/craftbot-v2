import discord
from discord.ext import commands
from discord import app_commands
import db
from datetime import datetime, timedelta
import random, re

LEVEL_THRESHOLDS = [10, 25, 50, 75, 100]
PERKS = {
    10: ("Settler",  "Access to suggestions"),
    25: ("Villager", "Access to staff application"),
    50: ("Knight",   "Access to admin application"),
    75: ("Elder",    "Special Elder role"),
    100:("Legend",   "The highest honour"),
}

def xp_needed(level): return 100 * (level ** 2)
def calc_level(xp):
    l = 0
    while xp >= xp_needed(l + 1): l += 1
    return l

async def get_multiplier(guild_id):
    row = await db.fetchone("SELECT value FROM xp_config WHERE guild_id=? AND key='boost'", (str(guild_id),))
    if not row: return 1.0
    mult, expires = row["value"].split(":")
    if float(expires) < datetime.utcnow().timestamp(): return 1.0
    return float(mult)

async def is_blacklisted(guild_id, channel_id):
    row = await db.fetchone("SELECT value FROM xp_config WHERE guild_id=? AND key='blacklist'", (str(guild_id),))
    if not row: return False
    return str(channel_id) in row["value"].split(",")

class Leveling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cooldowns = {}

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild: return
        if await is_blacklisted(message.guild.id, message.channel.id): return
        uid = message.author.id
        now = datetime.utcnow()
        if uid in self.cooldowns and now - self.cooldowns[uid] < timedelta(seconds=60): return
        self.cooldowns[uid] = now
        xp_gain = int(random.randint(10, 25) * await get_multiplier(message.guild.id))
        gid, user_id = str(message.guild.id), str(uid)
        await db.execute("INSERT OR IGNORE INTO levels (guild_id,user_id) VALUES (?,?)", (gid, user_id))
        await db.execute("UPDATE levels SET xp=xp+? WHERE guild_id=? AND user_id=?", (xp_gain, gid, user_id))
        row = await db.fetchone("SELECT xp,level FROM levels WHERE guild_id=? AND user_id=?", (gid, user_id))
        old_level, new_xp = row["level"], row["xp"]
        new_level = calc_level(new_xp)
        if new_level != old_level:
            await db.execute("UPDATE levels SET level=? WHERE guild_id=? AND user_id=?", (new_level, gid, user_id))
            await self.on_level_up(message, new_level)

    async def on_level_up(self, message, level):
        ch_id = await db.get_config(message.guild.id, "level_channel")
        ch = message.guild.get_channel(int(ch_id)) if ch_id else message.channel
        embed = discord.Embed(title="Level Up!", description=f"{message.author.mention} reached **Level {level}**!", color=0xFFD700)
        if level in PERKS:
            name, perk = PERKS[level]
            embed.add_field(name=f"Perk Unlocked: {name}", value=perk)
            role_id = await db.get_config(message.guild.id, f"level_role_{level}")
            if role_id:
                role = message.guild.get_role(int(role_id))
                if role:
                    try: await message.author.add_roles(role)
                    except: pass
        await ch.send(embed=embed)

    @commands.hybrid_command(name="rank", description="Check your level and XP")
    @app_commands.describe(member="Member to check (defaults to you)")
    async def rank(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        gid, uid = str(ctx.guild.id), str(member.id)
        row = await db.fetchone("SELECT xp,level FROM levels WHERE guild_id=? AND user_id=?", (gid, uid))
        xp, level = (row["xp"], row["level"]) if row else (0, 0)
        next_xp = xp_needed(level + 1)
        progress = int((xp / next_xp) * 20)
        bar = "█" * progress + "░" * (20 - progress)
        embed = discord.Embed(title=f"{member.display_name}'s Rank", color=member.top_role.color)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Level", value=str(level), inline=True)
        embed.add_field(name="XP", value=f"{xp}/{next_xp}", inline=True)
        embed.add_field(name="Progress", value=f"`{bar}`", inline=False)
        next_perk = next((l for l in LEVEL_THRESHOLDS if l > level), None)
        if next_perk:
            name, perk = PERKS[next_perk]
            embed.add_field(name=f"Next perk at Level {next_perk}: {name}", value=perk, inline=False)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="leaderboard", description="Show the XP leaderboard")
    async def leaderboard(self, ctx):
        rows = await db.fetchall("SELECT user_id,xp,level FROM levels WHERE guild_id=? ORDER BY xp DESC LIMIT 10", (str(ctx.guild.id),))
        if not rows: await ctx.send("No XP data yet."); return
        embed = discord.Embed(title="XP Leaderboard", color=0xFFD700)
        lines = []
        for i, row in enumerate(rows, 1):
            m = ctx.guild.get_member(int(row["user_id"]))
            lines.append(f"{i}. **{m.display_name if m else 'Unknown'}** — Level {row['level']} ({row['xp']} XP)")
        embed.description = "\n".join(lines)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="perks", description="Show all level perks")
    async def perks(self, ctx):
        embed = discord.Embed(title="Level Perks", color=0x4CAF50)
        for level, (name, perk) in PERKS.items():
            embed.add_field(name=f"Level {level} — {name}", value=perk, inline=False)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="setxp", description="Set a member's XP")
    @app_commands.describe(member="The member", amount="XP amount")
    @commands.has_permissions(manage_guild=True)
    async def setxp(self, ctx, member: discord.Member, amount: int):
        gid, uid = str(ctx.guild.id), str(member.id)
        level = calc_level(max(0, amount))
        await db.execute("INSERT OR REPLACE INTO levels (guild_id,user_id,xp,level) VALUES (?,?,?,?)", (gid, uid, max(0,amount), level))
        await ctx.send(f"Set {member.mention}'s XP to {amount} (Level {level}).")

    @commands.hybrid_command(name="addxp", description="Add or subtract XP from a member")
    @app_commands.describe(member="The member", amount="Amount (negative to subtract)")
    @commands.has_permissions(manage_guild=True)
    async def addxp(self, ctx, member: discord.Member, amount: int):
        gid, uid = str(ctx.guild.id), str(member.id)
        await db.execute("INSERT OR IGNORE INTO levels (guild_id,user_id) VALUES (?,?)", (gid, uid))
        await db.execute("UPDATE levels SET xp=MAX(0,xp+?) WHERE guild_id=? AND user_id=?", (amount, gid, uid))
        row = await db.fetchone("SELECT xp FROM levels WHERE guild_id=? AND user_id=?", (gid, uid))
        new_level = calc_level(row["xp"])
        await db.execute("UPDATE levels SET level=? WHERE guild_id=? AND user_id=?", (new_level, gid, uid))
        action = "Added" if amount >= 0 else "Removed"
        await ctx.send(f"{action} {abs(amount)} XP {'to' if amount >= 0 else 'from'} {member.mention}. Now Level {new_level}.")

    @commands.hybrid_command(name="xpboost", description="Start an XP multiplier event")
    @app_commands.describe(multiplier="e.g. 2 for double XP", duration="e.g. 1h, 30m")
    @commands.has_permissions(manage_guild=True)
    async def xpboost(self, ctx, multiplier: float, duration: str):
        match = re.fullmatch(r"(\d+)(m|h|d)", duration.lower())
        if not match: await ctx.send("Invalid duration. Use 30m, 2h, 1d."); return
        v, u = int(match.group(1)), match.group(2)
        seconds = v * {"m":60,"h":3600,"d":86400}[u]
        expires = (datetime.utcnow() + timedelta(seconds=seconds)).timestamp()
        await db.execute("INSERT OR REPLACE INTO xp_config VALUES (?,?,?)", (str(ctx.guild.id), "boost", f"{multiplier}:{expires}"))
        embed = discord.Embed(title="XP Boost Active!", description=f"**{multiplier}x XP** for **{duration}**!", color=0xFFD700)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="xpboostend", description="End the XP boost early")
    @commands.has_permissions(manage_guild=True)
    async def xpboostend(self, ctx):
        await db.execute("DELETE FROM xp_config WHERE guild_id=? AND key='boost'", (str(ctx.guild.id),))
        await ctx.send("XP boost ended.")

    @commands.hybrid_command(name="xpblacklist", description="Blacklist a channel from earning XP")
    @app_commands.describe(channel="Channel to blacklist")
    @commands.has_permissions(manage_guild=True)
    async def xpblacklist(self, ctx, channel: discord.TextChannel):
        row = await db.fetchone("SELECT value FROM xp_config WHERE guild_id=? AND key='blacklist'", (str(ctx.guild.id),))
        current = row["value"].split(",") if row else []
        if str(channel.id) not in current:
            current.append(str(channel.id))
        await db.execute("INSERT OR REPLACE INTO xp_config VALUES (?,?,?)", (str(ctx.guild.id), "blacklist", ",".join(current)))
        await ctx.send(f"{channel.mention} blacklisted from XP.")

    @commands.hybrid_command(name="setlevelchannel", description="Set the level-up announcement channel")
    @app_commands.describe(channel="The channel")
    @commands.has_permissions(manage_guild=True)
    async def setlevelchannel(self, ctx, channel: discord.TextChannel):
        await db.set_config(ctx.guild.id, "level_channel", channel.id)
        await ctx.send(f"Level-up announcements will go to {channel.mention}.")

async def setup(bot): await bot.add_cog(Leveling(bot))
