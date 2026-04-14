import discord
from discord.ext import commands
from discord import app_commands
import db

STAR_THRESHOLD = 5
STAR_EMOJI = "⭐"

class Starboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if str(payload.emoji) != STAR_EMOJI: return
        guild = self.bot.get_guild(payload.guild_id)
        if not guild: return
        sb_id = await db.get_config(guild.id, "starboard_channel")
        if not sb_id: return
        sb_channel = guild.get_channel(int(sb_id))
        if not sb_channel: return
        channel = guild.get_channel(payload.channel_id)
        if not channel or channel.id == sb_channel.id: return
        try: message = await channel.fetch_message(payload.message_id)
        except: return
        star_reaction = discord.utils.get(message.reactions, emoji=STAR_EMOJI)
        count = star_reaction.count if star_reaction else 0
        if count < STAR_THRESHOLD: return
        gid, mid = str(guild.id), str(payload.message_id)
        existing = await db.fetchone("SELECT sb_message_id FROM starboard WHERE guild_id=? AND message_id=?", (gid, mid))
        if existing:
            try:
                sb_msg = await sb_channel.fetch_message(int(existing["sb_message_id"]))
                await sb_msg.edit(content=f"{STAR_EMOJI} **{count}** | {channel.mention}")
            except: pass
            return
        embed = discord.Embed(description=message.content or "", color=0xFFD700)
        embed.set_author(name=message.author.display_name, icon_url=message.author.display_avatar.url)
        embed.add_field(name="Original", value=f"[Jump]({message.jump_url})")
        embed.set_footer(text=f"#{channel.name}")
        if message.attachments: embed.set_image(url=message.attachments[0].url)
        sb_msg = await sb_channel.send(content=f"{STAR_EMOJI} **{count}** | {channel.mention}", embed=embed)
        await db.execute("INSERT INTO starboard VALUES (?,?,?)", (gid, mid, str(sb_msg.id)))

    @commands.hybrid_command(name="setstarboard", description="Set the starboard channel")
    @app_commands.describe(channel="The starboard channel")
    @commands.has_permissions(manage_guild=True)
    async def setstarboard(self, ctx, channel: discord.TextChannel):
        await db.set_config(ctx.guild.id, "starboard_channel", channel.id)
        await ctx.send(f"Starboard set to {channel.mention}! Messages with {STAR_THRESHOLD}+ stars will be pinned there.")

async def setup(bot): await bot.add_cog(Starboard(bot))
