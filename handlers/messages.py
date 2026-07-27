import os

from pyrogram import filters
from pyrogram.types import Message

import batch_service
import state
from bot_instance import app
from database import batches, get_thumbnail_channel_id, set_thumbnail_channel_id
from thumbnail_service import build_message_link

TRACKED_COMMANDS = [
    "start",
    "fetch_batches",
    "set_thumbnail_channel",
    "edit_batch",
    "new_batch",
    "delete_batch",
    "manage_search",
]


@app.on_message(
    filters.private
    & (filters.text | filters.photo | filters.document)
    & ~filters.command(TRACKED_COMMANDS)
)
async def state_router(client, message: Message):
    st = state.get_state(message.from_user.id)
    if not st:
        return

    action = st.get("action")

    if action == "awaiting_thumbnail_channel":
        await _handle_thumbnail_channel(message)
    elif action == "awaiting_thumbnail":
        await _handle_thumbnail_update(client, message, st["anilist_id"])
    elif action == "awaiting_episode":
        await _handle_episode_update(message, st["anilist_id"])
    elif action == "awaiting_sub_channel":
        await _handle_sub_channel_update(message, st["anilist_id"])
    elif action == "awaiting_new_batch_anilist_id":
        await _handle_new_batch(message)


async def _handle_thumbnail_channel(message: Message):
    channel_id = None
    if message.forward_from_chat:
        channel_id = message.forward_from_chat.id
    elif message.text and message.text.strip().lstrip("-").isdigit():
        channel_id = int(message.text.strip())

    if channel_id is None:
        return await message.reply(
            "Couldn't detect a channel. Forward a message from it, or send its numeric ID."
        )

    await set_thumbnail_channel_id(channel_id)
    state.clear_state(message.from_user.id)
    await message.reply(f"Thumbnail channel set to `{channel_id}`.")


async def _handle_thumbnail_update(client, message: Message, anilist_id: int):
    if not (message.photo or message.document):
        return await message.reply("Please send an image (photo or document).")

    thumbnail_channel_id = await get_thumbnail_channel_id()
    if not thumbnail_channel_id:
        state.clear_state(message.from_user.id)
        return await message.reply("No thumbnail channel set yet — run /set_thumbnail_channel first.")

    file_path = await client.download_media(message)
    try:
        sent = await client.send_document(
            chat_id=thumbnail_channel_id,
            document=file_path,
            file_name=f"{anilist_id}.jpg",
            caption=f"AniList ID: {anilist_id} (manual update)",
        )
    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

    link = build_message_link(sent)
    await batches.update_one({"anilist_id": anilist_id}, {"$set": {"telegram_thumbnail_path": link}})
    state.clear_state(message.from_user.id)
    await message.reply("Thumbnail updated.")


async def _handle_episode_update(message: Message, anilist_id: int):
    if not message.text or not message.text.strip().isdigit():
        return await message.reply("Please send a valid episode number.")
    ep = int(message.text.strip())
    await batches.update_one({"anilist_id": anilist_id}, {"$set": {"last_uploaded_episode": ep}})
    state.clear_state(message.from_user.id)
    await message.reply(f"Last uploaded episode set to {ep}.")


async def _handle_sub_channel_update(message: Message, anilist_id: int):
    if not message.text:
        return await message.reply("Please send a valid channel link.")
    link = message.text.strip()
    await batches.update_one({"anilist_id": anilist_id}, {"$set": {"telegram_sub_channel_link": link}})
    state.clear_state(message.from_user.id)
    await message.reply("Sub channel updated.")


async def _handle_new_batch(message: Message):
    if not message.text or not message.text.strip().isdigit():
        return await message.reply("Please send a numeric AniList ID.")
    anilist_id = int(message.text.strip())

    status_msg = await message.reply("Fetching data and building batch...")
    try:
        result = await batch_service.build_single_batch(anilist_id)
        if result:
            await status_msg.edit(f"Batch created for **{result.get('english_title')}**.")
        else:
            await status_msg.edit("Couldn't find an English dub for that AniList ID — batch not created.")
    except Exception as e:
        await status_msg.edit(f"Failed: {e}")
    finally:
        state.clear_state(message.from_user.id)
