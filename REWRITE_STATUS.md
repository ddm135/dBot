# dBot rewrite: status summary

As of 24 October 2026. Covers what is done, what changed in this round, what is left, and the open decisions.

---

## 1. Where things stand

Every user-facing feature of v0 now exists in the rewrite except the heavy asset sync, world records, `forward_update`, `/coupon`, pinata and Alice. Storage moved from JSON on Drive to Postgres, and the song, deck and bonus logic now comes from the game's data tables instead of the spreadsheets.

| Area | State |
|---|---|
| Registry, config, game-server client, logins, data sync | Done (earlier rounds) |
| Deck and bonus logic (`decks.py`, `bonuses.py`) | **Done**, checked against your `bonus_periods.py` |
| Postgres storage layer | **Done** |
| Search and aliases | **Done** |
| `/info`, `/bonus` (list, top, live_theme, ping add/remove/list/time) | **Done** |
| `/ping` (word pings, ignore, unignore) and the listener | **Done** |
| `/role` | **Done** |
| `/ssl pin_by_name`, `pin_by_id` and the hourly SSL pin task | **Done** |
| `notify_bonus` task | **Done** |
| Owner commands, status messages, weekly-restart notice, day counters | **Done** |
| v0 data import (JSON to Postgres) | **Done** |
| Song charts: note counts and durations, read from bundles in place (`games/bundles.py`, `seq.py`, `songsync.py`, `tasks/song_stats.py`) | **Done**, checked against your `SM.json` for one song |
| Album art and emblems read from bundles (`games/images.py`), shown in `/info`, `/bonus list` and the SSL post | **Done**, unverified against a real image bundle |
| Built-in files from the game's `base_assets` APK (`games/apks.py`), for charts and images | **Done**, untested against Google Play |
| Borders: uploaded to Google Drive and announced (`games/borders.py`, `drive.py`, `tasks/borders.py`) | **Done**, not run against Drive |
| Hidden-song audio, artist info | Not started |
| World records, `forward_update` | Done (not run against live services) |
| Pinata ("Guitar Collecting", `guitar/`, `ui/pinata.py`, `tasks/pinata.py`) | **Done** |
| `/coupon`, Alice, hot reload | Not ported |

---

## 2. Files in this round

Every file goes at the same path in the project. All are LF.

**Changed:** `bot.py`, `config.py`, `games/service.py` (one added `server` property).

**New, game logic (pure, no Discord):** `games/decks.py`, `games/bonuses.py`, `games/scoring.py`, `games/notices.py`, `games/index.py`, `games/songstats.py`, `games/accounts.py`, `games/ssleague.py`.

**New, storage:** `db/` (`__init__`, `database`, `migrations`, `wordpings`, `roles`, `ssl`, `bonuspings`, `misc`, `legacy`), `scripts/import_v0.py`.

**New, Discord layer:** `cogs/` (`common`, `info`, `bonus`, `ping`, `role`, `ssl`, `admin`, `misc`, `status`), `ui/` (`text`, `pages`, `bonus`), `tasks/notify_bonus.py`, `tasks/pin_ssl.py`, `search.py`, `ssl_pins.py`, `extensions.py`.

**Tests** (122 tests) are in `tests/` plus `pytest.ini`. Your `.gitignore` excludes `**/test*`, so a `tests/` folder is invisible to git until that pattern changes.

---

## 3. How the new parts work

