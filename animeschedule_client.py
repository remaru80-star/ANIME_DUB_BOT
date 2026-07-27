"""AnimeSchedule.net v3 API client.

ROOT-CAUSE FIX (2026-07-27): the `/timetables/dub` endpoint returns
`TimetableAnime` objects — title, route, episodeNumber, airType, etc.
— but these objects do **not** include a `websites` block or any MAL
id at all. Only the separate `/anime` search endpoint returns full
`Anime` objects with `websites.mal`. The original code tried to read
`websites.mal` off a *timetable* entry, which is always absent, so
every match silently failed and 100% of anime got skipped.

The fix bridges the two endpoints: query `/anime?mal-ids=<id>` to get
the AnimeSchedule `route` (slug) for a MAL id, then find that route
inside the dub timetable list (which does carry `route`).

This targets the *private* v3 API, which requires a Bearer token from
an Application created in your AnimeSchedule.net account (Settings ->
API tab). See README.md for how to get one.
"""

import aiohttp

import config


def _headers():
    return {"Authorization": f"Bearer {config.ANIMESCHEDULE_TOKEN}"}


async def get_dub_timetable() -> list:
    """Fetch the full current dub timetable (raw list of TimetableAnime)."""
    url = f"{config.ANIMESCHEDULE_API_BASE}/timetables/dub"
    async with aiohttp.ClientSession(headers=_headers()) as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                raise RuntimeError(
                    f"AnimeSchedule timetable request failed (status {resp.status}). "
                    f"Check ANIMESCHEDULE_TOKEN in your .env."
                )
            return await resp.json()


async def get_route_for_mal_id(mal_id: int):
    """Looks up the AnimeSchedule `route` (slug) for a MAL id via the
    /anime search endpoint (query param `mal-ids`) — the only endpoint
    that actually returns a `websites` block. Timetable entries don't
    carry a MAL id, so this indirection is required to bridge
    AniList/MAL ids to AnimeSchedule's own identifiers.

    Returns None if AnimeSchedule doesn't track this MAL id at all.
    """
    if not mal_id:
        return None

    url = f"{config.ANIMESCHEDULE_API_BASE}/anime"
    params = [("mal-ids", str(mal_id))]
    async with aiohttp.ClientSession(headers=_headers()) as session:
        async with session.get(url, params=params) as resp:
            if resp.status != 200:
                return None
            payload = await resp.json()
            anime_list = payload.get("anime") or []
            if not anime_list:
                return None
            return anime_list[0].get("route")


async def find_by_mal_id(mal_id: int, timetable: list = None):
    """Returns the dub timetable entry matching a MAL id, or None if
    AnimeSchedule doesn't track it or it's not in the current dub
    timetable (i.e. no confirmed English dub airing right now).
    """
    if not mal_id:
        return None

    route = await get_route_for_mal_id(mal_id)
    if not route:
        return None

    if timetable is None:
        timetable = await get_dub_timetable()
    for entry in timetable:
        if entry.get("route") == route:
            return entry
    return None


def get_last_dub_episode(entry: dict) -> int:
    """Best-effort extraction of the most recently aired dub episode number."""
    for key in ("episodeNumber", "episode", "episodes"):
        value = entry.get(key)
        if isinstance(value, int):
            return value
    return 0