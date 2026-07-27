"""Downloads the AniList cover thumbnail and re-uploads it to the
configured Telegram thumbnail channel as a document (not a photo),
so Telegram doesn't recompress it — preserves original quality.
"""

import os

import aiohttp

import config

DOWNLOAD_DIR = "downloads"


async def download_thumbnail(anilist_id: int) -> str:
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    url = config.ANILIST_THUMBNAIL_URL.format(anilist_id=anilist_id)
    dest_path = os.path.join(DOWNLOAD_DIR, f"{anilist_id}.jpg")

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                raise RuntimeError(
                    f"Failed to download AniList thumbnail for ID {anilist_id} "
                    f"(status {resp.status})"
                )
            content = await resp.read()

    with open(dest_path, "wb") as f:
        f.write(content)
    return dest_path


def build_message_link(message) -> str:
    """Public helper — also reused by handlers/messages.py for manual
    thumbnail updates, so the link format stays consistent everywhere.
    """
    channel_username = message.chat.username
    if channel_username:
        return f"https://t.me/{channel_username}/{message.id}"
    chat_id_str = str(message.chat.id).replace("-100", "", 1)
    return f"https://t.me/c/{chat_id_str}/{message.id}"


async def upload_thumbnail(app, anilist_id: int, thumbnail_channel_id: int) -> str:
    """Downloads from img.anili.st and uploads to the thumbnail channel.
    Returns the Telegram message link to the uploaded document.
    """
    file_path = await download_thumbnail(anilist_id)
    try:
        message = await app.send_document(
            chat_id=thumbnail_channel_id,
            document=file_path,
            file_name=f"{anilist_id}.jpg",
            caption=f"AniList ID: {anilist_id}",
        )
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)
    return build_message_link(message)
