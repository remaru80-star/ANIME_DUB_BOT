from pyrogram import filters
from pyrogram.types import CallbackQuery

import keyboards
import state
from bot_instance import app
from database import batches


async def _sorted_batches():
    return await batches.find().sort("mal_rating", -1).to_list(length=None)


def _format_batch_text(doc: dict) -> str:
    return (
        f"**{doc.get('english_title')}**\n"
        f"Japanese: {doc.get('japanese_title')}\n"
        f"Type: {doc.get('type')} | Season: {doc.get('season')}\n"
        f"MAL Rating: {doc.get('mal_rating')}\n"
        f"Status: {doc.get('status')}\n"
        f"Total Episodes: {doc.get('total_episodes')}\n"
        f"Last Dub Episode: {doc.get('last_dub_episode')}\n"
        f"Last Uploaded Episode: {doc.get('last_uploaded_episode')}\n"
        f"Sub Channel: {doc.get('telegram_sub_channel_link') or 'Not set'}\n"
        f"Searching: {'🟢 On' if doc.get('searching') else '🔴 Off'}"
    )


@app.on_callback_query(filters.regex(r"^edit_page:(\d+)$"))
async def edit_page_cb(client, cq: CallbackQuery):
    page = int(cq.matches[0].group(1))
    docs = await _sorted_batches()
    if not docs:
        return await cq.answer("No batches left.", show_alert=True)
    await cq.message.edit_text(
        "Select a batch to edit (sorted by MAL rating):",
        reply_markup=keyboards.batch_list_keyboard(docs, page=page, mode="edit"),
    )
    await cq.answer()


@app.on_callback_query(filters.regex(r"^delete_page:(\d+)$"))
async def delete_page_cb(client, cq: CallbackQuery):
    page = int(cq.matches[0].group(1))
    docs = await _sorted_batches()
    if not docs:
        return await cq.message.edit_text("No batches left.")
    await cq.message.edit_reply_markup(keyboards.batch_list_keyboard(docs, page=page, mode="delete"))
    await cq.answer()


@app.on_callback_query(filters.regex(r"^search_page:(\d+)$"))
async def search_page_cb(client, cq: CallbackQuery):
    page = int(cq.matches[0].group(1))
    docs = await _sorted_batches()
    if not docs:
        return await cq.message.edit_text("No batches left.")
    await cq.message.edit_reply_markup(keyboards.search_toggle_keyboard(docs, page=page))
    await cq.answer()


@app.on_callback_query(filters.regex(r"^edit_batch:(-?\d+)$"))
async def edit_batch_cb(client, cq: CallbackQuery):
    anilist_id = int(cq.matches[0].group(1))
    doc = await batches.find_one({"anilist_id": anilist_id})
    if not doc:
        return await cq.answer("Batch not found.", show_alert=True)
    await cq.message.edit_text(_format_batch_text(doc), reply_markup=keyboards.batch_edit_menu(anilist_id))
    await cq.answer()


@app.on_callback_query(filters.regex(r"^delete_batch:(-?\d+)$"))
async def delete_batch_cb(client, cq: CallbackQuery):
    anilist_id = int(cq.matches[0].group(1))
    result = await batches.delete_one({"anilist_id": anilist_id})
    if not result.deleted_count:
        return await cq.answer("Batch not found.", show_alert=True)

    await cq.answer("Batch deleted.", show_alert=True)
    docs = await _sorted_batches()
    if docs:
        await cq.message.edit_reply_markup(keyboards.batch_list_keyboard(docs, page=1, mode="delete"))
    else:
        await cq.message.edit_text("No batches left.")


@app.on_callback_query(filters.regex(r"^toggle_search:(-?\d+)$"))
async def toggle_search_cb(client, cq: CallbackQuery):
    anilist_id = int(cq.matches[0].group(1))
    doc = await batches.find_one({"anilist_id": anilist_id})
    if not doc:
        return await cq.answer("Batch not found.", show_alert=True)

    new_status = not doc.get("searching", False)
    await batches.update_one({"anilist_id": anilist_id}, {"$set": {"searching": new_status}})

    docs = await _sorted_batches()
    await cq.message.edit_reply_markup(keyboards.search_toggle_keyboard(docs, page=1))
    await cq.answer(f"Searching {'started' if new_status else 'stopped'}.")


@app.on_callback_query(filters.regex(r"^set_thumb:(-?\d+)$"))
async def set_thumb_cb(client, cq: CallbackQuery):
    anilist_id = int(cq.matches[0].group(1))
    state.set_state(cq.from_user.id, action="awaiting_thumbnail", anilist_id=anilist_id)
    await cq.message.reply("Send the new thumbnail (as a photo or as a document/file for full quality).")
    await cq.answer()


@app.on_callback_query(filters.regex(r"^set_ep:(-?\d+)$"))
async def set_ep_cb(client, cq: CallbackQuery):
    anilist_id = int(cq.matches[0].group(1))
    state.set_state(cq.from_user.id, action="awaiting_episode", anilist_id=anilist_id)
    await cq.message.reply("Send the new last-uploaded episode number.")
    await cq.answer()


@app.on_callback_query(filters.regex(r"^set_season:(-?\d+)$"))
async def set_season_cb(client, cq: CallbackQuery):
    anilist_id = int(cq.matches[0].group(1))
    state.set_state(cq.from_user.id, action="awaiting_season", anilist_id=anilist_id)
    await cq.message.reply("Send the correct season number (e.g. 3).")
    await cq.answer()


@app.on_callback_query(filters.regex(r"^set_sub:(-?\d+)$"))
async def set_sub_cb(client, cq: CallbackQuery):
    anilist_id = int(cq.matches[0].group(1))
    state.set_state(cq.from_user.id, action="awaiting_sub_channel", anilist_id=anilist_id)
    await cq.message.reply("Send the new Telegram sub channel link.")
    await cq.answer()
