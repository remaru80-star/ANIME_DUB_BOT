"""AniList GraphQL client.

Only handles what this bot needs: pulling currently-releasing anime
(with the fields required for the batch schema) and fetching a single
anime by AniList ID for the manual /new_batch flow.
"""

import aiohttp

import config

RELEASING_QUERY = """
query ($page: Int, $perPage: Int) {
  Page(page: $page, perPage: $perPage) {
    pageInfo {
      hasNextPage
    }
    media(type: ANIME, status: RELEASING, sort: POPULARITY_DESC) {
      id
      idMal
      title {
        romaji
        english
        native
      }
      format
      genres
      description(asHtml: false)
      episodes
      duration
      status
      relations {
        edges {
          relationType
          node {
            id
            format
          }
        }
      }
    }
  }
}
"""

MEDIA_BY_ID_QUERY = """
query ($id: Int) {
  Media(id: $id, type: ANIME) {
    id
    idMal
    title {
      romaji
      english
      native
    }
    format
    genres
    description(asHtml: false)
    episodes
    duration
    status
    relations {
      edges {
        relationType
        node {
          id
          format
        }
      }
    }
  }
}
"""


async def _post(query: str, variables: dict) -> dict:
    async with aiohttp.ClientSession() as session:
        async with session.post(
            config.ANILIST_API_URL,
            json={"query": query, "variables": variables},
            headers={"Content-Type": "application/json"},
        ) as resp:
            payload = await resp.json()
            if resp.status != 200 or "errors" in payload:
                raise RuntimeError(f"AniList API error: {payload}")
            return payload["data"]


async def fetch_releasing_anime(
    max_pages: int = config.ANILIST_MAX_PAGES,
    per_page: int = config.ANILIST_PER_PAGE,
) -> list:
    """Returns a flat list of all currently RELEASING anime across pages."""
    results = []
    page = 1
    while page <= max_pages:
        data = await _post(RELEASING_QUERY, {"page": page, "perPage": per_page})
        page_data = data["Page"]
        results.extend(page_data["media"])
        if not page_data["pageInfo"]["hasNextPage"]:
            break
        page += 1
    return results


async def fetch_media_by_id(anilist_id: int):
    data = await _post(MEDIA_BY_ID_QUERY, {"id": anilist_id})
    return data.get("Media")
