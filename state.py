"""Simple in-memory per-user conversation state.

Not persisted across restarts by design — these are short-lived
prompts (e.g. "waiting for a new thumbnail"), not durable data.
"""

_user_state = {}


def set_state(user_id: int, **kwargs):
    _user_state[user_id] = kwargs


def get_state(user_id: int):
    return _user_state.get(user_id)


def clear_state(user_id: int):
    _user_state.pop(user_id, None)
