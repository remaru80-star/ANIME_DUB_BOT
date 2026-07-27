# AnimeDub Batch Manager Bot

Pyrogram + Motor (async MongoDB) admin bot that:

1. Pulls all currently-airing (`RELEASING`) anime from **AniList**.
2. Keeps only the ones with a confirmed English dub, matched against
   **AnimeSchedule.net**'s dub timetable (by MAL ID).
3. Pulls the MAL rating from the **official MyAnimeList API** for sorting.
4. Downloads each anime's thumbnail from `https://img.anili.st/media/{anilist_id}`
   and re-uploads it as a **document** (not a photo) to your Telegram
   thumbnail channel — documents skip Telegram's photo recompression,
   so the image stays original quality.
5. Stores everything as one "batch" document per anime in MongoDB.
6. Gives you an admin bot to fetch, create, edit, delete, and
   start/stop batches from Telegram.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# fill in .env, then:
python main.py
```

### Getting your credentials

- **API_ID / API_HASH**: https://my.telegram.org
- **BOT_TOKEN**: create a bot via [@BotFather](https://t.me/BotFather)
- **ADMIN_IDS**: your Telegram numeric user ID(s) — get it from
  [@userinfobot](https://t.me/userinfobot)
- **MONGO_URI**: your MongoDB Atlas connection string
- **ANIMESCHEDULE_TOKEN**: go to
  `https://animeschedule.net/users/<your_username>/settings/api`,
  create an Application, copy its Bearer token
- **MAL_CLIENT_ID**: go to https://myanimelist.net/apiconfig, create
  an app, copy the Client ID (no OAuth/user login needed for this
  read-only lookup)

The bot must be an **admin** of your thumbnail channel (and, in
practice, of your sub channels too) so it can post there.

## Troubleshooting: bot connects but doesn't respond

If you see "AnimeDub admin bot is up" but commands get no reply:

1. **Set `DEBUG_LOG=true` in `.env` and restart.** Every incoming
   update now prints to the console. Send `/start` again:
   - **Nothing printed at all** → Telegram isn't delivering updates to
     this bot session. Confirm you're messaging the exact bot
     `main.py` just logged in as (it now prints `@username` on
     startup) — it's easy to have `BOT_TOKEN` pointed at a different
     bot than the one you're chatting with.
   - **Something is printed, but still no reply** → the handler itself
     is erroring. Pyrogram swallows exceptions inside handlers by
     default; temporarily add `import traceback` and wrap the handler
     body in `try/except Exception: traceback.print_exc()` to see the
     real error, or run with `pyrogram`'s logging enabled
     (`import logging; logging.basicConfig(level=logging.INFO)` near
     the top of `main.py`).
2. **Check `ADMIN_IDS` in `.env`.** If your numeric Telegram ID isn't
   in that comma-separated list exactly, `/fetch_batches`, `/edit_batch`,
   etc. reply "You're not authorized" — but `/start` has no admin
   check, so if even `/start` gets nothing, this isn't the cause.
3. **Confirm you're in a private chat with the bot**, not a group —
   these handlers are scoped to `filters.private`.
4. **Re-check `requirements.txt` installed inside your venv** —
   `pip install -r requirements.txt` while the venv shown in your
   prompt is active. A missing `pyrogram`/`motor`/`aiohttp` would have
   thrown on import before "is up" ever printed, so that's less likely
   given what you're seeing — but worth a quick `pip list` check.

## Commands

| Command | What it does |
|---|---|
| `/fetch_batches` | Full sweep: AniList → AnimeSchedule.net → MyAnimeList → upserts all currently-ongoing English-dubbed anime as batches. Existing batches get their metadata refreshed; your manual edits (last uploaded episode, searching status, sub channel) are never overwritten by this. |
| `/new_batch` | Add one anime manually by AniList ID. |
| `/delete_batch` | Button list (sorted by MAL rating) to remove a batch. |
| `/edit_batch` | Button list (sorted by MAL rating) → per-batch menu to update thumbnail, last uploaded episode, or sub channel. |
| `/manage_search` | Button list with a 🟢/🔴 toggle per batch for the `searching` start/stop flag. |
| `/set_thumbnail_channel` | Forward a message from the channel (or send its numeric ID) to set where thumbnails get uploaded. |

## Database schema

One document per anime in the `batches` collection:

```python
{
    # External IDs + URIs
    "anilist_id": int,
    "anilist_uri": str,
    "mal_id": int,
    "mal_uri": str,
    "animeschedule_id": str,
    "animeschedule_uri": str,

    # Metadata (AniList)
    "english_title": str,
    "japanese_title": str,
    "type": str,
    "genres": [str],
    "synopsis": str,
    "runtime": int,
    "total_episodes": int,
    "season": str,          # e.g. "Season 01" — heuristic, see caveat below
    "status": str,
    "mal_rating": float,    # from the official MAL API

    # Dub tracking (AnimeSchedule.net)
    "audio": str,
    "last_dub_episode": int,

    # Your pipeline state (never overwritten by /fetch_batches)
    "last_uploaded_episode": int,   # defaults to last_dub_episode, editable
    "searching": bool,
    "telegram_thumbnail_path": str,
    "telegram_sub_channel_link": str,

    "anilist_thumbnail_url": str,
}
```

Indexes: unique on `anilist_id`, plus indexes on `mal_rating` and
`searching` for the sorted/filtered list views.

## Honest caveats — please read before running

- **AnimeSchedule.net field names**: their private v3 API requires an
  authenticated account to query, so `animeschedule_client.py` is
  built from their public documentation, not a live response I could
  test against. If your account's JSON differs from what's assumed
  (`websites.mal`, `episodeNumber`, `route`), open
  `animeschedule_client.py` — `_extract_mal_id()` and
  `get_last_dub_episode()` are the two functions to adjust. Everything
  downstream (batch building, DB schema, bot commands) stays the same.
- **Season numbering**: neither AniList nor AnimeSchedule.net expose
  clean "Season 01/02" numbering — AniList treats each cour as a
  separate entry linked via `relations`. The bot estimates season
  number by counting same-format `PREQUEL` edges. It's a reasonable
  starting point, not guaranteed correct for every franchise — use
  `/edit_batch` to override if it gets one wrong (episode/sub-channel
  editing is wired up; if you also want a "correct season number"
  button added to that menu, that's a quick addition).
- **MyAnimeList API rate limits**: not officially published, but it's
  far more generous than Jikan's public proxy was. The bot still
  sleeps 0.2s between calls during `/fetch_batches` as a courtesy —
  lower `MAL_REQUEST_DELAY` in `.env` if you find it's unnecessary, or
  raise it if you start seeing 429s.

## File structure

```
animedub_bot/
├── main.py                  # entry point
├── bot_instance.py          # shared Pyrogram Client
├── config.py                # env vars / constants
├── database.py               # Motor connection, collections, indexes
├── anilist_client.py         # AniList GraphQL queries
├── animeschedule_client.py   # AnimeSchedule.net dub timetable + matching
├── mal_client.py              # MAL rating lookup (official API)
├── thumbnail_service.py      # img.anili.st download + Telegram upload
├── batch_service.py          # merges all sources, upserts batch docs
├── state.py                  # in-memory conversation state
├── keyboards.py              # inline keyboard builders
├── handlers/
│   ├── commands.py           # /start, /fetch_batches, /new_batch, etc.
│   ├── callbacks.py          # inline button handlers
│   └── messages.py           # FSM text/photo input routing
├── requirements.txt
└── .env.example
```