### Decks and bonuses
- `build_deck_index(tables)` is `deck_mapping.py` as a pure function. Decks and songs are keyed by code. A shared name gets `[code]` in its label, except a main deck.
- `bonuses.py` is `bonus_periods.py` with one deliberate change: periods are **not clipped to a calendar year**. A window across New Year is one period, so there are no artificial "ongoing" events on 1 January. Inside any single year the result is identical to your script (a randomised differential test compares them).
- Data timestamps are read as Korean dates (as in your script). Bonus days start at midnight in the game's own timezone.
- `/bonus list` now shows bonuses that **overlap** the chosen range, and has a new "Right Now" range (active today only).
- Entries follow the game's own list: a member birthday is one entry ("All Songs" when it covers the whole deck), and every song that also has a release anniversary gets its own entry with the combined total.
- **Checked against real data:** with your four files and a live theme bonus of 90,000, all 33 entries of the list you pasted for 25 October 2026 are reproduced exactly (percentage, dates, and max score).
- `/bonus top` "Highest Bonuses Only" lists **every** deck with only its best-scoring entries (ties all stay), best score first, ended ones included. Decks are ordered by `secondOrderIndex` then `orderIndex`, songs by code; both match your old list except where it was ordered by hand (TAEYEON, the NCT U trio).
- Max score = deck base score (member count based) + bonus % + live theme, as in v0.

### Bonus pings
- v0 applied a changed ping time only after the day ended. Now the change is immediate, and a delivery log (`bonus_ping_log`) guarantees one ping per user, game, day and kind. A ping due at 23:00 is still sent if the bot was down then, until midnight.
- A failed send is retried at the next hour. Closed DMs are not retried.
- `/bonus ping list` replies privately instead of sending a DM.

### Word pings
- Words are case-insensitive and stored lower case (v0 kept "Cat" and "cat" apart).
- Pings are cached in memory and written through to Postgres.
- **Behaviour change:** a ping is only sent if the recipient can read the channel. v0 would DM message text from channels the user could not see.
- A user gets at most one DM per message.

### SSL
- One row per game and day in `ssl_history`; "last appearance" is the latest earlier day for the song and for its deck.
- The hourly task pins as soon as the game's SSL day (clock minus 2 hours) has no row yet, so a restart at 02:00 no longer skips the day. Manual pins record the day too.
- Old pins are unpinned by matching the weekday slot (`SSL #3`) in the embed author.

### Search
- Autocomplete values are the **codes** (`artist` = deck code, `song` = song code), so duplicate names cannot clash.
- Searching matches English, Korean and Japanese names, the analytics name, the code, and aliases from the `search_aliases` table.
- Aliases are managed with owner commands: `db!alias list|add|remove <game> <song|deck> <code> [alias]`.

### Storage (asyncpg-typed)

All SQL in `db/` is declared with `asyncpg-typed` as module-level statements with typed parameters and results (`sql("...", args=tuple[int, str], resultset=SomeNamedTuple)`). Multi-column results are NamedTuples whose field names must equal the column names. `tests/test_db.py::test_every_statement_matches_the_schema` prepares every statement against the real schema, because the library checks types only on prepare (and not on `execute`).

Things that changed with it: row counts now come from `RETURNING` (typed `execute` returns nothing); no jsonb codec is registered any more (the library encodes JSON itself); `PingPreferences` and `LastAppearance` are NamedTuples. The migration scripts are multi-statement text and still run as plain `execute`. The library treats every integer type as `int`, so it cannot catch a 32-bit column; a test with Discord-sized ids covers that.
Tables: `word_pings`, `word_ping_ignores`, `stored_roles`, `ssl_history`, `bonus_subscriptions`, `bonus_preferences`, `bonus_ping_log`, `live_themes`, `game_credentials`, `search_aliases`. Migrations run at startup under an advisory lock.

New environment variables: `POSTGRES_DATABASE` (defaults to the username) and `POSTGRES_TLS`.

### Migrating v0 data
After the bot has synced game data once:

    uv run python -m scripts.import_v0 --data-dir ./data

It reads v0's `credentials`, `word_pings`, `roles`, `ssleagues`, `live_theme` and `notify_bonus` JSON files, maps artist names to deck codes, and prints anything it could not match. It is safe to run twice.

---

## 4. Decisions that came out of this round

- Search aliases live in Postgres, edited with owner commands. A spreadsheet tab is not needed.
- `rename` is gone: nothing is keyed by name any more.
- Credentials are not set through Discord (secrets in chat). Use the import script, or insert into `game_credentials`.
- Day counters (`mots7`, `got7`, `baemon`, `bonusbot`) were kept; they cost nothing.

---

## 5. Verification

