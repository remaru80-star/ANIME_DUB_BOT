import math

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

import config


def _paginate(docs, page):
    per_page = config.PAGE_SIZE
    start = (page - 1) * per_page
    total_pages = max(1, math.ceil(len(docs) / per_page))
    return docs[start : start + per_page], total_pages


def batch_list_keyboard(docs: list, page: int, mode: str) -> InlineKeyboardMarkup:
    """mode is 'edit' or 'delete' — controls the callback_data prefix."""
    page_docs, total_pages = _paginate(docs, page)

    rows = []
    for doc in page_docs:
        rating = doc.get("mal_rating")
        rating_str = f"{rating:.1f}" if isinstance(rating, (int, float)) else "N/A"
        label = f"{doc.get('english_title', 'Untitled')} ⭐{rating_str}"
        rows.append([InlineKeyboardButton(label, callback_data=f"{mode}_batch:{doc['anilist_id']}")])

    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"{mode}_page:{page - 1}"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"{mode}_page:{page + 1}"))
    if nav_row:
        rows.append(nav_row)

    return InlineKeyboardMarkup(rows)


def batch_edit_menu(anilist_id: int) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("🖼 Update Thumbnail", callback_data=f"set_thumb:{anilist_id}")],
        [InlineKeyboardButton("📺 Update Last Uploaded Episode", callback_data=f"set_ep:{anilist_id}")],
        [InlineKeyboardButton("🔢 Update Season", callback_data=f"set_season:{anilist_id}")],
        [InlineKeyboardButton("🔗 Update Sub Channel", callback_data=f"set_sub:{anilist_id}")],
        [InlineKeyboardButton("⬅️ Back to list", callback_data="edit_page:1")],
    ]
    return InlineKeyboardMarkup(rows)


def search_toggle_keyboard(docs: list, page: int) -> InlineKeyboardMarkup:
    page_docs, total_pages = _paginate(docs, page)

    rows = []
    for doc in page_docs:
        status_icon = "🟢" if doc.get("searching") else "🔴"
        label = f"{status_icon} {doc.get('english_title', 'Untitled')}"
        rows.append([InlineKeyboardButton(label, callback_data=f"toggle_search:{doc['anilist_id']}")])

    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"search_page:{page - 1}"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"search_page:{page + 1}"))
    if nav_row:
        rows.append(nav_row)

    return InlineKeyboardMarkup(rows)
