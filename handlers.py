"""Message + callback routing for the Mission Academy bot, reloaded per update.

bot.py owns the API plumbing (call, show_menu, keyboards, menus/faqs loading)
and passes a ctx dict of callables. This module owns ALL behaviour so logic
changes take effect without restarting the bot.
"""
import json
import os
import re
import time
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
# FadeHost apps run on a read-only filesystem; writable state goes under /data
# when it exists (read-only data files stay next to the code).
STATE_DIR = "/data" if os.path.isdir("/data") and os.access("/data", os.W_OK) else HERE
FAQS_PATH = os.path.join(HERE, "faqs.json")
QUIZZES_PATH = os.path.join(HERE, "quizzes.json")
NOTES_PATH = os.path.join(HERE, "notes.json")
SUBSCRIBERS_PATH = os.path.join(STATE_DIR, "subscribers.json")
PENDING_PATH = os.path.join(STATE_DIR, "pending_files.json")
NOTES_FILES_PATH = os.path.join(STATE_DIR, "notes_files.json")

FALLBACK = (
    "Thanks for your message! 😊 I'm still learning, so I don't have an "
    "answer for that one yet. Our team will be happy to help you directly — "
    "message Mission Academy on WhatsApp: +91 86066 56245"
)

_FAQS_CACHE = {"mtime": None, "faqs": []}


def load_faqs() -> list:
    mtime = os.path.getmtime(FAQS_PATH)
    if _FAQS_CACHE["mtime"] != mtime:
        with open(FAQS_PATH, encoding="utf-8") as f:
            _FAQS_CACHE["faqs"] = json.load(f)
        _FAQS_CACHE["mtime"] = mtime
    return _FAQS_CACHE["faqs"]


def _words(text: str) -> set:
    return set(re.findall(r"[a-z0-9.]+", text.lower()))


def qa_answer(text: str) -> str | None:
    """Best keyword match from the knowledge base, or None if nothing matches."""
    msg_words = _words(text)
    lowered = text.lower()
    best, best_score = None, 0
    for entry in load_faqs():
        score = 0
        for kw in entry["keywords"]:
            kw = kw.lower()
            if " " in kw or "." in kw:
                if kw in lowered:
                    score += 2
            elif kw in msg_words:
                score += 1
        if score > best_score:
            best, best_score = entry, score
    return best["answer"] if best else None


def _load_json_cached(path: str, cache: dict):
    mtime = os.path.getmtime(path)
    if cache.get("mtime") != mtime:
        with open(path, encoding="utf-8") as f:
            cache["data"] = json.load(f)
        cache["mtime"] = mtime
    return cache["data"]


_QUIZ_CACHE: dict = {}
_NOTES_CACHE: dict = {}


def today_quiz() -> dict:
    quizzes = _load_json_cached(QUIZZES_PATH, _QUIZ_CACHE)
    return quizzes[date.today().toordinal() % len(quizzes)]


def today_notes() -> str:
    notes = _load_json_cached(NOTES_PATH, _NOTES_CACHE)
    return notes[date.today().toordinal() % len(notes)]


def subscribe(chat_id: int) -> bool:
    """Add chat_id to the Daily Study list. Returns True if newly added."""
    try:
        with open(SUBSCRIBERS_PATH, encoding="utf-8") as f:
            subs = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        subs = []
    if chat_id in subs:
        return False
    subs.append(chat_id)
    with open(SUBSCRIBERS_PATH, "w", encoding="utf-8") as f:
        json.dump(subs, f)
    return True


def _load_json_file(path: str):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_json_file(path: str, data) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)


# Force-join gate: Notes PDFs are served only to members of the Mission Academy
# channel. The bot must be an admin of the channel for the membership check
# to work; if the check itself fails, fail OPEN (serve the file) so no
# student is blocked by a misconfiguration.
FORCE_JOIN_CHANNEL = "@missionacademy_official"
FORCE_JOIN_URL = "https://t.me/missionacademy_official"

# Membership cache: avoid a getChatMember round-trip on every PDF.
# Positive (member) cached 1 hour; negative (left/kicked) cached 5 minutes
# so a user who just joined gets access quickly.
_MEMBER_CACHE: dict = {}
_MEMBER_TTL = 3600
_NONMEMBER_TTL = 300


def _is_channel_member(ctx: dict, user_id: int) -> bool:
    now = time.time()
    cached = _MEMBER_CACHE.get(user_id)
    if cached is not None:
        value, ts, ttl = cached
        if now - ts < ttl:
            return value
    try:
        res = ctx["call"]("getChatMember", {
            "chat_id": FORCE_JOIN_CHANNEL,
            "user_id": user_id,
        })
    except Exception:
        return True
    if not isinstance(res, dict) or not res.get("ok"):
        return True
    status = (res.get("result") or {}).get("status", "")
    member = status in ("member", "administrator", "creator", "restricted")
    ttl = _MEMBER_TTL if member else _NONMEMBER_TTL
    _MEMBER_CACHE[user_id] = (member, now, ttl)
    return member


