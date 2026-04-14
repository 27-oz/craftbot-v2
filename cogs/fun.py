import discord
from discord.ext import commands
from discord import app_commands
from db import get_db
import random, aiohttp, re
from collections import defaultdict

EIGHT_BALL = [
    "It is certain.", "Without a doubt.", "Yes, definitely.",
    "Most likely.", "Outlook good.", "Signs point to yes.",
    "Reply hazy, try again.", "Ask again later.", "Cannot predict now.",
    "Don't count on it.", "My reply is no.", "Very doubtful.",
]

JOKES = [
    ("Why did the Creeper go to therapy?", "Because it had too many explosive emotions."),
    ("What do you call a Minecraft player who works at a bakery?", "A bread miner."),
    ("Why don't Endermen use umbrellas?", "They'd teleport away the moment it rained."),
    ("What did Steve say to the diamond?", "I dig you."),
    ("What's a Creeper's favourite subject?", "Hiss-tory."),
    ("Why did the zombie break up with the skeleton?", "He had no guts."),
    ("How do Minecraft players stay cool?", "They stand next to a fan."),
]

# ── Markov chain ──────────────────────────────────────────────────────────────

def build_chain(messages, state_size=2):
    chain = defaultdict(list)
    for msg in messages:
        words = msg.split()
        if len(words) < state_size + 1: continue
        for i in range(len(words) - state_size):
            key = tuple(words[i:i+state_size])
            chain[key].append(words[i+state_size])
    return chain

def generate_text(chain, state_size=2, max_words=40):
    if not chain: return None
    key = random.choice(list(chain.keys()))
    words = list(key)
    for _ in range(max_words):
        next_words = chain.get(tuple(words[-state_size:]))
        if not next_words: break
        words.append(random.choice(next_words))
    return " ".join(words)

class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Store messages for Markov
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild: return
        if message.content.startswith("!") or message.content.startswith("/"): return
        if len(message.content) < 10 or len(message.content) > 300: return
        # Only store plain text, no mentions/links
        clean = re.sub(r"<[^>]+>|https?://\S+", "", message.content).strip()
        if not clean: return
        with get_db() as db:
            count = db.execute("SELECT COUNT(*) as c FROM markov WHERE guild_id=? AND user_id=?",
                               (str(message.guild.id), str(message.author.id))).fetchone()["c"]
            if count > 500:
                db.execute("DELETE FROM markov WHERE rowid IN (SELECT rowid FROM markov WHERE guild_id=? AND user_id=? ORDER BY rowid ASC LIMIT 1)",
                           (str(message.guild.id), str(message.author.id)))
            db.execute("INSERT INTO markov (guild_id,user_id,message) VALUES (?,?,?)",
                       (str(message.guild.id), str(message.author.id), clean))

    @commands.hybrid_command(name="markov", description="Generate a sentence from server messages")
    async def markov(self, ctx):
        with get_db() as db:
            rows = db.execute("SELECT message FROM markov WHERE guild_id=? ORDER BY RANDOM() LIMIT 200",
                              (str(ctx.guild.id),)).fetchall()
        if len(rows) < 20: await ctx.send("Not enough messages yet! Keep chatting."); return
        chain = build_chain([r["message"] for r in rows])
        text = generate_text(chain)
        if not text: await ctx.send("Couldn't generate anything yet."); return
        embed = discord.Embed(description=f'"{text}"', color=0x9C27B0)
        embed.set_footer(text="Generated from server messages")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="mock", description="Generate a sentence in a user's style")
    @app_commands.describe(member="Member to mock")
    async def mock(self, ctx, member: discord.Member):
        with get_db() as db:
            rows = db.execute("SELECT message FROM markov WHERE guild_id=? AND user_id=? ORDER BY RANDOM() LIMIT 200",
                              (str(ctx.guild.id), str(member.id))).fetchall()
        if len(rows) < 10: await ctx.send(f"Not enough messages from {member.display_name} yet!"); return
        chain = build_chain([r["message"] for r in rows])
        text = generate_text(chain)
        if not text: await ctx.send("Couldn't generate anything."); return
        embed = discord.Embed(description=f'"{text}"', color=0xFF4081)
        embed.set_footer(text=f"Generated from {member.display_name}'s messages")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="8ball", description="Ask the magic 8-ball")
    @app_commands.describe(question="Your question")
    async def eight_ball(self, ctx, *, question: str):
        embed = discord.Embed(color=0x1A237E)
        embed.add_field(name="Question", value=question, inline=False)
        embed.add_field(name="Answer", value=random.choice(EIGHT_BALL), inline=False)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="dice", description="Roll a dice")
    @app_commands.describe(sides="Number of sides (default 6)")
    async def dice(self, ctx, sides: int = 6):
        if not 2 <= sides <= 1000: await ctx.send("Sides must be between 2 and 1000."); return
        result = random.randint(1, sides)
        embed = discord.Embed(title=f"D{sides} Roll", description=f"You rolled **{result}**!", color=0xFF5722)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="coinflip", description="Flip a coin")
    async def coinflip(self, ctx):
        result = random.choice(["Heads", "Tails"])
        embed = discord.Embed(title="Coin Flip", description=f"**{result}**!", color=0xFFD700)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="rps", description="Play rock paper scissors vs the bot")
    @app_commands.describe(choice="rock, paper, or scissors")
    async def rps(self, ctx, choice: str):
        choice = choice.lower()
        options = ["rock", "paper", "scissors"]
        if choice not in options: await ctx.send("Choose rock, paper, or scissors."); return
        bot_choice = random.choice(options)
        if choice == bot_choice: result, color = "Tie!", 0x9E9E9E
        elif (choice=="rock" and bot_choice=="scissors") or (choice=="paper" and bot_choice=="rock") or (choice=="scissors" and bot_choice=="paper"):
            result, color = "You win!", 0x4CAF50
        else: result, color = "Bot wins!", 0xF44336
        embed = discord.Embed(title="Rock Paper Scissors", color=color)
        embed.add_field(name="You", value=choice.capitalize(), inline=True)
        embed.add_field(name="Bot", value=bot_choice.capitalize(), inline=True)
        embed.add_field(name="Result", value=result, inline=False)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="joke", description="Get a random Minecraft joke")
    async def joke(self, ctx):
        setup, punchline = random.choice(JOKES)
        embed = discord.Embed(title="Minecraft Joke", color=0x4CAF50)
        embed.add_field(name=setup, value=f"||{punchline}||", inline=False)
        embed.set_footer(text="Click the spoiler to reveal!")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="meme", description="Get a random Minecraft meme")
    async def meme(self, ctx):
        async with ctx.typing():
            try:
                async with aiohttp.ClientSession() as s:
                    async with s.get("https://meme-api.com/gimme/Minecraft", timeout=aiohttp.ClientTimeout(total=5)) as r:
                        if r.status == 200:
                            data = await r.json()
                            embed = discord.Embed(title=data.get("title","Minecraft Meme"), color=0x4CAF50)
                            embed.set_image(url=data.get("url"))
                            embed.set_footer(text=f"{data.get('ups',0)} upvotes on r/Minecraft")
                            await ctx.send(embed=embed); return
            except: pass
        await ctx.send("Couldn't fetch a meme right now.")

async def setup(bot): await bot.add_cog(Fun(bot))
