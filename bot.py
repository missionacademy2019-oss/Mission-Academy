#!/usr/bin/env python3
"""Mission Academy Telegram bot — @Shafeeque_rayaroth_bot.

Polls the Bot API with long polling. Auth: --token-stdin reads one token
line from stdin (held in memory only), otherwise the stored custom.telegram
credential via the authd surrogate exchange.

Behaviour lives in handlers.py, reloaded when its file changes — so logic
changes take effect WITHOUT restarting the bot. Menus live in menus.json
(reloaded on change), the Q&A knowledge base in faqs.json.
"""
import importlib
import json
import os
import sys
import time
import urllib.request

# dynamic_credentials exists only on the Hatch host. On a plain VM (e.g. Oracle)
# the import fails, so fall back to plain json parsing. With --token-stdin the
# dc helpers are never called: api_url() uses the direct token URL and call()
# only needs read_json_response, which here is json.load.
try:
    sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
    import dynamic_credentials as dc
except ImportError:
    class _DcFallback:
        @staticmethod
        def read_json_response(resp):
            return json.load(resp)

        @staticmethod
        def url_with_surrogate_path_segment(url, *a, **k):
            raise RuntimeError("vault credential exchange unavailable outside Hatch host")

    dc = _DcFallback()

import handlers

CRED = "custom.telegram-shafeeque6"
HOSTS = ["api.telegram.org"]
BASE = "https://api.telegram.org/bot{}/"
POLL_TIMEOUT = 30
HERE = os.path.dirname(os.path.abspath(__file__))
# FadeHost apps run on a read-only filesystem; writable state goes under /data
# when it exists (the original bot folder stays untouched by this change).
STATE_DIR = "/data" if os.path.isdir("/data") and os.access("/data", os.W_OK) else HERE
MENUS_PATH = os.path.join(HERE, "menus.json")
HANDLERS_PATH = os.path.join(HERE, "handlers.py")

DIRECT_TOKEN = None  # set when run with --token-stdin (held in memory only)

_MENUS_CACHE = {"mtime": None, "menus": None}
_HANDLERS_MTIME = None


def load_menus() -> dict:
    mtime = os.path.getmtime(MENUS_PATH)
    if _MENUS_CACHE["mtime"] != mtime:
        with open(MENUS_PATH, encoding="utf-8") as f:
            _MENUS_CACHE["menus"] = json.load(f)
        _MENUS_CACHE["mtime"] = mtime
    return _MENUS_CACHE["menus"]


def api_url(method: str) -> str:
    if DIRECT_TOKEN:
        return BASE.format(DIRECT_TOKEN) + method
    return dc.url_with_surrogate_path_segment(BASE + method, CRED, allowed_hosts=HOSTS)


def call(method: str, payload: dict, timeout: int = 15) -> dict:
    # content protection: members cannot forward, save, or copy anything
    # the bot sends; screenshots/screen recording are blocked on mobile.
    # The bot itself (the sender) is unaffected.
    if method.startswith("send"):
        payload = {**payload, "protect_content": True}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(api_url(method), data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return dc.read_json_response(resp)


def build_keyboard(menu: dict) -> dict:
    rows = []
    for row in menu.get("buttons", []):
        rows.append([{"text": b["text"], "callback_data": "menu:" + b["to"]} for b in row])
    return {"inline_keyboard": rows}


def main_keyboard() -> dict:
    return build_keyboard(load_menus()["home"])


def show_menu(chat_id: int, message_id: int | None, key: str, menus: dict) -> None:
    menu = menus.get(key, menus["home"])
    payload = {
        "chat_id": chat_id,
        "text": menu["text"],
        "reply_markup": build_keyboard(menu),
        "link_preview_options": {"is_disabled": True},
    }
    if message_id is None:
        call("sendMessage", payload)
    else:
        payload["message_id"] = message_id
        call("editMessageText", payload)


def reload_handlers() -> None:
    global _HANDLERS_MTIME
    mtime = os.path.getmtime(HANDLERS_PATH)
    if _HANDLERS_MTIME != mtime:
        importlib.reload(handlers)
        _HANDLERS_MTIME = mtime


CTX = {
    "call": call,
    "show_menu": show_menu,
    "load_menus": load_menus,
    "main_keyboard": main_keyboard,
}


def main() -> int:
    # single-instance guard: if another bot process already holds the lock,
    # exit instead of running a duplicate that fights over updates
    import fcntl
    lock_f = open(os.path.join(STATE_DIR, "bot.lock"), "w")
    try:
        fcntl.flock(lock_f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("another bot instance is already running, exiting", flush=True)
        return 3
    me = call("getMe", {})
    print("bot:", me.get("result", {}).get("username"), flush=True)
    # handlers need the bot's own id to ignore its own group joins
    CTX["bot_id"] = me.get("result", {}).get("id")
    offset = 0
    while True:
        try:
            res = call("getUpdates", {
                "offset": offset, "timeout": POLL_TIMEOUT,
                "allowed_updates": ["message", "callback_query"],
            }, timeout=POLL_TIMEOUT + 5)
        except Exception as e:
            print("poll error:", e, flush=True)
            time.sleep(5)
            continue
        for upd in res.get("result", []):
            offset = upd["update_id"] + 1
            try:
                reload_handlers()
                handlers.handle_update(upd, CTX)
            except Exception as e:
                print("handle error:", e, flush=True)


if __name__ == "__main__":
    if "--token-stdin" in sys.argv:
        DIRECT_TOKEN = sys.stdin.readline().strip()
        if not DIRECT_TOKEN:
            print("no token on stdin", flush=True)
            sys.exit(2)
    elif os.environ.get("TELEGRAM_BOT_TOKEN"):
        # FadeHost (and most hosts) run the bot directly, not via the
        # Procfile's stdin pipe, so read the token from the environment
        # variable set on the app. This must come before any Telegram call:
        # without it api_url() falls back to the Hatch-only vault helper,
        # which raises RuntimeError outside the Hatch host and crash-loops.
        DIRECT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"].strip()
    sys.exit(main())
