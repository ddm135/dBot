# dBot

Discord bot for the Dalcomsoft rhythm games (SuperStar). Python 3.14, discord.py, Postgres (asyncpg), Valkey for the lease.

Run `python dBot.py`. Tests: `uv run pytest` (needs Postgres, see `DBOT_TEST_PG`).

## Layout

| Where | What |
|---|---|
| `dBot.py`, `app.py`, `bot.py`, `config.py` | Start-up, the bot object, settings. |
| `lease/` | Leader election in Valkey and the supervisor that restarts the bot's term. |
| `ops/` | The event-loop watchdog, the console, and `tuning` (memory settings: malloc arenas, GC freeze, trimming; and `Pacer`). |
| `games/` | Everything about the games, with no Discord in it. |
| `games/api/` | Talking to the game servers and CDNs: HTTP with retries, login, accounts, requests, manifests, encryption, MagicOnion, store listings, world records. |
| `games/data/` | What the game tables say: schema, files on disk, downloading, strings, decks and songs, dates and seasons. |
| `games/media/` | Bundles and APKs, pictures, borders and their Google Drive folder. |
| `games/charts/` | Song charts: reading `.seq` files, measuring them, keeping the stats. |
| `games/bonus/` | The bonus rules and periods (`periods`), the calendar of events (`events`), the deck-level entries (`entries`) and the notices built from them. |
| `games/service.py`, `games/index.py` | The data service (what is current) and the indexes built from it. |
| `games/models.py`, `registry.py`, `errors.py` | Shared definitions: the games, their settings, errors. |
| `cogs/`, `ui/` | The Discord layer: commands, and in `ui/` the embeds, views, name search for autocomplete and the SSL pinning. |
| `tasks/` | Hourly and periodic jobs. `hourly.py` is the shape most share. |
| `db/` | Postgres access and migrations. |
| `pinata/`, `scripts/` | The pinata game; one-off and maintenance scripts. |

`REWRITE_STATUS.md` is the history of the rewrite; its module names are from before this layout.
