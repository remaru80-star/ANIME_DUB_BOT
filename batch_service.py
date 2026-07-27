import asyncio
import re

import anilist_client
import animeschedule_client
import config
import mal_client
from bot_instance import app
from database import batches, get_thumbnail_channel_id
from thumbnail_service import upload_thumbnail


def _anilist_uri(anilist_id: int) -> str:
    return f"https://anilist.co/anime/{anilist_id}"


def _mal_uri(mal_id):
    return f"https://myanimelist.net/anime/{mal_id}" if mal_id else None


_ROMAN_NUMERALS = {
    "I": 1, "II": 2, "III": 3, "IV": 4, "V": 5,
    "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10,
    "XI": 11, "XII": 12, "XIII": 13, "XIV": 14, "XV": 15,
}


def _roman_to_int(token: str):
    return _ROMAN_NUMERALS.get(token.upper())


def _season_from_title(title: str):
    """Parses a season number directly out of a title string, checked
    in priority order:
      1. "Season 3" / "season III"    -> explicit word + arabic/roman number
      2. "S3" / "S03"                 -> abbreviated form
      3. "3rd Season" / "2nd season"  -> ordinal + word
      4. a trailing bare number, e.g. "... Reincarnation 3"
      5. a trailing roman numeral, e.g. "... Reincarnation III"
    Returns None if nothing matches (caller defaults to Season 1).
    """
    if not title:
        return None
    title = title.strip()

    m = re.search(r"\bseason\s+([IVXLCDM]+|\d+)\b", title, re.IGNORECASE)
    if m:
        token = m.group(1)
        return int(token) if token.isdigit() else _roman_to_int(token)

    m = re.search(r"\bS(\d{1,2})\b", title)
    if m:
        return int(m.group(1))

    m = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)\s+season\b", title, re.IGNORECASE)
    if m:
        return int(m.group(1))

    m = re.search(r"(\d{1,2})\s*$", title)
    if m:
        return int(m.group(1))

    m = re.search(r"\b([IVXLCDM]{1,6})\s*$", title, re.IGNORECASE)
    if m:
        val = _roman_to_int(m.group(1))
        if val:
            return val

    return None


async def _derive_season_label(media: dict) -> str:
    """AniList has no native cour/season numbering, and walking the
    PREQUEL relation chain turned out to be unreliable — side stories,
    OVAs, or alt-format entries chained in with a PREQUEL relation
    inflate a pure relation-count (e.g. Mushoku Tensei Season 3 was
    coming back as "Season 05" that way). Parsing the number straight
    out of the title text is more robust, so that's what this does now
    — see `_season_from_title()` for the exact patterns checked.
    Falls back to Season 1 if no pattern matches anywhere in the title.
    Treat this as a starting point, not a guarantee: override manually
    via /edit_batch for titles this still gets wrong (e.g. a title with
    no season marker at all, like "... Final Season").
    """
    title = (media.get("title") or {}).get("english") or (media.get("title") or {}).get("romaji") or ""
    season_num = _season_from_title(title)
    if season_num is None:
        season_num = 1
    return f"Season {season_num:02d}"


async def _build_doc_fields(media: dict, dub_entry: dict, mal_score) -> dict:
    anilist_id = media["id"]
    mal_id = media.get("idMal")
    route = dub_entry.get("route")

    return {
        "anilist_id": anilist_id,
        "anilist_uri": _anilist_uri(anilist_id),
        "mal_id": mal_id,
        "mal_uri": _mal_uri(mal_id),
        "animeschedule_id": route,
        "animeschedule_uri": f"https://animeschedule.net/anime/{route}" if route else None,
        "english_title": (media.get("title") or {}).get("english")
        or (media.get("title") or {}).get("romaji"),
        "japanese_title": (media.get("title") or {}).get("native"),
        "type": media.get("format"),
        "genres": media.get("genres") or [],
        "synopsis": media.get("description"),
        "runtime": media.get("duration"),
        "total_episodes": media.get("episodes"),
        "season": await _derive_season_label(media),
        "status": media.get("status"),
        "mal_rating": mal_score,
        "audio": "English Dub",
        "last_dub_episode": animeschedule_client.get_last_dub_episode(dub_entry),
        "anilist_thumbnail_url": config.ANILIST_THUMBNAIL_URL.format(anilist_id=anilist_id),
    }


async def _upsert_batch(media: dict, dub_entry: dict):
    anilist_id = media["id"]
    mal_id = media.get("idMal")

    mal_score = await mal_client.get_mal_score(mal_id)
    await asyncio.sleep(config.MAL_REQUEST_DELAY)

    doc_fields = await _build_doc_fields(media, dub_entry, mal_score)
    existing = await batches.find_one({"anilist_id": anilist_id})

    if existing:
        # Metadata refresh only — never touch user-editable fields
        # (last_uploaded_episode, searching, telegram_* fields) on re-fetch.
        await batches.update_one({"_id": existing["_id"]}, {"$set": doc_fields})
        return doc_fields, "updated"

    thumbnail_channel_id = await get_thumbnail_channel_id()
    telegram_thumbnail_path = None
    if thumbnail_channel_id:
        try:
            telegram_thumbnail_path = await upload_thumbnail(app, anilist_id, thumbnail_channel_id)
        except Exception:
            telegram_thumbnail_path = None  # fetch continues even if one upload fails

    doc_fields.update(
        {
            "last_uploaded_episode": doc_fields["last_dub_episode"],
            "searching": False,
            "telegram_thumbnail_path": telegram_thumbnail_path,
            "telegram_sub_channel_link": None,
        }
    )
    await batches.insert_one(doc_fields)
    return doc_fields, "created"


async def build_batches() -> dict:
    """Full sweep: pulls all RELEASING anime from AniList, keeps only
    the ones with a confirmed English dub on AnimeSchedule.net, and
    upserts them as batches.
    """
    anilist_media = await anilist_client.fetch_releasing_anime()
    dub_timetable = await animeschedule_client.get_dub_timetable()

    created = updated = skipped_no_dub = 0

    for media in anilist_media:
        mal_id = media.get("idMal")
        if not mal_id:
            skipped_no_dub += 1
            continue

        dub_entry = await animeschedule_client.find_by_mal_id(mal_id, timetable=dub_timetable)
        await asyncio.sleep(config.ANIMESCHEDULE_REQUEST_DELAY)
        if not dub_entry:
            skipped_no_dub += 1
            continue

        _, action = await _upsert_batch(media, dub_entry)
        if action == "created":
            created += 1
        else:
            updated += 1

    return {"created": created, "updated": updated, "skipped_no_dub": skipped_no_dub}


async def build_single_batch(anilist_id: int):
    """Manual /new_batch flow — adds one anime by AniList ID, if it has
    a confirmed English dub. Returns the built doc, or None if no dub
    was found (or the AniList ID doesn't exist).
    """
    media = await anilist_client.fetch_media_by_id(anilist_id)
    if not media:
        return None

    mal_id = media.get("idMal")
    if not mal_id:
        return None

    dub_entry = await animeschedule_client.find_by_mal_id(mal_id)
    if not dub_entry:
        return None

    doc_fields, _ = await _upsert_batch(media, dub_entry)
    return doc_fields
