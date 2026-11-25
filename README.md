# dBot

Discord bot for the Dalcomsoft rhythm games (SuperStar). Python 3.14, discord.py, Postgres (asyncpg), Valkey for the lease.

Run `python dBot.py`. Tests: `uv run pytest` (needs Postgres, see `DBOT_TEST_PG`).

## Layout

| Where | What |
|---|---|
| `dBot.py`, `app.py`, `bot.py`, `config.py`, `tuning.py` | Start-up, the bot object, settings; `tuning.py` has the memory settings (malloc arenas, GC freeze, trimming) and `Pacer`. |
| `lease/` | Leader election in Valkey, the supervisor that restarts the bot's term, the event-loop watchdog, the console. |
| `games/` | Everything about the games, with no Discord in it. |
| `games/api/` | Talking to the game servers: login, accounts, requests, manifests, encryption, MagicOnion, store listings, world records. |
| `games/data/` | The game tables and catalogs: schema, files on disk, downloading, strings. |
| `games/media/` | Bundles and APKs, pictures, borders and their Google Drive folder. |
| `games/charts/` | Song charts: reading `.seq` files, measuring them, keeping the stats. |
| `games/bonus/` | Decks, dates (schedule, seasons), bonus periods and the calendar, notices. |
| `games/service.py`, `games/index.py` | The data service (what is current) and the indexes built from it. |
| `games/models.py`, `registry.py`, `errors.py`, `http.py` | Shared definitions: the games, their settings, errors, HTTP with retries. |
| `cogs/`, `ui/`, `search.py`, `ssl_pins.py` | The Discord layer: commands, embeds and views. |
| `tasks/` | Hourly and periodic jobs. `hourly.py` is the shape most share. |
| `db/` | Postgres access and migrations. |
| `pinata/`, `scripts/` | The pinata game; one-off and maintenance scripts. |

`REWRITE_STATUS.md` is the history of the rewrite; its module names are from before this layout.