- 122 tests pass, with warnings treated as errors. The database tests run against a real Postgres 16.
- `ruff` is clean. `mypy --strict` is clean on every new module (the only warnings are the 5 older strict-only ones in `games/catalog.py`).
- Mutation checks over the bonus, notice, deck, scoring, search, role, ping and stats logic: every mutant was caught after adding five tests for the ones that first survived.
- A headless test loads all 13 extensions into a real `dBot` and checks the registered slash and prefix commands and their choices.
- Command callbacks for `/info`, `/bonus list|top|ping|live_theme` run against fake interactions.
- **Not verified against live services:** Discord itself (button views, embeds as rendered, permission behaviour), the game servers, and real game data. No real `MusicData`, `ArtistData`, `GroupData` or `LocaleData` was available; the logic is verified against synthetic tables and your script.

---

## 5b. Charts and bundles (new)

- Bundles are downloaded once to `data/files/<game>/<bundle name>` (v0's layout, so bundles v0 already has are reused) and **kept**. Files are read straight out of the bundle with UnityPy; nothing is unpacked.
- A chart's asset is found in its bundle by name (the key's file name without `.bytes`). The catalog supplies the bundle URL via `bundle_urls(key)`.
- `parse_seq` reproduces v0's `Seq` exactly: it matches your `SM.json` for song 770 (113 / 223 / 378 notes, 86.74169921875 s) and a randomised comparison against v0's own class.
- The hourly job (`:25`) only measures charts whose key or bundle changed, and saves every 50 bundles, so the long first run can be interrupted.
- Not yet verified: that the catalog's raw `internal_id` values are full download URLs (not tokens) for every game; a first run on real data will show it. Built-in bundles (inside the APK) are counted and skipped.
- Disk: SM alone has about 1,400 bundles of roughly 1 MB each.

### Built-in bundles (APK)

A catalog entry without a URL (`{UnityEngine.AddressableAssets.Addressables.RuntimePath}/Android/<name>`) is in the game's `base_assets` split APK from Google Play, at `assets/aa/Android/<name>`. The APK is downloaded once to `data/apks/<game>/<version>.apk` (v0's layout, so existing APKs are reused) and kept; a bundle is read out of the zip in memory and never written to disk. APKs already kept are searched newest first. Only if none has the bundle is the current version fetched, and after a miss Google Play is not asked again for an hour. If Google Play cannot be reached the built-in file is skipped and retried later. Checked on your real catalogs: every built-in id parses (SM 119 distinct APK members, JYP 10, SS 42, ATZ 8, SC 8, W1 16).

### Coverage on your real data (data.zip)

Every chart reference in all 12 non-BL games resolves. Charts: SM 4164, JYP 2676, SS 1452, ATZ 945, SC 540, W1 387, KD 246, PH 345, SMTOWN 4335, JYPNATION 996, EB 1311, LDH 228. Only 3 per catalog game (1 song each in JYP, SS and SC) are built in; they are read from the APK. W1 lists its charts in `SeqData`; SMTOWN, JYPNATION, EB and LDH store full URLs, which are downloaded as plain files (kept by URL, so a new `?v=` is fetched again).

Images: album art and in-game backgrounds are remote for every catalog game. Emblems are the exception: many are built in (SM 163 of 780, JYP 517 of 632), and are read from the APK; until it has been downloaded those decks show the game icon.

## 5c. Fixes after the first live run

