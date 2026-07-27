from pyrogram import filters
from pyrogram.types import Message

import batch_service
import config
import keyboards
import state
from bot_instance import app
from database import batches


def _is_admin(message: Message) -> bool:
    return message.from_user is not None and message.from_user.id in config.ADMIN_IDS


async def _sorted_batches():
    return await batches.find().sort("mal_rating", -1).to_list(length=None)


@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message: Message):
    await message.reply(
        "**English Dub Batch Manager**\n\n"
        "/fetch_batches — Pull ongoing English-dubbed anime and build/refresh batches\n"
        "/new_batch — Manually add one anime by AniList ID\n"
        "/delete_batch — Delete a batch\n"
        "/edit_batch — Edit thumbnail / last uploaded episode / sub channel\n"
        "/manage_search — View and toggle start/stop searching status\n"
        "/set_thumbnail_channel — Set the channel thumbnails get uploaded to"
    )


@app.on_message(filters.command("fetch_batches") & filters.private)
async def fetch_batches_cmd(client, message: Message):
    if not _is_admin(message):
        return await message.reply("You're not authorized to use this bot.")

    status_msg = await message.reply("Fetching ongoing English-dubbed anime, please wait...")
    try:
        result = await batch_service.build_batches()
        await status_msg.edit(
            "Done.\n"
            f"New batches: {result['created']}\n"
            f"Updated: {result['updated']}\n"
            f"Skipped (no English dub found): {result['skipped_no_dub']}"
        )
    except Exception as e:
        await status_msg.edit(f"Fetch failed: {e}")


@app.on_message(filters.command("new_batch") & filters.private)
async def new_batch_cmd(client, message: Message):
    if not _is_admin(message):
        return await message.reply("You're not authorized to use this bot.")
    state.set_state(message.from_user.id, action="awaiting_new_batch_anilist_id")
    await message.reply("Send the AniList ID of the anime you want to add as a batch.")


@app.on_message(filters.command("delete_batch") & filters.private)
async def delete_batch_cmd(client, message: Message):
    if not _is_admin(message):
        return await message.reply("You're not authorized to use this bot.")
    docs = await _sorted_batches()
    if not docs:
        return await message.reply("No batches found. Run /fetch_batches first.")
    await message.reply(
        "Select a batch to delete:",
        reply_markup=keyboards.batch_list_keyboard(docs, page=1, mode="delete"),
    )


@app.on_message(filters.command("edit_batch") & filters.private)
async def edit_batch_cmd(client, message: Message):
    if not _is_admin(message):
        return await message.reply("You're not authorized to use this bot.")
    docs = await _sorted_batches()
    if not docs:
        return await message.reply("No batches found. Run /fetch_batches first.")
    await message.reply(
        "Select a batch to edit (sorted by MAL rating):",
        reply_markup=keyboards.batch_list_keyboard(docs, page=1, mode="edit"),
    )


@app.on_message(filters.command("manage_search") & filters.private)
async def manage_search_cmd(client, message: Message):
    if not _is_admin(message):
        return await message.reply("You're not authorized to use this bot.")
    docs = await _sorted_batches()
    if not docs:
        return await message.reply("No batches found. Run /fetch_batches first.")
    await message.reply(
        "Tap to toggle searching status (🟢 = on, 🔴 = off):",
        reply_markup=keyboards.search_toggle_keyboard(docs, page=1),
    )


@app.on_message(filters.command("set_thumbnail_channel") & filters.private)
async def set_thumbnail_channel_cmd(client, message: Message):
    if not _is_admin(message):
        return await message.reply("You're not authorized to use this bot.")
    state.set_state(message.from_user.id, action="awaiting_thumbnail_channel")
    await message.reply(
        "Forward any message from the target thumbnail channel, "
        "or send its numeric channel ID (e.g. -1001234567890).\n\n"
        "Note: the bot must already be an admin in that channel."
    )
