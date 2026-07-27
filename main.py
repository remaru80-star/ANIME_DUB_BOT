from pyrogram import filters, idle
from pyrogram.handlers import MessageHandler

import config
import database
from bot_instance import app

# Importing these registers their @app.on_message / @app.on_callback_query
# handlers onto the shared `app` Client instance.
import handlers.commands  # noqa: F401
import handlers.callbacks  # noqa: F401
import handlers.messages  # noqa: F401


async def _debug_log(client, message):
    print(f"[DEBUG] update from user_id={message.from_user.id if message.from_user else '?'} "
          f"chat_id={message.chat.id} text={message.text or message.caption}")


async def main():
    if config.DEBUG_LOG:
        # group=-1 runs before every other handler and doesn't stop
        # propagation, so this only ever adds a print line.
        app.add_handler(MessageHandler(_debug_log, filters.all), group=-1)
        print("DEBUG_LOG is on — every incoming update will be printed.")

    await database.ensure_indexes()
    await app.start()
    me = await app.get_me()
    print(f"AnimeDub admin bot is up as @{me.username} (id={me.id}).")
    await idle()
    await app.stop()


if __name__ == "__main__":
    # NOTE: bot_instance.py creates `app = Client(...)` at import time,
    # which binds it to whatever event loop was current at that
    # moment (app.loop). asyncio.run() creates a brand-new, separate
    # loop for main() — so awaits inside app.start()/idle() end up
    # attached to a *different* loop than the Client itself, which is
    # exactly the "attached to a different loop" crash.
    # Passing our coroutine into app.run() instead makes Pyrogram
    # execute it on app.loop itself, so everything shares one loop.
    app.run(main())
