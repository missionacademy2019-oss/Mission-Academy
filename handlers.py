"""Message + callback routing for the Mission Academy bot, reloaded per update.

bot.py owns the API plumbing (call, show_menu, keyboards, menus/faqs loading)
and passes a ctx dict of callables. This module owns ALL behaviour so logic
changes take effect without restarting the bot.
"""
import html
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


# Group force-join: anyone JOINING one of the listed groups must join the
# assignment channel. New joiners ONLY — existing members are never touched
# (this event only fires for joins). The bot must be admin of the assignment
# channel (for the membership check) and admin with ban/restrict permission
# in each group (for the restrict calls).
# Fail-open philosophy, same as the PDF gate: a failed membership CHECK
# unrestricts (never trap a user because of a bot misconfiguration), and a
# failed restrict/unrestrict call is logged, never fatal. Restriction only
# works in groups/supergroups; if a listed entry turns out to be a channel,
# the restrict call fails and is logged (type verification happens at go-live).
ASSIGN_CHANNEL = "@ignouassignmentsofficial"
ASSIGN_CHANNEL_URL = "https://t.me/ignouassignmentsofficial"
ASSIGN_GROUPS_PATH = os.path.join(HERE, "force-join-assignment-channel-groups.txt")

# Bot-start requirement: a joiner must ALSO have started the bot itself.
# Telegram has no "bot membership" query, so the enforceable version is a
# starters set: any private message to the bot (pressing Start sends /start
# as a private message) records the sender's user ID. The file is the source
# of truth — read fresh on every record/check — so the set survives restarts
# with no startup load step. User IDs only, nothing else is stored.
BOT_USERNAME = "Shafeeque_rayaroth_bot"
BOT_URL = "https://t.me/Shafeeque_rayaroth_bot"
BOT_STARTERS_PATH = os.path.join(STATE_DIR, "bot_starters.json")