- **Embed colours:** the tables store `0xRRGGBBAA` (e.g. `0x0f0f11FF`); the parser now drops the alpha as v0 did.
- **Bonus embeds now follow v0's layout:** `/bonus list` title `All Bonuses (October 19 - October 26)`, author `<game> - Bonus Info`, struck-through names and values for expired entries, members left out when they are the deck itself. `/bonus top` has no title (the decks are the fields, entry names in bold), and its max-score embed is `Max Score of This Week` with `Top 1-3` fields. `/bonus ping list` is one embed per game. Name escaping is v0's three characters. The SSL post lists note counts in chart order without commas.
- **Bonus pings follow v0's model:** a birthday is announced once for the deck ("All Songs"), and each song with an anniversary is announced on its own, with album, song and length. One embed per artist (artist and emblem as the author) with `Available ... :green_circle:` and `Ends ... :orange_circle:` fields, after the header `## Bonus Reminder for <game> on <date>`; sent silently.
- **Song stats now run at start-up** as soon as the first data sync is done (before, only at :25 each hour).
- **Built-in images:** a failed lookup was remembered for ever; it now expires after 10 minutes. The APK is downloaded in the background when the tables refer to built-in files, and the reason a built-in file is missing is logged once.
- **v0 import:** v0's leftover keys (`start`, `end`, `restart`, `reend`) under a game are ignored; artists are matched by English, Korean, Japanese and Chinese names, `æ` equals `ae`, and `X (Hidden)` maps to the hidden-only deck of that name. Unmatched names are reported once per game.

## 6. Known gaps and risks

1. **`/info` needs the heavy asset sync.** Durations and note counts come from `data/MusicData/<game>.json`, which v0 wrote and the rewrite does not yet write. If you reuse a v0 data directory they are there; otherwise `/info` shows "Unknown".
2. **No skill order.** `JYPNATION`, `EB` and `LDH` showed a skill order from the spreadsheet. No data table has it, so it is dropped.
3. **Images.** Album art and deck emblems are used only when the table refers to them by `URLs` code. Games that use catalog keys need bundle extraction (heavy sync), and show no image until then.
4. **Bonus rules are assumed to be the same for every game** (2% per artist code, 3% anniversary, 3-day window, artist type 4 excluded). They live in `BonusRules` if a game differs.
5. **BL** is covered by the section "BL" at the end: its tables come through the gRPC platform server, so `/info` and search work for it. It still has no bonuses (the game has none in its tables or sheet).
6. `/bonus top` "week" is Monday to the following Monday, as in v0. The "Highest Bonuses Only" and "Max Score" buttons are my reconstruction of v0's view; compare them with how you remember it.
7. `tasks/pin_ssl.py` uses `account.call(manifest, "StarLeague", "getWeekPlayMusic")`, which has never run against a live server.
8. First-run caveat from the last round still applies: manifest URLs for STARSHIP, ATEEZ, STAYC, WAKEONE and JYP, the classic login version, and the `dBot` nickname are unconfirmed.

---

## 7. Remaining work, in a suggested order

1. **Heavy asset sync:** `.seq` parsing (note counts, durations), hidden-song audio, border extraction, artist info (emblem, member count, max score, live theme max), catalog-only variant for BL, world-record season detection, base-assets APK.
2. **World records:** `/world_record` quarterly and weekly (`MusicRankServerUrl`).
4. **Leftovers:** `/coupon`, pinata, Alice, hot reload (decide whether to keep any).
5. Per-guild pin and forward settings in Postgres, if you want them editable at runtime.

---

## 8. Questions for you

1. Please check one real game: send me `MusicData`, `ArtistData`, `GroupData`, `LocaleData` (and `URLs`) for one game, plus its current bonus rows from the sheet, and I will compare the new `/bonus list` against it.
2. Should `/bonus list` with no time given show only what is active right now, like the list you pasted, or the whole year? Today it is the whole year; "Right Now" is a choice.
3. Are the bonus percentages and window really identical in every game?
4. Which leftovers should be ported: `/coupon`, Alice, pinata?
5. Should `.gitignore`'s `**/test*` be narrowed so `tests/` can be committed?

## World records

`/world_record quarterly` and `/world_record weekly` show the top-100 leaderboard of a song, or the first place of every song of an artist.

