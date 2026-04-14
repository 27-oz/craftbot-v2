import discord
from discord.ext import commands, tasks
from discord import app_commands
import db
from datetime import datetime, timedelta
import re

def parse_duration(s):
    match = re.fullmatch(r"(\d+)(s|m|h|d|w)", s.lower())
    if not match: return None
    v, u = int(match.group(1)), match.group(2)
    return v * {"s":1,"m":60,"h":3600,"d":86400,"w":604800}[u]

async def send_log(bot, guild, embed):
    channel_id = await db.get_config(guild.id, "log_channel")
    if not channel_id: return
    ch = guild.get_channel(int(channel_id))
    if ch: await ch.send(embed=embed)

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_tempbans.start()

    def cog_unload(self):
        self.check_tempbans.cancel()

    @tasks.loop(minutes=1)
    async def check_tempbans(self):
        now = datetime.utcnow().isoformat()
        bans = await db.fetchall("SELECT * FROM tempbans WHERE expires_at <= ?", (now,))
        for ban in bans:
            guild = self.bot.get_guild(ban["guild_id"])
            if guild:
                try:
                    user = await self.bot.fetch_user(ban["user_id"])
                    await guild.unban(user, reason="Temp-ban expired")
                except: pass
            await db.execute("DELETE FROM tempbans WHERE guild_id=? AND user_id=?", (ban["guild_id"], ban["user_id"]))

    @check_tempbans.before_loop
    async def before_check(self): await self.bot.wait_until_ready()

    @commands.hybrid_command(name="warn", description="Warn a member")
    @app_commands.describe(member="Member to warn", reason="Reason")
    @commands.has_permissions(manage_messages=True)
    async def warn(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        await db.execute("INSERT INTO warnings (guild_id,user_id,reason,mod_id,created_at) VALUES (?,?,?,?,?)",
                   (str(ctx.guild.id), str(member.id), reason, str(ctx.author.id), datetime.utcnow().isoformat()))
        row = await db.fetchone("SELECT COUNT(*) as c FROM warnings WHERE guild_id=? AND user_id=?",
                               (str(ctx.guild.id), str(member.id)))
        count = row["c"]
        embed = discord.Embed(title="Member Warned", color=0xFF9800)
        embed.add_field(name="Member", value=member.mention, inline=True)
        embed.add_field(name="By", value=ctx.author.mention, inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.set_footer(text=f"Total warnings: {count}")
        await ctx.send(embed=embed)
        try: await member.send(f"You were warned in **{ctx.guild.name}**: {reason} (warning #{count})")
        except: pass
        log = discord.Embed(title="Warn", color=0xFF9800, timestamp=datetime.utcnow())
        log.add_field(name="Member", value=str(member))
        log.add_field(name="Reason", value=reason)
        await send_log(self.bot, ctx.guild, log)

    @commands.hybrid_command(name="warnings", description="Check warnings for a member")
    @app_commands.describe(member="Member to check")
    async def warnings(self, ctx, member: discord.Member):
        warns = await db.fetchall("SELECT * FROM warnings WHERE guild_id=? AND user_id=? ORDER BY created_at DESC",
                               (str(ctx.guild.id), str(member.id)))
        if not warns: await ctx.send(f"{member.mention} has no warnings."); return
        embed = discord.Embed(title=f"Warnings for {member.display_name}", color=0xFF9800)
        for i, w in enumerate(warns, 1):
            embed.add_field(name=f"#{i} — {w['created_at'][:10]}", value=w["reason"], inline=False)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="clearwarnings", description="Clear all warnings for a member")
    @app_commands.describe(member="Member to clear")
    @commands.has_permissions(manage_messages=True)
    async def clearwarnings(self, ctx, member: discord.Member):
        await db.execute("DELETE FROM warnings WHERE guild_id=? AND user_id=?", (str(ctx.guild.id), str(member.id)))
        await ctx.send(f"Cleared all warnings for {member.mention}.")

    @commands.hybrid_command(name="kick", description="Kick a member")
    @app_commands.describe(member="Member to kick", reason="Reason")
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        try: await member.send(f"You were kicked from **{ctx.guild.name}**: {reason}")
        except: pass
        await member.kick(reason=reason)
        await ctx.send(f"Kicked {member} — {reason}")
        log = discord.Embed(title="Kick", color=0xF44336, timestamp=datetime.utcnow())
        log.add_field(name="Member", value=str(member))
        log.add_field(name="Reason", value=reason)
        await send_log(self.bot, ctx.guild, log)

    @commands.hybrid_command(name="ban", description="Ban a member")
    @app_commands.describe(member="Member to ban", reason="Reason")
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        try: await member.send(f"You were banned from **{ctx.guild.name}**: {reason}")
        except: pass
        await member.ban(reason=reason)
        await ctx.send(f"Banned {member} — {reason}")
        log = discord.Embed(title="Ban", color=0xB71C1C, timestamp=datetime.utcnow())
        log.add_field(name="Member", value=str(member))
        log.add_field(name="Reason", value=reason)
        await send_log(self.bot, ctx.guild, log)

    @commands.hybrid_command(name="unban", description="Unban a user by ID")
    @app_commands.describe(user_id="The user's ID")
    @commands.has_permissions(ban_members=True)
    async def unban(self, ctx, user_id: str):
        try:
            user = await self.bot.fetch_user(int(user_id))
            await ctx.guild.unban(user)
            await ctx.send(f"Unbanned {user}.")
        except: await ctx.send("User not found or not banned.")

    @commands.hybrid_command(name="tempban", description="Temporarily ban a member")
    @app_commands.describe(member="Member to ban", duration="e.g. 1d, 12h, 1w", reason="Reason")
    @commands.has_permissions(ban_members=True)
    async def tempban(self, ctx, member: discord.Member, duration: str, *, reason: str = "No reason provided"):
        seconds = parse_duration(duration)
        if not seconds: await ctx.send("Invalid duration. Use: 30m, 12h, 1d, 1w"); return
        expires = (datetime.utcnow() + timedelta(seconds=seconds)).isoformat()
        try: await member.send(f"You were temp-banned from **{ctx.guild.name}** for {duration}: {reason}")
        except: pass
        await member.ban(reason=f"[Temp {duration}] {reason}")
        await db.execute("INSERT OR REPLACE INTO tempbans VALUES (?,?,?)", (ctx.guild.id, member.id, expires))
        await ctx.send(f"Temp-banned {member} for {duration}.")

    @commands.hybrid_command(name="mute", description="Mute a member for 10 minutes")
    @app_commands.describe(member="Member to mute", reason="Reason")
    @commands.has_permissions(moderate_members=True)
    async def mute(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        await member.timeout(timedelta(minutes=10), reason=reason)
        await ctx.send(f"Muted {member.mention} for 10 minutes.")

    @commands.hybrid_command(name="unmute", description="Unmute a member")
    @app_commands.describe(member="Member to unmute")
    @commands.has_permissions(moderate_members=True)
    async def unmute(self, ctx, member: discord.Member):
        await member.timeout(None)
        await ctx.send(f"Unmuted {member.mention}.")

    @commands.hybrid_command(name="purge", description="Delete messages")
    @app_commands.describe(amount="Number of messages (max 100)")
    @commands.has_permissions(manage_messages=True)
    async def purge(self, ctx, amount: int):
        if amount > 100: await ctx.send("Max 100."); return
        await ctx.channel.purge(limit=amount + 1)
        await ctx.send(f"Deleted {amount} messages.", delete_after=3)

    @commands.hybrid_command(name="lock", description="Lock a channel")
    @app_commands.describe(channel="Channel to lock (defaults to current)")
    @commands.has_permissions(manage_channels=True)
    async def lock(self, ctx, channel: discord.TextChannel = None):
        channel = channel or ctx.channel
        ow = channel.overwrites_for(ctx.guild.default_role)
        ow.send_messages = False
        await channel.set_permissions(ctx.guild.default_role, overwrite=ow)
        await ctx.send(f"{channel.mention} locked.")

    @commands.hybrid_command(name="unlock", description="Unlock a channel")
    @app_commands.describe(channel="Channel to unlock (defaults to current)")
    @commands.has_permissions(manage_channels=True)
    async def unlock(self, ctx, channel: discord.TextChannel = None):
        channel = channel or ctx.channel
        ow = channel.overwrites_for(ctx.guild.default_role)
        ow.send_messages = None
        await channel.set_permissions(ctx.guild.default_role, overwrite=ow)
        await ctx.send(f"{channel.mention} unlocked.")

    @commands.hybrid_command(name="slowmode", description="Set slowmode")
    @app_commands.describe(seconds="Seconds (0 to disable)")
    @commands.has_permissions(manage_channels=True)
    async def slowmode(self, ctx, seconds: int = 0):
        await ctx.channel.edit(slowmode_delay=seconds)
        await ctx.send(f"Slowmode set to {seconds}s." if seconds else "Slowmode disabled.")

    @commands.hybrid_command(name="setlog", description="Set the logging channel")
    @app_commands.describe(channel="The log channel")
    @commands.has_permissions(manage_guild=True)
    async def setlog(self, ctx, channel: discord.TextChannel):
        await db.set_config(ctx.guild.id, "log_channel", channel.id)
        await ctx.send(f"Log channel set to {channel.mention}.")

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.author.bot: return
        embed = discord.Embed(title="Message Deleted", color=0xF44336, timestamp=datetime.utcnow())
        embed.add_field(name="Author", value=message.author.mention)
        embed.add_field(name="Channel", value=message.channel.mention)
        embed.add_field(name="Content", value=message.content[:1024] or "empty", inline=False)
        await send_log(self.bot, message.guild, embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if before.author.bot or before.content == after.content: return
        embed = discord.Embed(title="Message Edited", color=0xFF9800, timestamp=datetime.utcnow())
        embed.add_field(name="Author", value=before.author.mention)
        embed.add_field(name="Channel", value=before.channel.mention)
        embed.add_field(name="Before", value=before.content[:512], inline=False)
        embed.add_field(name="After", value=after.content[:512], inline=False)
        await send_log(self.bot, before.guild, embed)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        embed = discord.Embed(title="Member Joined", color=0x4CAF50, timestamp=datetime.utcnow())
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Member", value=member.mention)
        embed.add_field(name="Account Created", value=member.created_at.strftime("%b %d, %Y"))
        embed.set_footer(text=f"Member #{member.guild.member_count}")
        await send_log(self.bot, member.guild, embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        embed = discord.Embed(title="Member Left", color=0x9E9E9E, timestamp=datetime.utcnow())
        embed.add_field(name="Member", value=str(member))
        await send_log(self.bot, member.guild, embed)

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        embed = discord.Embed(title="Member Banned", color=0xB71C1C, timestamp=datetime.utcnow())
        embed.add_field(name="User", value=str(user))
        await send_log(self.bot, guild, embed)

async def setup(bot): await bot.add_cog(Moderation(bot))