def _load_starters() -> list:
    """User IDs that have privately messaged the bot. A missing/corrupt
    file is treated as empty (and logged) — never raises."""
    try:
        with open(BOT_STARTERS_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return []
    except (OSError, json.JSONDecodeError) as e:
        print("bot starters: unreadable file, treating as empty:", e, flush=True)
        return []
    if not isinstance(data, list):
        print("bot starters: unexpected file shape, treating as empty", flush=True)
        return []
    return [u for u in data if isinstance(u, int)]


def record_bot_starter(user_id: int) -> bool:
    """Persist a private-messaging user ID. Returns True if newly added.
    Never raises."""
    try:
        starters = _load_starters()
        if user_id in starters:
            return False
        starters.append(user_id)
        with open(BOT_STARTERS_PATH, "w", encoding="utf-8") as f:
            json.dump(starters, f)
        return True
    except OSError as e:
        print("bot starters: record failed:", e, flush=True)
        return False


def is_bot_starter(user_id: int) -> bool:
    return user_id in _load_starters()

_GROUPS_CACHE: dict = {}

# Read-only: the restricted user can read but cannot send anything.
_READ_ONLY_PERMISSIONS = {
    "can_send_messages": False,
    "can_send_audios": False,
    "can_send_documents": False,
    "can_send_photos": False,
    "can_send_videos": False,
    "can_send_video_notes": False,
    "can_send_voice_notes": False,
    "can_send_polls": False,
    "can_send_other_messages": False,
    "can_add_web_page_previews": False,
    "can_change_info": False,
    "can_invite_users": False,
    "can_pin_messages": False,
    "can_manage_topics": False,
}

_FULL_PERMISSIONS = {k: True for k in _READ_ONLY_PERMISSIONS}


def load_assign_force_join_groups() -> set:
    """Group usernames (lowercased, no @) from the groups file, reloaded
    when the file changes. Comment lines (#) and blanks are skipped."""
    try:
        mtime = os.path.getmtime(ASSIGN_GROUPS_PATH)
    except OSError as e:
        print("assign force-join: groups file unreadable:", e, flush=True)
        return set()
    if _GROUPS_CACHE.get("mtime") != mtime:
        groups = set()
        try:
            with open(ASSIGN_GROUPS_PATH, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    groups.add(line.lstrip("@").lower())
        except OSError as e:
            print("assign force-join: groups file unreadable:", e, flush=True)
            return set()
        _GROUPS_CACHE["groups"] = groups
        _GROUPS_CACHE["mtime"] = mtime
    return _GROUPS_CACHE["groups"]


def _assignment_channel_status(ctx: dict, user_id: int) -> str:
    """"member" for member/administrator/creator/restricted, "left" for
    left/kicked/unknown, "error" when the check itself fails (exception or
    ok:false). Deliberately NOT cached: a Verify tap must reflect the
    just-completed join, not a stale negative result."""
    try:
        res = ctx["call"]("getChatMember", {
            "chat_id": ASSIGN_CHANNEL,
            "user_id": user_id,
        })
    except Exception as e:
        print("assign force-join: membership check error:", e, flush=True)
        return "error"
    if not isinstance(res, dict) or not res.get("ok"):
        print("assign force-join: membership check not ok:", res, flush=True)
        return "error"
    status = (res.get("result") or {}).get("status", "")
    if status in ("member", "administrator", "creator", "restricted"):
        return "member"
    return "left"


def _set_member_permissions(ctx: dict, chat_id: int, user_id: int, permissions: dict) -> bool:
    """restrictChatMember wrapper. Returns False (and logs) when the bot is
    not admin with restrict rights in the group — never raises."""
    try:
        ctx["call"]("restrictChatMember", {
            "chat_id": chat_id,
            "user_id": user_id,
            "permissions": permissions,
        })
        return True
    except Exception as e:
        print("assign force-join: restrictChatMember failed:", e, flush=True)
        return False


def _handle_new_members(msg: dict, ctx: dict) -> None:
    chat = msg.get("chat", {})
    username = (chat.get("username") or "").lower()
    if username not in load_assign_force_join_groups():
        return
    chat_id = chat.get("id")
    if chat_id is None:
        return
    bot_id = ctx.get("bot_id")
    for member in msg.get("new_chat_members", []):
        user_id = member.get("id")
        if user_id is None:
            continue
        if bot_id is not None and user_id == bot_id:
            continue  # ignore the bot's own joins
        _set_member_permissions(ctx, chat_id, user_id, _READ_ONLY_PERMISSIONS)
        mention = '<a href="tg://user?id=%d">%s</a>' % (
            user_id, html.escape(member.get("first_name") or "new member"))
        try:
            ctx["call"]("sendMessage", {
                "chat_id": chat_id,
                "text": ("👋 Welcome %s!\n\n"
                         "To chat in this group, please join our assignment "
                         "channel AND start our bot first.\n\n"
                         "Tap Join, then tap 🤖 Start the Bot, then tap "
                         "✅ I've joined — Verify." % mention),
                "parse_mode": "HTML",
                "reply_markup": {"inline_keyboard": [
                    [{"text": "📢 Join @ignouassignmentsofficial",
                      "url": ASSIGN_CHANNEL_URL}],
                    [{"text": "🤖 Start the Bot",
                      "url": BOT_URL}],
                    [{"text": "✅ I've joined — Verify",
                      "callback_data": "verify-assign:%d" % user_id}],
                ]},
            })
        except Exception as e:
            print("assign force-join: welcome message failed:", e, flush=True)


def _send_verify_confirmation(ctx: dict, cb: dict, chat_id: int) -> None:
    try:
        ctx["call"]("answerCallbackQuery", {
            "callback_query_id": cb["id"],
            "text": "✅ Verified! You can now send messages in this group.",
        })
    except Exception:
        pass
    try:
        ctx["call"]("sendMessage", {
            "chat_id": chat_id,
            "text": "✅ Verified! You can now send messages in this group.",
        })
    except Exception as e:
        print("assign force-join: verify confirmation failed:", e, flush=True)


def _handle_verify_callback(cb: dict, ctx: dict) -> None:
    """Verify BOTH conditions, in order: (1) assignment-channel membership,
    (2) bot started. Channel check error → fail-open unrestrict (same
    philosophy as the PDF gate). Channel left/kicked → stay restricted
    regardless of bot-start state. Channel OK but bot not started → stay
    restricted with a start-the-bot alert. Only both satisfied unrestricts."""
    try:
        user_id = int(cb.get("data", "").split(":", 1)[1])
    except (ValueError, IndexError):
        return
    chat = (cb.get("message") or {}).get("chat", {})
    username = (chat.get("username") or "").lower()
    if username not in load_assign_force_join_groups():
        return  # this button only operates in listed groups
    chat_id = chat.get("id")
    if chat_id is None:
        return
    status = _assignment_channel_status(ctx, user_id)
    if status == "error":
        # fail open: never trap a user because of a bot misconfiguration
        _set_member_permissions(ctx, chat_id, user_id, _FULL_PERMISSIONS)
        _send_verify_confirmation(ctx, cb, chat_id)
        return
    if status == "left":
        # left/kicked: they STAY restricted; tell them to join first.
        try:
            ctx["call"]("answerCallbackQuery", {
                "callback_query_id": cb["id"],
                "text": ("Please join @ignouassignmentsofficial first, "
                         "then tap Verify again."),
                "show_alert": True,
            })
        except Exception:
            pass
        return
    # Channel membership OK — now the bot-start condition.
    if not is_bot_starter(user_id):
        try:
            ctx["call"]("answerCallbackQuery", {
                "callback_query_id": cb["id"],
                "text": ("You're in the channel — one more step: start our "
                         "bot first. Open t.me/Shafeeque_rayaroth_bot and "
                         "tap Start, then tap Verify again."),
                "show_alert": True,
            })
        except Exception:
            pass
        return
    _set_member_permissions(ctx, chat_id, user_id, _FULL_PERMISSIONS)
    _send_verify_confirmation(ctx, cb, chat_id)


def handle_update(upd: dict, ctx: dict) -> None:
    menus = ctx["load_menus"]()
    msg = upd.get("message")
    # Group force-join: a new member in a listed group is restricted until
    # they join the assignment channel and tap Verify. Existing members are
    # never touched (this event only fires for joins).
    if msg and msg.get("new_chat_members"):
        _handle_new_members(msg, ctx)
        return
    # Bot-start recording: ANY private message counts as "started the bot"
    # (pressing Start sends /start as a private message). Group messages
    # never count. Wrapped so a file problem can never break message flow.
    if msg and msg.get("chat", {}).get("type") == "private":
        sender = msg.get("from") or {}
        if sender.get("id") is not None:
            try:
                record_bot_starter(sender["id"])
            except Exception as e:
                print("bot starters: record error:", e, flush=True)
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
    data = cb.get("data", "")
    # Group force-join verification: answered here with its own text, before
    # the generic spinner-clearing answer below.
    if data.startswith("verify-assign:"):
        _handle_verify_callback(cb, ctx)
        return
    # answer the callback FIRST so the button spinner clears immediately,
    # even if the menu edit is slow on a bad connection
    try:
        ctx["call"]("answerCallbackQuery", {"callback_query_id": cb["id"]})
    except Exception:
        pass
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
