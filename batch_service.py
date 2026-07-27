import asyncio

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


async def _count_prequel_chain(media: dict, max_depth: int = 20) -> int:
    """Walks the PREQUEL chain backward via the AniList API to count how
    many same-format entries precede this one.

    `media["relations"]` only contains this entry's own *immediate*
    PREQUEL/SEQUEL edge, not the whole franchise chain — so checking it
    once only ever tells you "does a prior season exist? yes/no", which
    is why the old version returned "Season 02" for every non-first
    season regardless of how many came before it. To get an actual
    count we have to follow the chain one hop at a time, re-fetching
    each prequel's own relations, until an entry has no further PREQUEL.
    """
    count = 1
    current = media
    depth = 0
    while depth < max_depth:
        prequel_id = None
        for edge in (current.get("relations") or {}).get("edges", []):
            node = edge.get("node") or {}
            if edge.get("relationType") == "PREQUEL" and node.get("format") == media.get("format"):
                prequel_id = node.get("id")
                break
        if not prequel_id:
            break
        current = await anilist_client.fetch_media_by_id(prequel_id)
        if not current:
            break
        count += 1
        depth += 1
        await asyncio.sleep(0.1)  # be polite to AniList during the chain walk
    return count


async def _derive_season_label(media: dict) -> str:
    """AniList has no native cour/season numbering — each season is a
    separate Media entry linked via relations, chained together one
    hop at a time. We estimate the season number by walking that
    PREQUEL chain back to its start.
    Treat this as a starting point, not a guarantee: override manually
    via /edit_batch for titles where this heuristic gets it wrong (e.g.
    a "Director's Cut" re-release tagged PREQUEL with the same format
    would still inflate the count by one).
    """
    count = await _count_prequel_chain(media)
    return f"Season {count:02d}"


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