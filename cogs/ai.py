import discord
from discord.ext import commands
from discord import app_commands
import db
import aiohttp, os

GROQ_KEY   = os.getenv("GROQ_API_KEY")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

SYSTEM = (
    "You are CraftBot, a helpful assistant for a Minecraft Discord community. "
    "Be friendly and concise. Keep responses under 1800 characters. "
    "You can answer Minecraft questions, general questions, and server stuff."
)

MODELS = {
    "llama3": ("Llama 3 — Groq", "Fast open-source model by Meta", "GROQ_API_KEY"),
    "gemini": ("Gemini Flash — Google", "Google's free fast AI", "GEMINI_API_KEY"),
}

MODEL_CHOICES = [
    app_commands.Choice(name="Llama 3 — Groq (fast, free)", value="llama3"),
    app_commands.Choice(name="Gemini Flash — Google (free)", value="gemini"),
]

async def ask_groq(prompt):
    if not GROQ_KEY: return "Groq API key not set. Add `GROQ_API_KEY` to your environment variables."
    async with aiohttp.ClientSession() as s:
        async with s.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"},
            json={"model":"llama3-8b-8192","messages":[{"role":"system","content":SYSTEM},{"role":"user","content":prompt}],"max_tokens":500}
        ) as r:
            if r.status != 200: return f"Groq error ({r.status}). Try again later."
            data = await r.json()
            return data["choices"][0]["message"]["content"].strip()

async def ask_gemini(prompt):
    if not GEMINI_KEY: return "Gemini API key not set. Add `GEMINI_API_KEY` to your environment variables."
    async with aiohttp.ClientSession() as s:
        async with s.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}",
            headers={"Content-Type": "application/json"},
            json={"contents":[{"parts":[{"text":f"{SYSTEM}\n\nUser: {prompt}"}]}],"generationConfig":{"maxOutputTokens":500}}
        ) as r:
            if r.status != 200: return f"Gemini error ({r.status}). Try again later."
            data = await r.json()
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()

async def ask(model, prompt):
    if model == "llama3": return await ask_groq(prompt)
    if model == "gemini": return await ask_gemini(prompt)
    return "Unknown model."

class AI(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="ask", description="Ask the AI a question")
    @app_commands.describe(question="Your question", model="Which AI model to use")
    @app_commands.choices(model=MODEL_CHOICES)
    async def ask_cmd(self, ctx, *, question: str, model: app_commands.Choice[str] = None):
        selected = model.value if model else (await db.get_config(ctx.guild.id, "ai_model") or "llama3")
        model_name = MODELS.get(selected, (selected,))[0]
        async with ctx.typing():
            response = await ask(selected, question)
        embed = discord.Embed(description=response, color=0x4CAF50)
        embed.set_author(name=model_name)
        embed.set_footer(text=f"Asked by {ctx.author.display_name}")
        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild: return
        if self.bot.user not in message.mentions: return
        prompt = message.content.replace(f"<@{self.bot.user.id}>", "").replace(f"<@!{self.bot.user.id}>", "").strip()
        if not prompt:
            await message.reply("Hey! Ask me anything or use `/ask`."); return
        model = await db.get_config(message.guild.id, "ai_model") or "llama3"
        model_name = MODELS.get(model, (model,))[0]
        async with message.channel.typing():
            response = await ask(model, prompt)
        embed = discord.Embed(description=response, color=0x4CAF50)
        embed.set_author(name=model_name)
        embed.set_footer(text="Mention me anytime or use /ask")
        await message.reply(embed=embed)

    @commands.hybrid_command(name="setai", description="Set the default AI model")
    @app_commands.describe(model="Default model")
    @app_commands.choices(model=MODEL_CHOICES)
    @commands.has_permissions(manage_guild=True)
    async def setai(self, ctx, model: app_commands.Choice[str]):
        await db.set_config(ctx.guild.id, "ai_model", model.value)
        await ctx.send(f"Default AI set to **{model.name}**!")

    @commands.hybrid_command(name="aimodels", description="Show available AI models")
    async def aimodels(self, ctx):
        embed = discord.Embed(title="AI Models", color=0x4CAF50)
        checks = {"llama3": GROQ_KEY, "gemini": GEMINI_KEY}
        default = await db.get_config(ctx.guild.id, "ai_model") or "llama3"
        for key, (name, desc, env) in MODELS.items():
            status = "Active" if checks[key] else "Not configured — add `" + env + "` to environment"
            is_default = " (server default)" if key == default else ""
            embed.add_field(name=f"{name}{is_default}", value=f"{desc}\nStatus: **{status}**", inline=False)
        await ctx.send(embed=embed)

async def setup(bot): await bot.add_cog(AI(bot))
