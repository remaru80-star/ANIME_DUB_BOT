from motor.motor_asyncio import AsyncIOMotorClient

import config

_client = AsyncIOMotorClient(config.MONGO_URI)
db = _client[config.DB_NAME]

batches = db["batches"]
settings = db["settings"]  # single global-config document, _id="global"


async def ensure_indexes():
    """Call once at startup."""
    await batches.create_index("anilist_id", unique=True)
    await batches.create_index("mal_rating")
    await batches.create_index("searching")


async def get_thumbnail_channel_id():
    doc = await settings.find_one({"_id": "global"})
    return doc.get("thumbnail_channel_id") if doc else None


async def set_thumbnail_channel_id(channel_id: int):
    await settings.update_one(
        {"_id": "global"},
        {"$set": {"thumbnail_channel_id": channel_id}},
        upsert=True,
    )
