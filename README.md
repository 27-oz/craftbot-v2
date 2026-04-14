# CraftBot v2.0

A clean, fast Minecraft community Discord bot. Built with Python, discord.py, SQLite, and hybrid commands (both `/` slash and `!` prefix work).

---

## Setup

### 1. Create your Discord bot
1. discord.com/developers/applications → New Application
2. Bot tab → Add Bot → copy token
3. Enable all Privileged Gateway Intents
4. OAuth2 → URL Generator → scopes: `bot` + `applications.commands` → permissions: Administrator
5. Invite to your server

### 2. Deploy on Render
1. Push repo to GitHub
2. render.com → New → Web Service → connect repo
3. Build command: `pip install -r requirements.txt`
4. Start command: `python bot.py`
5. Environment variables:
   - `DISCORD_TOKEN` — required
   - `PORT` — set to `8080`
   - `GROQ_API_KEY` — optional, for AI (groq.com, free)
   - `GEMINI_API_KEY` — optional, for AI (aistudio.google.com, free)
   - `TWITCH_CLIENT_ID` + `TWITCH_CLIENT_SECRET` — optional, for Twitch alerts

### 3. Keep it awake (UptimeRobot)
1. uptimerobot.com → sign up free
2. New Monitor → HTTP(s) → paste your Render URL → every 5 minutes

---

## Commands

Use `/help` in Discord. All commands work with both `/` and `!`.

| Category   | Key commands |
|------------|-------------|
| Moderation | `/warn` `/kick` `/ban` `/tempban` `/mute` `/purge` `/lock` `/setlog` |
| Leveling   | `/rank` `/leaderboard` `/perks` `/xpboost` `/setxp` `/addxp` |
| Economy    | `/balance` `/daily` `/transfer` `/shop` `/buy` `/richest` |
| Minecraft  | `/skin` `/uuid` `/wiki` `/mcstatus` `/tip` `/events` |
| Fun        | `/markov` `/mock` `/8ball` `/dice` `/coinflip` `/rps` `/joke` `/meme` |
| Feeds      | `/addtiktok` `/addtwitch` `/removetiktok` `/removetwitch` |
| AI         | `/ask` `/setai` `/aimodels` |
| Starboard  | `/setstarboard` |

---

## File structure

```
craftbot/
├── bot.py          — main entry point
├── db.py           — SQLite database setup
├── requirements.txt
├── render.yaml
├── .python-version
├── .env.example
└── cogs/
    ├── moderation.py
    ├── leveling.py
    ├── economy.py
    ├── minecraft.py
    ├── fun.py
    ├── feeds.py
    ├── ai.py
    └── starboard.py
```

---

## Changelog

### v2.0.0
- Full rewrite from scratch
- SQLite database replacing JSON files
- Hybrid commands (slash + prefix)
- Markov chain message generator
- AI integration (Groq + Gemini)
- Starboard
- Moderation logging
- Clean 8-cog structure

---

Copyright (c) 2026 27-oz. All Rights Reserved.
