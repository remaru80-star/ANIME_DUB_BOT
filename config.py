import os
from dotenv import load_dotenv

load_dotenv()

# ---- Telegram ----
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

# Comma-separated list of Telegram user IDs allowed to use admin commands
ADMIN_IDS = [
    int(x.strip()) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip()
]

# ---- MongoDB ----
MONGO_URI = os.environ.get("MONGO_URI", "")
DB_NAME = os.environ.get("DB_NAME", "SUBARU")

# ---- AnimeSchedule.net ----
# Private v3 API requires a Bearer token created from your account's
# Settings -> API tab (https://animeschedule.net/users/<username>/settings/api)
ANIMESCHEDULE_TOKEN = os.environ.get("ANIMESCHEDULE_TOKEN", "")
ANIMESCHEDULE_API_BASE = "https://animeschedule.net/api/v3"

# ---- AniList ----
ANILIST_API_URL = "https://graphql.anilist.co"

# ---- AniList thumbnail CDN ----
ANILIST_THUMBNAIL_URL = "https://img.anili.st/media/{anilist_id}"

# ---- MyAnimeList (official API) ----
# https://myanimelist.net/apiconfig -> create an app -> Client ID
MAL_CLIENT_ID = os.environ.get("MAL_CLIENT_ID", "")
MAL_API_BASE = "https://api.myanimelist.net/v2"

# ---- Bot behaviour ----
PAGE_SIZE = 8            # batches shown per page in inline lists
ANILIST_MAX_PAGES = 5    # pages of RELEASING anime to pull per /fetch_batches run
ANILIST_PER_PAGE = 50
MAL_REQUEST_DELAY = 0.2  # seconds between MAL API calls (official API is far more lenient than Jikan)
ANIMESCHEDULE_REQUEST_DELAY = 0.2  # seconds between AnimeSchedule /anime lookups (one per candidate anime)

# Prints every incoming private message to the console before any
# handler processes it — set DEBUG_LOG=true in .env to enable while
# troubleshooting "bot doesn't respond" issues.
DEBUG_LOG = os.environ.get("DEBUG_LOG", "false").lower() == "true"
