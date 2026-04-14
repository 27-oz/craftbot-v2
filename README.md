# CraftBot v2.0

A clean, fast Minecraft community Discord bot. Built with Python, discord.py, SQLite, and hybrid commands (both `/` slash and `!` prefix work).

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