def handle_update(upd: dict, ctx: dict) -> None:
    menus = ctx["load_menus"]()
    msg = upd.get("message")
    # Document (PDF) forwarded/sent to the bot in a private chat: queue it
    # for assignment. The sender then navigates to the right Notes page and
    # taps Notes to attach it there. Group documents are ignored — the bot
    # must not react to every file posted in a group.
    if msg and msg.get("document") and msg.get("chat", {}).get("type") == "private":
        doc = msg["document"]
        chat_id = msg["chat"]["id"]
        pending = _load_json_file(PENDING_PATH)
        queue = pending.setdefault(str(chat_id), [])
        queue.append({
            "file_id": doc["file_id"],
            "file_name": doc.get("file_name") or "notes.pdf",
            "ts": time.time(),
        })
        _save_json_file(PENDING_PATH, pending)
        ctx["call"]("sendMessage", {
            "chat_id": chat_id,
            "text": (f"Got {queue[-1]['file_name']} 📄\n\n"
                     "Now navigate to the Notes page where it belongs "
                     "(University → UG/PG → category → course → year/semester) "
                     "and tap Notes — I'll attach it there. "
                     "You can forward more files first; I'll attach them in order."),
            "reply_markup": ctx["main_keyboard"](),
            "protect_content": True,
        })
        return
    if msg and msg.get("text"):
        text = msg["text"].strip()
        if text.startswith("/start"):
            ctx["show_menu"](msg["chat"]["id"], None, "welcome", menus)
            return
        answer = qa_answer(text)
        ctx["call"]("sendMessage", {
            "chat_id": msg["chat"]["id"],
            "text": answer or FALLBACK,
            "reply_markup": ctx["main_keyboard"](),
            "protect_content": True,
            "link_preview_options": {"is_disabled": True},
        })
        return
    cb = upd.get("callback_query")
    if not cb:
        return
    # answer the callback FIRST so the button spinner clears immediately,
    # even if the menu edit is slow on a bad connection
    try:
        ctx["call"]("answerCallbackQuery", {"callback_query_id": cb["id"]})
    except Exception:
        pass
    data = cb.get("data", "")
    chat_id = cb["message"]["chat"]["id"]
    # Daily Study actions (buttons on the daily-study menu)
    if data == "menu:daily-quiz-take":
        q = today_quiz()
        ctx["call"]("sendPoll", {
            "chat_id": chat_id,
            "question": q["q"],
            "options": q["options"],
            "type": "quiz",
            "correct_option_id": q["answer"],
            "explanation": q["explanation"],
            "is_anonymous": False,
        })
        return
    if data == "menu:daily-notes":
        ctx["call"]("sendMessage", {
            "chat_id": chat_id,
            "text": "📚 Today's Notes\n\n" + today_notes(),
        })
        return
    if data == "menu:daily-subscribe":
        new = subscribe(chat_id)
        ctx["call"]("sendMessage", {
            "chat_id": chat_id,
            "text": ("✅ You're on the Daily Study list!"
                     if new else
                     "✅ You're already on the Daily Study list.")
                + "\n\nYou'll get one quiz + one notes card every morning.",
        })
        return
    if data.startswith("menu:"):
        key = data[len("menu:"):]
        if key.endswith("-notes"):
            chat_id = cb["message"]["chat"]["id"]
            pending = _load_json_file(PENDING_PATH)
            queue = pending.get(str(chat_id), [])
            # drop stale queued files (older than 1 hour)
            queue = [e for e in queue if time.time() - e.get("ts", 0) < 3600]
            if queue:
                # attach the oldest queued file to this Notes page
                entry = queue.pop(0)
                if queue:
                    pending[str(chat_id)] = queue
                else:
                    pending.pop(str(chat_id), None)
                _save_json_file(PENDING_PATH, pending)
                mapping = _load_json_file(NOTES_FILES_PATH)
                files = mapping.setdefault(key, [])
                if all(f.get("file_id") != entry["file_id"] for f in files):
                    files.append({"file_id": entry["file_id"],
                                  "file_name": entry["file_name"]})
                    _save_json_file(NOTES_FILES_PATH, mapping)
                note = (f"✅ Attached {entry['file_name']} to this Notes page.\n\n"
                        "Students tapping Notes here will now get this file.")
                if queue:
                    note += (f"\n\n{len(queue)} more file(s) waiting — navigate to "
                             "the next Notes page and tap Notes to attach the next one.")
                ctx["call"]("sendMessage", {"chat_id": chat_id, "text": note})
                ctx["show_menu"](chat_id, cb["message"]["message_id"], key, menus)
                return
            if str(chat_id) in pending:
                pending.pop(str(chat_id), None)
                _save_json_file(PENDING_PATH, pending)
            files = _load_json_file(NOTES_FILES_PATH).get(key, [])
            if files:
                if not _is_channel_member(ctx, chat_id):
                    ctx["call"]("sendMessage", {
                        "chat_id": chat_id,
                        "text": ("📢 To download this PDF, please join our "
                                 "Mission Academy channel first.\n\n"
                                 "Tap Join below, then come back and tap Notes again."),
                        "reply_markup": {"inline_keyboard": [[
                            {"text": "📢 Join Mission Academy Channel",
                             "url": FORCE_JOIN_URL}]]},
                    })
                    return
                for fl in files:
                    ctx["call"]("sendDocument", {
                        "chat_id": chat_id,
                        "document": fl["file_id"],
                        "caption": fl["file_name"],
                    })
                parent = key[: -len("-notes")]
                title = menus.get(key, {}).get("text", key).split("\n\n")[0]
                ctx["call"]("sendMessage", {
                    "chat_id": chat_id,
                    "text": title + "\n\n📄 Notes files above.",
                    "reply_markup": {"inline_keyboard": [[{"text": "⬅ Back",
                                                         "callback_data": "menu:" + parent}]]},
                })
                return
        ctx["show_menu"](cb["message"]["chat"]["id"],
                         cb["message"]["message_id"],
                         key, menus)
