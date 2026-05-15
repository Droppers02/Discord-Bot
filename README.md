# EPA BOTCHI

Community Discord bot with economy, games, music, moderation, tickets, and utility systems.

This branch, `en`, is the English version. The Portuguese version lives on branch `main`.

## Features

- Economy with balances, shop, inventory, custom roles, trading, achievements, and auctions
- Casino and social games with stats and leaderboards
- Social progression with XP, levels, reputation, profiles, badges, and marriages
- Moderation with logs, automatic filters, strikes, anti-spam, and anti-raid protections
- Tickets, suggestions, giveaways, reminders, announcements, starboard, and AFK tools
- Music playback with queue management, controls, and `yt-dlp` integration

## Requirements

- Python 3.10 or newer
- FFmpeg available on the system or via `FFMPEG_PATH`
- A PostgreSQL database, such as Neon
- A Discord bot token

## Installation

```bash
git clone https://github.com/Droppers02/Discord-Community-Bot.git
cd Discord-Community-Bot
git checkout en
pip install -r requirements.txt
```

Create a `.env` file with at least:

```env
DISCORD_TOKEN=your_token_here
SQL_DATABASE_URL=postgresql://user:password@host/database?sslmode=require
BOT_LANGUAGE=en

# Optional
SERVER_ID=0
MOD_ROLE_ID=0
TICKET_CATEGORY_ID=0
OWNER_IDS=123456789012345678,987654321098765432
FFMPEG_PATH=ffmpeg
LOG_LEVEL=INFO
```

`DATABASE_URL` and `NEON_DATABASE_URL` are also accepted as aliases for `SQL_DATABASE_URL`.

Run the bot:

```bash
python main.py
```

## Database

- PostgreSQL is the primary persistence layer.
- The schema is created automatically on startup.
- Startup no longer imports legacy JSON or SQLite data automatically.
- `data/` and `logs/` remain in the repository only with `.gitkeep`; generated runtime files should stay out of version control.

## Project Structure

```text
EPA BOTCHI/
├── cogs/                  # Command modules
├── config/                # Settings and i18n
├── utils/                 # Database, logging, embeds, pagination
├── data/                  # Runtime-generated local data files
├── logs/                  # Runtime-generated log files
├── main.py                # Bot entry point
├── requirements.txt       # Python dependencies
└── README.md              # Documentation for this branch
```

## Development

- Use `python -m compileall main.py cogs utils config` for a quick validation pass.
- Keep `en` in English and `main` in European Portuguese.
- Do not reintroduce generated runtime state into the repository.

## License

Released under the MIT license. See `LICENSE` for details.
