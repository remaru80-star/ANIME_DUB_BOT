"""Official MyAnimeList API v2 client — used only to pull the MAL
score (their `mean` field) for sorting batch lists by rating.

Needs a Client ID from https://myanimelist.net/apiconfig/references/authorization
(create an app; the ID alone is enough to auth read-only public
endpoints like this one — no OAuth token/user login needed).
"""

import aiohttp

import config


async def get_mal_score(mal_id: int):
    if not mal_id:
        return None
    if not config.MAL_CLIENT_ID:
        return None

    url = f"{config.MAL_API_BASE}/anime/{mal_id}"
    headers = {"X-MAL-CLIENT-ID": config.MAL_CLIENT_ID}
    params = {"fields": "mean"}

    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url, params=params) as resp:
            if resp.status != 200:
                return None
            payload = await resp.json()
            return payload.get("mean")