- `games/seasons.py`: quarterly seasons come from the `WorldRecordData` table (one row per reward tier, grouped by season; only seasons that have started are listed, in the game's timezone). Weekly games (W1) use Monday codes `YYYYMMDD`, the first being 2024-12-02; `check_weekly` validates a code.
- `games/worldrecords.py`: reads `{MusicRankServerUrl}/{season}/{item}/latest.json`, falling back to `latest_first.json`; 403/404 mean an empty board, other failures raise `WorldRecordError`. Results are cached for 60 seconds per URL, and artist views fetch up to 8 songs at once. `Last-Modified` is shown in the game's timezone.
- `ui/worldrecord.py`, `cogs/world_record.py`: v0's embed layout (10 rows per page, footer with "Last Updated"), season autocomplete newest first.
- Not verified against a live rank server.

Running the tests: `uv pip install pytest pytest-asyncio` (not in `pyproject.toml`), then `DBOT_TEST_PG=host:port:user:database uv run --no-sync pytest`. `mypy --strict` still reports the 5 old warnings in `games/catalog.py`; `ruff` is clean for the bot code.

## forward_update

`tasks/forward_update.py` runs at :15 every hour. For each game with a `forward` config:

- If the manifest has a `MaintenanceUrl`, it polls `DataService.is_online` every minute (fresh manifest with no maintenance URL, then, for games with a game server, `checkAssetBundle` answering code 1000; catalog-only games skip that second step). When the game is back it forwards every message of the maintenance channel to each target channel, oldest first, and purges the source.
- Otherwise, if a song (else a group) in the tables has a `displayStartAt` within the next 7 days (`games/forward.py`, in the game's timezone), it posts "Forwarding from <#source> on <t:...>" once in the next-update channel, waits until that moment, then forwards the same way, from the scheduled channel if the game has one.
- Differences from v0: the earliest coming song is used, not the first in file order; nothing is purged when no target channel could be reached; a crashed wait is logged and retried at the next hour instead of blocking the game for ever.

## BL (MagicOnion)

BL's platform server speaks gRPC with MessagePack bodies (`games/magiconion.py`), so its asset context does not come from the HTTP `checkAssetBundle` call the other games use.

- `GrpcConfig` on the game (target, CDN, AES key, `assetver`) drives it. `CheckAssetBundle("")` answers the bundle directory; `<cdn>/<Context>/%23AssetContext.json` lists the `.bin` tables, which are fetched from `<cdn>/<Context>/<file>`. That layout is from your sample and unverified against the live CDN.
- The tables are in the same format as the other games' (gzip, base64, AES-ECB, JSON), encrypted with the gRPC key, so `DataService` uses a cipher of its own for BL. The context is converted to the usual `a.json` shape (only the result, with full URLs), so the normal table sync, storage and versioning apply. If the platform server is down, the stored tables are used.
- Song names come from `analyticsData` (BL's `localeName` is 0), albums and artists from `LocaleData`. BL leaves `releaseDate` at a placeholder year (2077); `StartedAt` is used as the release date when a song has it (a guess: it is the only real date in the table).
- Note counts and lengths come from the catalog, found by key (`bytes_notes_<song>_<level>`), instead of from `MusicData`.
- BL now shows up in `/info` and search. Decks are the groups of `MusicData` (TAEYANG, JEON SOMI, ...), not v0's "Artist : Album" combinations; the album is shown on each song.
- Not done for BL: border extraction, album art (`image` is a catalog key; v0 used only the game icon), `GroupData` and `ThemeTypeData` were not in the samples, so deck names fall back to "Deck N" until the real `GroupData` is synced.

## Structure and naming (dedup pass)

The `Game` prefix is gone from class names (`Game` itself stays, as it is the thing being described):

| Before | After |
|---|---|
| `GameDataService` / `GameData` | `DataService` / `State` |
| `GameIndex` / `GameIndexes` | `Index` / `Indexes` |
| `GameCipher` | `Cipher` |
| `GameServer` | `Server` |
| `GameAccount` | `Account` |
| `GameError` / `GameServerError` | `ServiceError` / `ServerError` |
| `GameSearch` | `Search` |

Duplicated code that was merged:

- **AES:** `Cipher` is the only place that does AES. It has the base64 forms for the HTTP server and the data tables (`encrypt_cbc`, `decrypt_cbc`, `decrypt_ecb`) and the `IV || ciphertext` form for MagicOnion (`seal`, `unseal`); `magiconion.py` no longer has its own. A MagicOnion game's table cipher is the one its client already holds.
- **Downloads:** `http.fetch` is the one "GET, expect these statuses, mark network and server errors retryable" call; table downloads, BL's bundle context and the rank server use it with their own error class.
- **Timestamps:** `games/times.py` (`ms_to_datetime`, `ms_to_date`) replaces three separate conversions.
- **Names:** `decks.entry_name` is the one "locale text, else `analyticsData`" lookup for groups, artists and songs.
- **Discord:** `channels.find_channel` (cache, then fetch, with a type check) replaces three copies; `cogs/common.deck_of` and `choose_artist` replace six copies of the artist lookup; `ui/song.song_embed` is the shared start of the song embeds in `/info` and the SSL pins.
- **Predicates:** `has_bonuses` and `has_pins` are plain attribute getters; the `supports_bonuses` wrapper is gone.
- **Spreadsheet config removed:** nothing reads the spreadsheets any more, so `SheetConfig`, `SheetTable`, `ReplaceGrid`, the column tuples and the spreadsheet ids are gone from the registry. A game's bonus calendar is now the `has_bonuses` flag.
- **Tests:** `NO_RETRY` lives in `tests/data.py`; `tests/test_crypto.py` and `tests/test_channels.py` are new.

Left alone on purpose: the SQL statements in `db/` (each is a different statement) and the two places that still build an artist option block (a guard clause each).

## BL albums
BL songs are separated by album. `Game.album_decks` (True for BL) makes `build_deck_index`
use `AlbumData`: each album is a deck named "<artist> : <album>", with the album's
`releaseDate`. A song of no known album (the hidden one) stays in its artist's deck.
Album names come from the songs' `albumName`, which is per artist, so both TAEYANG albums
read "Down to Earth" and get a `[code]` suffix until real album names are known.

## BL names from the string tables
`games/strings.py` reads Unity Localization string tables from the kept bundles. The
catalog gives the bundles (`ItemName_<lang>` and `Assets/Localization/Tables/ItemName
Shared Data.asset`); no bundle name is written in code. `StringsConfig` on the game says
the collection, the languages and the keys: `Album_{code}` and `Group_{code}`. BL's album
and group names come from there (the group locale in `GroupData` points group 3 at
ALLDAY PROJECT; the string table says MEOVV). `tasks/strings_sync.py` fills
`State.strings` at start-up and at :35 every hour. Album art is the catalog key
`Image_Album_<albumCode>`.

## Borders
`games/borders.py` lists a game's borders by announced name: from the catalog keys for
catalog-only games (BL), from `ThemeTypeData` and `ThemeData` for the others (limited
themes only, with a `_Zoom` when the theme has one). `tasks/borders.py` (hourly, :40)
uploads what the game's Drive folder lacks and posts the link to `BORDER_CHANNEL_ID`.
The folder is the record of what was announced, so no table is needed. It needs the
service account file (`GOOGLE_CREDENTIALS_FILE`, default `/run/secrets/dBot.json`);
`BORDER_FOLDER_ID` overrides the folder. Without the file the task logs a warning and does nothing.

## Pinata
Every ten minutes on a day listed in `guitar/config.py` (KST), a box opens in each channel
of `CHANNELS`: five minutes to line up with the buttons, then one draw per prize. v0 only
ever posted to the test channel and had the date fixed to 0401 for testing; this posts
to both channels and uses the real date. Winners of a SuperStar role get it in their
stored roles; a guild role is given to the member; text prizes are only announced.

## Catalog URL and the APK's Addressables version
The catalog's URL has the build's Addressables version in its path, so it is not written
in the registry: `Game.catalog_url` has an `{addressables}` slot (and `{version}` for the
resource version). The version is `m_AddressablesVersion` in the game's `base_assets` APK,
`assets/aa/settings.json`. `ApkStore.newest_file` reads it from the newest APK (asking
Google Play at most once an hour for a newer one), so a game update that changes the path
is followed without a code change. A catalog already kept for the resource version is used
without the APK; downloading a new one needs the version, and fails (and is retried at
the next sync) if the APK cannot be read.