"""Message + callback routing for the Mission Academy bot, reloaded per update.

bot.py owns the API plumbing (call, show_menu, keyboards, menus/faqs loading)
and passes a ctx dict of callables. This module owns ALL behaviour so logic
changes take effect without restarting the bot.
"""
import ast
import html
import json
import os
import re
import time
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
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
    """Add chat_id to the Daily Study list. Returns True if newly added.
    Kept for backward compatibility: a legacy subscribe creates an
    entry with no subject yet (generic quiz/notes until the student
    picks a subject through the subscription flow)."""
    subs = load_subscriptions()
    if str(chat_id) in subs:
        return False
    subs[str(chat_id)] = _blank_subscription()
    _save_subscriptions(subs)
    return True


def _blank_subscription() -> dict:
    return {"university": None, "programme": None, "subject_code": None,
            "subject_name": None, "subscribed_at": None, "simple": False}


def load_subscriptions() -> dict:
    """subscribers.json as chat_id -> subscription dict. Migrates the
    old list format (plain chat ids) in memory: each old id becomes an
    entry with no subject yet. A missing or broken file is {} — the
    caller never sees a list, and migration never rewrites the file
    on its own; the next subscribe/set does that."""
    try:
        with open(SUBSCRIBERS_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    if isinstance(data, list):
        return {str(cid): _blank_subscription() for cid in data}
    if isinstance(data, dict):
        out = {}
        for key, value in data.items():
            entry = _blank_subscription()
            if isinstance(value, dict):
                entry.update(value)
            out[str(key)] = entry
        return out
    return {}


def _save_subscriptions(subs: dict) -> None:
    with open(SUBSCRIBERS_PATH, "w", encoding="utf-8") as f:
        json.dump(subs, f)


def get_subscription(chat_id: int) -> dict | None:
    return load_subscriptions().get(str(chat_id))


def set_subscription(chat_id: int, university: str, programme: str,
                     code: str, name: str) -> dict:
    subs = load_subscriptions()
    entry = subs.get(str(chat_id), _blank_subscription())
    entry.update({"university": university, "programme": programme,
                  "subject_code": code, "subject_name": name,
                  "subscribed_at": int(time.time())})
    subs[str(chat_id)] = entry
    _save_subscriptions(subs)
    return entry


def unsubscribe(chat_id: int) -> bool:
    subs = load_subscriptions()
    if str(chat_id) not in subs:
        return False
    del subs[str(chat_id)]
    _save_subscriptions(subs)
    return True


def set_simple(chat_id: int, on: bool) -> None:
    subs = load_subscriptions()
    entry = subs.get(str(chat_id), _blank_subscription())
    entry["simple"] = bool(on)
    subs[str(chat_id)] = entry
    _save_subscriptions(subs)


def is_simple(chat_id: int) -> bool:
    entry = get_subscription(chat_id)
    return bool(entry and entry.get("simple"))


# ---------------------------------------------------------------------------
# Universal Phase 1: per-subject quizzes and simple notes (MAEG only).
# Content rules: general academic knowledge for the paper only — never
# IGNOU/SGOU fees, deadlines, exam dates, marks, or syllabus claims.
# Files are read-only data next to the code (same in the FadeHost pack).
QUIZZES_BY_SUBJECT_PATH = os.path.join(HERE, "quizzes_by_subject.json")
NOTES_BY_SUBJECT_PATH = os.path.join(HERE, "notes_by_subject.json")
DOUBTS_PATH = os.path.join(STATE_DIR, "doubts.json")
_SUBJECT_QUIZ_CACHE: dict = {}
_SUBJECT_NOTE_CACHE: dict = {}

MAEG_SUBJECTS = {
    "MEG-01": "British Poetry", "MEG-02": "British Drama",
    "MEG-03": "British Novel", "MEG-04": "Aspects of Language",
    "MEG-05": "Literary Theory and Criticism",
    "MEG-06": "American Literature",
    "MEG-07": "Indian English Literature",
    "MEG-08": "New Literatures in English",
    "MEG-09": "Australian Literature",
    "MEG-10": "English Studies in India",
    "MEG-11": "American Novel",
    "MEG-12": "A Survey Course in 20th Century Canadian Literature",
    "MEG-13": "Writing from the Margins",
    "MEG-14": "Contemporary Indian Literature in English Translation",
    "MEG-15": "Comparative Literature",
    "MEG-16": "Indian Folk Literature",
    "MEG-17": "American Drama", "MEG-18": "American Poetry",
    "MEG-19": "Australian Novel",
}


def load_subject_quizzes() -> dict:
    return _load_json_cached(QUIZZES_BY_SUBJECT_PATH, _SUBJECT_QUIZ_CACHE)


def load_subject_notes() -> dict:
    return _load_json_cached(NOTES_BY_SUBJECT_PATH, _SUBJECT_NOTE_CACHE)


def today_subject_quiz(code: str, on_date: date | None = None) -> dict | None:
    """Deterministic daily pick for one subject: date ordinal % count.
    No timer is ever attached to the poll — no time pressure."""
    items = load_subject_quizzes().get(code)
    if not items:
        return None
    day = on_date or date.today()
    return items[day.toordinal() % len(items)]


def today_subject_note(code: str) -> str | None:
    return load_subject_notes().get(code)


def _plain(text: str) -> str:
    """Simple-mode form: strip emojis and decorative symbols, collapse
    whitespace. Plain words carry all the information — never an image,
    an emoji, or audio alone."""
    cleaned = re.sub(r"[\U0001F000-\U0001FAFF\u2600-\u27BF\u2190-\u21FF\uFE0F\u200D]+",
                     "", text)
    cleaned = cleaned.replace("·", " ")
    return re.sub(r"[ \t]+", " ", cleaned).strip()


def _fmt(chat_id: int, text: str) -> str:
    return _plain(text) if is_simple(chat_id) else text


_HELP_TEXT = (
    "Help — type a command instead of tapping a button.\n"
    "/home — home menu\n"
    "/ignou — IGNOU courses\n"
    "/sgou — SGOU courses\n"
    "/dailystudy — Daily Study\n"
    "/quiz — take today's quiz\n"
    "/notes — read today's note\n"
    "/subscribe — choose a subject to subscribe\n"
    "/mysubscription — show your subscription\n"
    "/unsubscribe — stop Daily Study\n"
    "/ask — how to ask a question\n"
    "/calc 2 + 3 — calculate a sum\n"
    "/simple on — plain text only\n"
    "/simple off — normal text\n"
    "/help — this list"
)


def _send_quiz(ctx: dict, chat_id: int) -> None:
    """Today's quiz for the subscriber's subject, else the generic one.
    The poll has no timer. The explanation also arrives as plain text
    right after the poll, not only inside the poll."""
    sub = get_subscription(chat_id)
    code = sub.get("subject_code") if sub else None
    quiz = today_subject_quiz(code) if code else None
    if quiz is None:
        quiz = today_quiz()
        label = "Today's Quiz"
    else:
        label = f"Today's Quiz — {code}"
    try:
        ctx["call"]("sendPoll", {
            "chat_id": chat_id,
            "question": quiz["q"],
            "options": quiz["options"],
            "type": "quiz",
            "correct_option_id": quiz["answer"],
            "explanation": quiz["explanation"],
            "is_anonymous": False,
        })
    except Exception as e:
        print("universal: quiz poll failed:", e, flush=True)
        return
    answer_text = quiz["options"][quiz["answer"]] if 0 <= quiz["answer"] < len(quiz["options"]) else ""
    try:
        ctx["call"]("sendMessage", {
            "chat_id": chat_id,
            "text": _fmt(chat_id, f"{label}\nAnswer: {answer_text}\n{quiz['explanation']}"),
        })
    except Exception:
        pass


def _send_notes(ctx: dict, chat_id: int) -> None:
    sub = get_subscription(chat_id)
    code = sub.get("subject_code") if sub else None
    note = today_subject_note(code) if code else None
    if note is None:
        text = "Today's Notes\n\n" + today_notes()
    else:
        text = f"Today's Notes — {code}\n\n{note}"
    try:
        ctx["call"]("sendMessage", {"chat_id": chat_id, "text": _fmt(chat_id, text)})
    except Exception as e:
        print("universal: notes failed:", e, flush=True)


def _send_my_subscription(ctx: dict, chat_id: int) -> None:
    sub = get_subscription(chat_id)
    if sub and sub.get("subject_code"):
        text = _fmt(chat_id, (
            "✅ My Subscription\n"
            f"University: {sub.get('university')}\n"
            f"Course: {sub.get('programme')}\n"
            f"Subject: {sub['subject_code']} {sub.get('subject_name') or ''}\n"
            "You get one quiz and one note each day for this subject."))
        rows = [[{"text": "Unsubscribe", "callback_data": "menu:unsubscribe"}],
                [{"text": "Back", "callback_data": "menu:home"}]]
    else:
        text = _fmt(chat_id, "My Subscription\nYou have no subscription yet.\nChoose a subject to start Daily Study.")
        rows = [[{"text": "Subscribe to Daily Study", "callback_data": "menu:sub-choose-university"}],
                [{"text": "Back", "callback_data": "menu:home"}]]
    try:
        ctx["call"]("sendMessage", {"chat_id": chat_id, "text": text,
                                    "reply_markup": {"inline_keyboard": rows}})
    except Exception as e:
        print("universal: my-subscription failed:", e, flush=True)


def _do_subscribe(ctx: dict, chat_id: int, code: str) -> None:
    name = MAEG_SUBJECTS.get(code)
    if name is None:
        try:
            ctx["call"]("sendMessage", {
                "chat_id": chat_id,
                "text": "That subject is not ready yet. MAEG English subjects are ready now."})
        except Exception:
            pass
        return
    set_subscription(chat_id, "IGNOU", "MAEG", code, name)
    try:
        ctx["call"]("sendMessage", {
            "chat_id": chat_id,
            "text": _fmt(chat_id, (
                f"✅ You are subscribed to {code} — {name}.\n"
                "You will get one quiz and one note each day."))})
    except Exception:
        pass


def safe_calc(expr: str) -> tuple[float | None, str | None]:
    """Safe arithmetic only: + - * / % ** and parentheses, numbers only.
    Never eval(). Returns (value, error)."""
    expr = (expr or "").strip()
    if not expr:
        return None, "Type a sum after /calc. Example: /calc 2 + 3"
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError:
        return None, "That sum is not clear. Use numbers and + - * / % ** only."
    allowed = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant,
               ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.Pow,
               ast.USub, ast.UAdd)
    nodes = list(ast.walk(tree))
    if len(nodes) > 60:
        return None, "That sum is too long."
    for node in nodes:
        if not isinstance(node, allowed):
            return None, "That calculation is not allowed. Use numbers and + - * / % ** only."
        if isinstance(node, ast.Constant) and not isinstance(node.value, (int, float)):
            return None, "That calculation is not allowed. Use numbers and + - * / % ** only."
        if isinstance(node, ast.Constant) and isinstance(node.value, bool):
            return None, "That calculation is not allowed. Use numbers and + - * / % ** only."

    def _eval(node):
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.UnaryOp):
            val = _eval(node.operand)
            return -val if isinstance(node.op, ast.USub) else +val
        if isinstance(node, ast.BinOp):
            left, right = _eval(node.left), _eval(node.right)
            if isinstance(node.op, ast.Add):
                out = left + right
            elif isinstance(node.op, ast.Sub):
                out = left - right
            elif isinstance(node.op, ast.Mult):
                out = left * right
            elif isinstance(node.op, ast.Div):
                out = left / right
            elif isinstance(node.op, ast.Mod):
                out = left % right
            elif isinstance(node.op, ast.Pow):
                if abs(right) > 1000:
                    raise ValueError("too large")
                out = left ** right
            else:
                raise ValueError("not allowed")
            if isinstance(out, float) and abs(out) > 1e15:
                raise ValueError("too large")
            return out
        raise ValueError("not allowed")

    try:
        value = _eval(tree)
    except ZeroDivisionError:
        return None, "Cannot divide by zero."
    except (ValueError, OverflowError):
        return None, "That sum is too large or not allowed."
    if isinstance(value, float):
        value = round(value, 10)
        if value.is_integer():
            value = int(value)
    return value, None


def _load_doubts() -> list:
    try:
        with open(DOUBTS_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def _save_doubt(chat_id: int, question: str) -> None:
    doubts = _load_doubts()
    doubts.append({"chat_id": chat_id, "question": question[:1000],
                   "ts": int(time.time())})
    with open(DOUBTS_PATH, "w", encoding="utf-8") as f:
        json.dump(doubts, f)


def _handle_private_command(ctx: dict, chat_id: int, text: str, menus: dict) -> bool:
    """Typed command equivalents for every Phase 1 button action.
    Returns True when the text was a command."""
    parts = text.strip().split(None, 1)
    cmd = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""
    if cmd == "/home":
        ctx["show_menu"](chat_id, None, "home", menus)
    elif cmd == "/ignou":
        ctx["show_menu"](chat_id, None, "ignou", menus)
    elif cmd == "/sgou":
        ctx["show_menu"](chat_id, None, "sgou", menus)
    elif cmd in ("/dailystudy", "/daily"):
        ctx["show_menu"](chat_id, None, "daily-study", menus)
    elif cmd == "/ask":
        ctx["show_menu"](chat_id, None, "ask-question", menus)
    elif cmd == "/quiz":
        _send_quiz(ctx, chat_id)
    elif cmd == "/notes":
        _send_notes(ctx, chat_id)
    elif cmd == "/subscribe":
        ctx["show_menu"](chat_id, None, "sub-choose-university", menus)
    elif cmd == "/mysubscription":
        _send_my_subscription(ctx, chat_id)
    elif cmd == "/unsubscribe":
        if unsubscribe(chat_id):
            msg = "✅ You are unsubscribed from Daily Study."
        else:
            msg = "You have no subscription to stop."
        try:
            ctx["call"]("sendMessage", {"chat_id": chat_id, "text": _fmt(chat_id, msg)})
        except Exception:
            pass
    elif cmd == "/simple":
        if arg.strip().lower() == "on":
            set_simple(chat_id, True)
            msg = "Simple mode is on. Messages will be plain text only."
        elif arg.strip().lower() == "off":
            set_simple(chat_id, False)
            msg = "Simple mode is off. Normal messages are back."
        else:
            state = "on" if is_simple(chat_id) else "off"
            msg = f"Simple mode is {state}. Type /simple on or /simple off to change it."
        try:
            ctx["call"]("sendMessage", {"chat_id": chat_id, "text": msg})
        except Exception:
            pass
    elif cmd == "/calc":
        value, error = safe_calc(arg)
        reply = f"Answer: {value}" if error is None else error
        try:
            ctx["call"]("sendMessage", {"chat_id": chat_id, "text": reply})
        except Exception:
            pass
    elif cmd == "/help":
        try:
            ctx["call"]("sendMessage", {"chat_id": chat_id, "text": _HELP_TEXT})
        except Exception:
            pass
    else:
        return False
    return True


def _handle_private_free_text(ctx: dict, chat_id: int, text: str) -> None:
    """FAQ answers first, with one precision rule: a message naming a
    full subject code (e.g. MEG-01) gets that subject's note when the
    rest of the message has no FAQ answer of its own — otherwise the
    generic 'meg' FAQ keyword would shadow every specific code and the
    notes would be unreachable. A message like 'fee for MEG-01' still
    gets the fee FAQ answer. Otherwise save the doubt honestly — never
    invent an answer."""
    codes = re.findall(r"\b([A-Z]{2,7}-\d{2,3})\b", text.upper())
    stripped = re.sub(r"\b[A-Z]{2,7}-\d{2,3}\b", "", text, flags=re.IGNORECASE)
    for code in codes:
        note = today_subject_note(code)
        if note and qa_answer(stripped) is None:
            try:
                ctx["call"]("sendMessage", {
                    "chat_id": chat_id,
                    "text": _fmt(chat_id, f"Note for {code}\n\n{note}"),
                    "reply_markup": ctx["main_keyboard"](),
                    "protect_content": True,
                })
            except Exception:
                pass
            return
    answer = qa_answer(text)
    if answer:
        try:
            ctx["call"]("sendMessage", {
                "chat_id": chat_id, "text": _fmt(chat_id, answer),
                "reply_markup": ctx["main_keyboard"](),
                "protect_content": True,
                "link_preview_options": {"is_disabled": True},
            })
        except Exception:
            pass
        return
    try:
        _save_doubt(chat_id, text)
    except Exception as e:
        print("universal: doubt save failed:", e, flush=True)
    try:
        ctx["call"]("sendMessage", {
            "chat_id": chat_id,
            "text": ("Saved for the team.\n"
                     "We will get back to you.\n"
                     "WhatsApp: +91 86066 56245"),
            "reply_markup": ctx["main_keyboard"](),
            "protect_content": True,
        })
    except Exception:
        pass


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

# Private verification (27 Oct 2026): the verification step must be
# invisible to other group members. Telegram has NO "only this user sees
# this group message" feature — a message posted in a group is visible to
# everyone who can read the group. So the prompt is NEVER posted in the
# group at all: it is sent privately to the joiner instead. The joiner is
# restricted silently in the group; other members see nothing, not even a
# welcome prompt.
#
# Hard limit of that design, stated plainly: a bot cannot start a private
# chat with someone who has never pressed Start on the bot — the private
# send fails with a 403. Those joiners stay restricted with no prompt
# until they start the bot themselves (e.g. via its link in the channel
# or from another member), at which point the pending prompt below is
# delivered immediately on their first private message. Pending entries
# are the source of truth for verification, so they survive restarts.
PENDING_VERIFY_PATH = os.path.join(STATE_DIR, "pending_verify.json")


def _load_pending_verify() -> list:
    """Pending force-join verifications: dicts with user_id, group_id,
    group_username, group_title and prompt_sent. Missing/corrupt file is
    treated as empty — never raises."""
    try:
        with open(PENDING_VERIFY_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return []
    except (OSError, json.JSONDecodeError) as e:
        print("pending verify: unreadable file, treating as empty:", e, flush=True)
        return []
    if not isinstance(data, list):
        print("pending verify: unexpected file shape, treating as empty", flush=True)
        return []
    return [e for e in data
            if isinstance(e, dict) and isinstance(e.get("user_id"), int)
            and isinstance(e.get("group_id"), int)]


def _save_pending_verify(entries: list) -> None:
    try:
        with open(PENDING_VERIFY_PATH, "w", encoding="utf-8") as f:
            json.dump(entries, f)
    except OSError as e:
        print("pending verify: save failed:", e, flush=True)


def _add_pending_verify(user_id: int, group_id: int, group_username: str,
                        group_title: str) -> None:
    entries = _load_pending_verify()
    for e in entries:
        if e["user_id"] == user_id and e["group_id"] == group_id:
            return  # already pending; keep its prompt_sent flag
    entries.append({"user_id": user_id, "group_id": group_id,
                    "group_username": group_username,
                    "group_title": group_title, "prompt_sent": False})
    _save_pending_verify(entries)


def _remove_pending_verify(user_id: int, group_id: int) -> None:
    entries = [e for e in _load_pending_verify()
               if not (e["user_id"] == user_id and e["group_id"] == group_id)]
    _save_pending_verify(entries)


def _pending_for_user(user_id: int) -> list:
    return [e for e in _load_pending_verify() if e["user_id"] == user_id]


def _send_private_verify_prompt(ctx: dict, user_id: int, group_id: int,
                                group_username: str, group_title: str) -> bool:
    """Send the verification prompt privately to the joiner. Returns True
    on success. On failure (bot cannot initiate a private chat with this
    user) the pending entry is left with prompt_sent=False so it is
    delivered when the user starts the bot. Never raises."""
    title = html.escape(group_title or group_username or "the group")
    try:
        ctx["call"]("sendMessage", {
            "chat_id": user_id,
            "text": ("👋 You joined %s!\n\n"
                     "To send messages in that group, please join our "
                     "assignment channel first, then tap ✅ Verify here.\n\n"
                     "This step is private — other members of the group "
                     "cannot see it." % title),
            "parse_mode": "HTML",
            "reply_markup": {"inline_keyboard": [
                [{"text": "📢 Join @ignouassignmentsofficial",
                  "url": ASSIGN_CHANNEL_URL}],
                [{"text": "✅ I've joined — Verify",
                  "callback_data": "verify-assign:%d:%d" % (user_id, group_id)}],
            ]},
        })
    except Exception as e:
        print("assign force-join: private prompt failed:", e, flush=True)
        return False
    entries = _load_pending_verify()
    for e in entries:
        if e["user_id"] == user_id and e["group_id"] == group_id:
            e["prompt_sent"] = True
    _save_pending_verify(entries)
    return True


def _deliver_pending_prompts(ctx: dict, user_id: int, force: bool) -> None:
    """Deliver pending verification prompts on a private message. Entries
    whose prompt was never delivered go out once; a /start (force=True)
    re-delivers even a previously sent prompt, in case the user lost it."""
    for entry in _pending_for_user(user_id):
        if entry.get("prompt_sent") and not force:
            continue
        _send_private_verify_prompt(ctx, user_id, entry["group_id"],
                                    entry.get("group_username", ""),
                                    entry.get("group_title", ""))


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


# Assignments from the channel (27 Oct 2026): a bot cannot read old
# channel history via the Bot API, so Assignments buttons do NOT fetch
# from Telegram — they use assignment_index.json, built from the upload
# manifest (course code -> @ignouassignmentsofficial message_id, 2,269
# entries, 1,895 codes). The file is read-only data next to the code
# (same in the FadeHost pack); it is reloaded when it changes.
#
# Scope, stated plainly: this wires SUBJECT pages only — a page whose
# title carries one course code (e.g. "MEG-01 · British Poetry"), which
# today means the 19 MAEG subject hubs, and any future subject hub built
# the same way. Year/semester Assignments pages (e.g. BAEGH Sem 1) carry
# no single code in their title, so they keep their existing behaviour
# until the subject lists for those programmes are built — guessing which
# codes belong to a semester would invent a curriculum.
#
# Delivery: forward the channel message to the user (the bot is admin of
# the channel, so forwarding works). If forwarding fails, fall back to
# the channel link — never fail silently. Assignments are official IGNOU
# booklets from a public channel, so unlike user-forwarded Notes PDFs
# they are NOT gated on Mission Academy channel membership (the link
# itself is public, so a gate would only annoy, not protect).
ASSIGN_INDEX_PATH = os.path.join(HERE, "assignment_index.json")
_ASSIGN_INDEX_CACHE: dict = {}


def load_assignment_index() -> dict:
    """Course code -> list of channel entries. Supports both the slim
    bot file ({code: [entries]}) and the full index ({"by_course": ...}).
    A missing/unreadable file returns {} — callers fall back to the
    menu page. Never raises."""
    try:
        mtime = os.path.getmtime(ASSIGN_INDEX_PATH)
    except OSError as e:
        print("assign index: file unreadable:", e, flush=True)
        return {}
    if _ASSIGN_INDEX_CACHE.get("mtime") != mtime:
        try:
            with open(ASSIGN_INDEX_PATH, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            print("assign index: unreadable, treating as empty:", e, flush=True)
            return {}
        _ASSIGN_INDEX_CACHE["data"] = data.get("by_course", data) \
            if isinstance(data, dict) else {}
        _ASSIGN_INDEX_CACHE["mtime"] = mtime
    return _ASSIGN_INDEX_CACHE["data"]


def _assignment_code_for_page(key: str, menus: dict) -> str | None:
    """Course code from a subject page's title, e.g. 'MEG-01' from
    'MAEG — Year 1 — MEG-01 · British Poetry — Assignments'."""
    text = (menus.get(key, {}) or {}).get("text", "")
    m = re.search(r"\b([A-Z]{2,7}-\d{2,3})\b", text)
    return m.group(1) if m else None


def _pick_assignment_entry(entries: list, key: str) -> dict | None:
    """One entry to forward, or None when the user must choose. MAEG
    subject hubs prefer the MAEG entry (e.g. MEG-08 also has a MEG /
    PGDNLEG booklet). Any other multi-entry code goes to a choice list
    rather than silently picking the wrong programme's booklet."""
    if "maeg" in key.lower():
        for e in entries:
            programmes = [p.strip() for p in str(e.get("programme", "")).split(",")]
            if "MAEG" in programmes:
                return e
    if len(entries) == 1:
        return entries[0]
    return None


def _deliver_assignment(ctx: dict, chat_id: int, code: str, entry: dict,
                        parent: str | None) -> None:
    """Forward the channel booklet, falling back to its link, then a
    caption with session/programme and a Back button. Never raises."""
    forwarded = False
    try:
        ctx["call"]("forwardMessage", {
            "chat_id": chat_id,
            "from_chat_id": ASSIGN_CHANNEL,
            "message_id": entry["telegram_message_id"],
        })
        forwarded = True
    except Exception as e:
        print("assign forward failed:", e, flush=True)
    rows = []
    if not forwarded:
        rows.append([{"text": "📢 Open in @ignouassignmentsofficial",
                      "url": entry.get("channel_link", ASSIGN_CHANNEL_URL)}])
    if parent:
        rows.append([{"text": "⬅ Back", "callback_data": "menu:" + parent}])
    text = ("📄 %s — Assignment (%s)\nProgramme: %s\n\n"
            % (code, entry.get("session", ""), entry.get("programme", "")))
    text += "Booklet above." if forwarded else \
        "Forwarding failed — open the booklet in the channel above."
    try:
        ctx["call"]("sendMessage", {
            "chat_id": chat_id,
            "text": text,
            "reply_markup": {"inline_keyboard": rows} if rows else None,
        })
    except Exception as e:
        print("assign caption failed:", e, flush=True)


def _handle_assignments_page(cb: dict, ctx: dict, menus: dict, key: str) -> bool:
    """Intercept a '*-assignments' menu tap. Returns True when handled
    (booklet forwarded, choice list sent, or an honest no-booklet
    message), False when the page carries no course code — the caller
    then falls through to the ordinary menu page."""
    chat_id = cb["message"]["chat"]["id"]
    code = _assignment_code_for_page(key, menus)
    if code is None:
        return False
    parent = key[: -len("-assignments")]
    entries = load_assignment_index().get(code)
    if not entries:
        try:
            ctx["call"]("sendMessage", {
                "chat_id": chat_id,
                "text": ("📄 %s — Assignments\n\n"
                         "No current assignment booklet for %s was found "
                         "in @ignouassignmentsofficial yet." % (code, code)),
                "reply_markup": {"inline_keyboard": [[
                    {"text": "⬅ Back", "callback_data": "menu:" + parent}]]},
            })
        except Exception:
            pass
        return True
    picked = _pick_assignment_entry(entries, key)
    if picked is not None:
        _deliver_assignment(ctx, chat_id, code, picked, parent)
        return True
    # Several programmes share this code and none is preferred: let the
    # student choose, rather than forwarding the wrong programme's paper.
    rows = []
    for e in entries:
        label = "%s — %s" % (e.get("programme", ""), e.get("session", ""))
        data = "assign-get:%d" % e["telegram_message_id"]
        if parent and len(data) + 1 + len(parent) <= 64:
            data += ":" + parent
        rows.append([{"text": label, "callback_data": data}])
    rows.append([{"text": "⬅ Back", "callback_data": "menu:" + parent}])
    try:
        ctx["call"]("sendMessage", {
            "chat_id": chat_id,
            "text": ("📄 %s — Assignments\n\n"
                     "This paper has booklets under more than one "
                     "programme. Choose yours:" % code),
            "reply_markup": {"inline_keyboard": rows},
        })
    except Exception:
        pass
    return True


def _handle_assign_get(cb: dict, ctx: dict, menus: dict) -> None:
    """Forward a chosen multi-programme booklet (assign-get callback).
    The code is recovered from the parent hub's title when present."""
    try:
        ctx["call"]("answerCallbackQuery", {"callback_query_id": cb["id"]})
    except Exception:
        pass
    parts = cb.get("data", "").split(":")
    try:
        message_id = int(parts[1])
    except (ValueError, IndexError):
        return
    parent = parts[2] if len(parts) >= 3 else None
    code = None
    if parent:
        code = _assignment_code_for_page(parent + "-assignments", menus)
    index = load_assignment_index()
    entry = None
    for entries in index.values():
        for e in entries:
            if e.get("telegram_message_id") == message_id:
                entry = e
                break
        if entry is not None:
            break
    if entry is None:
        return
    chat_id = cb["message"]["chat"]["id"]
    _deliver_assignment(ctx, chat_id, code or "Assignment", entry, parent)


def _handle_new_members(msg: dict, ctx: dict) -> None:
    """Restrict a new joiner silently and verify privately. NOTHING is
    posted in the group — no welcome prompt, no buttons — so other
    members never see the verification step. The prompt goes to the
    joiner's private chat; if that send fails (user never started the
    bot), the pending entry remains and the prompt is delivered when
    they start the bot (see _deliver_pending_prompts)."""
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
        _add_pending_verify(user_id, chat_id, username,
                            chat.get("title") or "")
        sent = _send_private_verify_prompt(ctx, user_id, chat_id, username,
                                           chat.get("title") or "")
        if not sent:
            print("assign force-join: private prompt undelivered, pending "
                  "until user starts the bot:", user_id, flush=True)


def _delete_prompt_message(ctx: dict, cb: dict, chat_id: int) -> None:
    """Delete the force-join prompt message from the group, immediately
    after a successful verification, so the group is left clean. Only
    called on success — on a failed Verify the prompt must stay, so the
    user can tap Verify again. A missing message_id or a failed delete
    (e.g. bot lacks the 'Delete messages' admin permission) is logged,
    never fatal, and never blocks the unrestrict."""
    message_id = (cb.get("message") or {}).get("message_id")
    if message_id is None:
        return
    try:
        ctx["call"]("deleteMessage", {
            "chat_id": chat_id,
            "message_id": message_id,
        })
    except Exception as e:
        print("assign force-join: delete prompt failed:", e, flush=True)


def _send_verify_confirmation(ctx: dict, cb: dict, chat_id: int) -> None:
    # Callback toast only — no new "Verified!" message is posted to the
    # group, so that after the prompt is deleted the group stays clean.
    try:
        ctx["call"]("answerCallbackQuery", {
            "callback_query_id": cb["id"],
            "text": "✅ Verified! You can now send messages in this group.",
        })
    except Exception:
        pass


def _handle_verify_callback(cb: dict, ctx: dict) -> None:
    """Verify BOTH conditions, in order: (1) assignment-channel membership,
    (2) bot started. Channel check error → fail-open unrestrict (same
    philosophy as the PDF gate). Channel left/kicked → stay restricted
    regardless of bot-start state. Channel OK but bot not started → stay
    restricted with a start-the-bot alert. Only both satisfied unrestricts.

    Two callback shapes:
    - New private shape "verify-assign:<user_id>:<group_id>": the button
      lives in the joiner's private chat. The group to unrestrict is the
      group_id, the prompt to delete is the private message, and tapping
      Verify in a private chat itself proves the bot-start condition, so
      the starter is recorded here. Only the joiner may tap it.
    - Legacy group shape "verify-assign:<user_id>": buttons posted in a
      group by the pre-private code (still live in groups until the next
      redeploy). Same checks, with the group taken from the message chat.
      The joiner-only tap rule applies here too — previously any member
      could tap Verify on a joiner's behalf."""
    parts = cb.get("data", "").split(":")
    try:
        user_id = int(parts[1])
    except (ValueError, IndexError):
        return
    # Only the joiner may use their own verification button.
    if (cb.get("from") or {}).get("id") != user_id:
        try:
            ctx["call"]("answerCallbackQuery", {
                "callback_query_id": cb["id"],
                "text": "This verification is only for the new member.",
                "show_alert": True,
            })
        except Exception:
            pass
        return
    if len(parts) >= 3:
        # Private verification.
        try:
            chat_id = int(parts[2])
        except ValueError:
            return
        pending = [e for e in _pending_for_user(user_id)
                   if e["group_id"] == chat_id]
        if not pending:
            try:
                ctx["call"]("answerCallbackQuery", {
                    "callback_query_id": cb["id"],
                    "text": "This verification is no longer pending.",
                    "show_alert": True,
                })
            except Exception:
                pass
            return
        if pending[0].get("group_username", "").lower() \
                not in load_assign_force_join_groups():
            return  # group no longer in the listed set
        prompt_chat_id = (cb.get("message") or {}).get("chat", {}).get("id")
        # Tapping Verify in a private chat proves the bot-start condition.
        record_bot_starter(user_id)
        starter_ok = True
    else:
        # Legacy group verification.
        chat = (cb.get("message") or {}).get("chat", {})
        username = (chat.get("username") or "").lower()
        if username not in load_assign_force_join_groups():
            return  # this button only operates in listed groups
        chat_id = chat.get("id")
        if chat_id is None:
            return
        prompt_chat_id = chat_id
        starter_ok = is_bot_starter(user_id)
    status = _assignment_channel_status(ctx, user_id)
    if status == "error":
        # fail open: never trap a user because of a bot misconfiguration
        _set_member_permissions(ctx, chat_id, user_id, _FULL_PERMISSIONS)
        _delete_prompt_message(ctx, cb, prompt_chat_id)
        if len(parts) >= 3:
            _remove_pending_verify(user_id, chat_id)
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
    if not starter_ok:
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
    _delete_prompt_message(ctx, cb, prompt_chat_id)
    if len(parts) >= 3:
        _remove_pending_verify(user_id, chat_id)
    _send_verify_confirmation(ctx, cb, chat_id)


# ---------------------------------------------------------------------------
# Rose-style group management (27 Oct 2026, "All Rose-style features").
#
# This is your bot acting as the group manager, in the groups where it is
# admin — it does NOT replace the private study menus, which keep working
# exactly as before. Group text never falls through to the private Q&A
# fallback: unknown group commands get a short /rosehelp hint, ordinary
# messages are checked against locks/blocklist/flood and otherwise ignored.
#
# Covered (Rose's core, per missrose.org docs): welcome/goodbye,
# rules, warns (limit + mode), ban/unban/tban, mute/unmute/tmute, kick,
# pin/unpin, antiflood, locks, blocklist, notes (#name + /get), clean
# service messages, and federation-style bans across YOUR OWN tracked
# groups (/fban — the bot only knows groups it has seen a message in).
#
# NOT in v1, stated plainly: (1) captcha — a button-captcha restriction
# would fight the force-join restriction in the same groups (two systems
# both muting and unmuting the same joiner); use one or the other per
# group, and captcha can be added later for non-force-join groups.
# (2) import/export, language settings, analytics/dashboard, and the
# /report-to-admins DM flow (admins who never started the bot cannot be
# DM'd) — none of those change what a member sees in the group.
#
# Privacy-mode caveat (Bot API, not a bug): with BotFather Group Privacy
# ON, the bot only sees commands and replies, so antiflood, locks and
# blocklist cannot see ordinary messages. For full moderation, turn
# Group Privacy OFF in @BotFather (Bot Settings -> Group Privacy).
# Commands work either way.
#
# State files (same pattern as the other bot state: HERE in main, /data
# in the FadeHost pack — the pack copy must patch these paths to
# STATE_DIR, as it does for subscribers/pending/notes/starters/verify):
#   group_settings.json — per-group config (welcome, rules, warn limit
#       and mode, flood, locks, blocklist, cleanservice)
#   group_warns.json    — per-group, per-user warn counts and reasons
#   group_notes.json    — per-group saved notes
#   group_tracked.json  — groups the bot has seen (for /fban)
# Flood timestamps live in memory only; a restart clears them.
GROUP_SETTINGS_PATH = os.path.join(STATE_DIR, "group_settings.json")
GROUP_WARNS_PATH = os.path.join(STATE_DIR, "group_warns.json")
GROUP_NOTES_PATH = os.path.join(STATE_DIR, "group_notes.json")
GROUP_TRACKED_PATH = os.path.join(STATE_DIR, "group_tracked.json")
_FLOOD_TRACKER: dict = {}

_GROUP_DEFAULTS = {
    "welcome_on": False, "welcome": "",
    "goodbye_on": False, "goodbye": "",
    "rules": "",
    "warn_limit": 3, "warn_mode": "ban",
    "flood_limit": 0, "flood_window": 10, "flood_mode": "mute",
    "locks": [], "blocklist": [], "cleanservice": False,
}


def _group_settings(group_id: int) -> dict:
    all_settings = _load_json_file(GROUP_SETTINGS_PATH)
    merged = dict(_GROUP_DEFAULTS)
    merged.update(all_settings.get(str(group_id), {}) or {})
    return merged


def _save_group_settings(group_id: int, settings: dict) -> None:
    all_settings = _load_json_file(GROUP_SETTINGS_PATH)
    all_settings[str(group_id)] = settings
    _save_json_file(GROUP_SETTINGS_PATH, all_settings)


def _track_group(chat: dict) -> None:
    chat_id = chat.get("id")
    if chat_id is None:
        return
    tracked = _load_json_file(GROUP_TRACKED_PATH)
    key = str(chat_id)
    entry = {"title": chat.get("title") or "", "username": chat.get("username") or ""}
    if tracked.get(key) != entry:
        tracked[key] = entry
        _save_json_file(GROUP_TRACKED_PATH, tracked)


def _is_group_admin(ctx: dict, chat_id: int, user_id: int, default: bool = False) -> bool:
    """Fresh getChatMember check. Commands fail CLOSED (default False);
    message filters fail OPEN (default True) so a failed check never
    deletes an admin's message by mistake."""
    try:
        res = ctx["call"]("getChatMember", {"chat_id": chat_id, "user_id": user_id})
    except Exception as e:
        print("rose: admin check failed:", e, flush=True)
        return default
    if not isinstance(res, dict) or not res.get("ok"):
        return default
    return (res.get("result") or {}).get("status") in ("administrator", "creator")


def _send_group(ctx: dict, chat_id: int, text: str, reply_to: int | None = None) -> None:
    payload = {"chat_id": chat_id, "text": text}
    if reply_to is not None:
        payload["reply_to_message_id"] = reply_to
    try:
        ctx["call"]("sendMessage", payload)
    except Exception as e:
        print("rose: send failed:", e, flush=True)


def _delete_msg(ctx: dict, chat_id: int, message_id: int) -> None:
    try:
        ctx["call"]("deleteMessage", {"chat_id": chat_id, "message_id": message_id})
    except Exception:
        pass


def _parse_duration(raw: str) -> int | None:
    """'10m'/'2h'/'3d'/'1w' -> seconds; plain digits -> seconds. None if bad."""
    raw = (raw or "").strip().lower()
    if raw.isdigit():
        return int(raw)
    m = re.fullmatch(r"(\d+)([mhdw])", raw)
    if not m:
        return None
    return int(m.group(1)) * {"m": 60, "h": 3600, "d": 86400, "w": 604800}[m.group(2)]


def _restrict(ctx: dict, chat_id: int, user_id: int, until: int | None = None,
              muted: bool = True) -> bool:
    payload = {"chat_id": chat_id, "user_id": user_id,
               "permissions": _READ_ONLY_PERMISSIONS if muted else _FULL_PERMISSIONS}
    if until is not None:
        payload["until_date"] = until
    try:
        ctx["call"]("restrictChatMember", payload)
        return True
    except Exception as e:
        print("rose: restrict failed:", e, flush=True)
        return False


def _ban(ctx: dict, chat_id: int, user_id: int, until: int | None = None) -> bool:
    payload = {"chat_id": chat_id, "user_id": user_id}
    if until is not None:
        payload["until_date"] = until
    try:
        ctx["call"]("banChatMember", payload)
        return True
    except Exception as e:
        print("rose: ban failed:", e, flush=True)
        return False


def _unban(ctx: dict, chat_id: int, user_id: int) -> bool:
    try:
        ctx["call"]("unbanChatMember", {"chat_id": chat_id, "user_id": user_id})
        return True
    except Exception as e:
        print("rose: unban failed:", e, flush=True)
        return False


def _target_user(msg: dict, args: list) -> tuple[int | None, str]:
    """Target for an admin action: reply first (Rose-style), else a
    numeric user id argument. Username lookup is NOT offered — the Bot
    API cannot reliably resolve a @username to a member id."""
    reply = msg.get("reply_to_message") or {}
    sender = reply.get("from") or {}
    if sender.get("id") is not None:
        return sender["id"], sender.get("first_name") or str(sender["id"])
    if args and args[0].isdigit():
        return int(args[0]), args[0]
    return None, ""


def _apply_punishment(ctx: dict, chat_id: int, user_id: int, mode: str,
                      extra: str | None = None) -> str:
    """Apply a warn/flood mode string. Returns a short description."""
    now = int(time.time())
    if mode == "ban":
        return "banned" if _ban(ctx, chat_id, user_id) else "ban failed (is the bot admin?)"
    if mode == "kick":
        if _ban(ctx, chat_id, user_id):
            _unban(ctx, chat_id, user_id)
            return "kicked"
        return "kick failed (is the bot admin?)"
    if mode == "mute":
        return "muted" if _restrict(ctx, chat_id, user_id) else "mute failed (is the bot admin?)"
    if mode == "tban":
        secs = _parse_duration(extra) if extra else None
        if secs is None:
            return "tban needs a duration (e.g. tban 1h)"
        return "temporarily banned" if _ban(ctx, chat_id, user_id, now + secs) else "tban failed"
    if mode == "tmute":
        secs = _parse_duration(extra) if extra else None
        if secs is None:
            return "tmute needs a duration (e.g. tmute 10m)"
        return "temporarily muted" if _restrict(ctx, chat_id, user_id, now + secs) else "tmute failed"
    return "unknown mode: " + mode


def _apply_warn(ctx: dict, chat_id: int, user_id: int, name: str,
                reason: str, settings: dict) -> None:
    warns = _load_json_file(GROUP_WARNS_PATH)
    group_warns = warns.setdefault(str(chat_id), {})
    entry = group_warns.setdefault(str(user_id), {"count": 0, "reasons": []})
    entry["count"] += 1
    if reason:
        entry["reasons"].append(reason)
    limit = int(settings.get("warn_limit", 3))
    if entry["count"] >= limit:
        mode = str(settings.get("warn_mode", "ban"))
        extra = None
        parts = mode.split(None, 1)
        if len(parts) == 2:
            mode, extra = parts
        result = _apply_punishment(ctx, chat_id, user_id, mode, extra)
        group_warns[str(user_id)] = {"count": 0, "reasons": []}
        _save_json_file(GROUP_WARNS_PATH, warns)
        _send_group(ctx, chat_id,
                    f"⚠️ {name} reached {limit} warnings and was {result}.")
    else:
        _save_json_file(GROUP_WARNS_PATH, warns)
        _send_group(ctx, chat_id,
                    f"⚠️ {name} warned ({entry['count']}/{limit})."
                    + (f" Reason: {reason}" if reason else ""))


_ROSE_HELP = (
    "🌹 Group management commands (admins only, unless noted):\n"
    "/rules — show the rules (anyone)\n"
    "/setrules <text> — set the rules · /resetrules\n"
    "/welcome on|off · /setwelcome <text> ({name}, {group} work)\n"
    "/goodbye on|off · /setgoodbye <text>\n"
    "/warn <reason> (reply) · /warns (reply) · /resetwarns (reply)\n"
    "/setwarnlimit <n> · /setwarnmode ban|mute|kick|tban <dur>|tmute <dur>\n"
    "/ban · /unban · /tban <dur> · /mute · /unmute · /tmute <dur> · /kick (reply)\n"
    "/fban · /unfban (reply — all your tracked groups)\n"
    "/pin · /unpin (reply)\n"
    "/setflood <n> <seconds> · /setfloodmode <mode> · /setflood off\n"
    "/lock links|photo|video|document|sticker|animation|forward · /unlock <type> · /locks\n"
    "/addblocklist <word> · /unblocklist <word> · /blocklist · /clearblocklist\n"
    "/save <name> <text> · /get <name> · /notes · /clear <name> · #<name> sends a note\n"
    "/cleanservice on|off\n"
    "Durations: 10m, 2h, 3d, 1w. Punishments act on the replied-to message."
)


def _handle_group_command(ctx: dict, msg: dict, cmd: str, args: list) -> bool:
    """Handle one group command. Returns True always (the caller must
    not fall through to private Q&A for any group message)."""
    chat = msg.get("chat", {})
    chat_id = chat.get("id")
    sender = msg.get("from") or {}
    user_id = sender.get("id")
    if chat_id is None or user_id is None:
        return True
    _track_group(chat)
    settings = _group_settings(chat_id)
    admin_only = cmd not in ("rules", "rosehelp", "warns", "notes", "get")
    if admin_only and not _is_group_admin(ctx, chat_id, user_id, default=False):
        _send_group(ctx, chat_id, "Only group admins can use that command.",
                    reply_to=msg.get("message_id"))
        return True
    reply_id = msg.get("message_id")

    if cmd == "rosehelp":
        _send_group(ctx, chat_id, _ROSE_HELP)
    elif cmd == "rules":
        _send_group(ctx, chat_id, settings.get("rules") or "No rules have been set for this group yet.")
    elif cmd == "setrules":
        settings["rules"] = " ".join(args)
        _save_group_settings(chat_id, settings)
        _send_group(ctx, chat_id, "✅ Rules updated.")
    elif cmd == "resetrules":
        settings["rules"] = ""
        _save_group_settings(chat_id, settings)
        _send_group(ctx, chat_id, "✅ Rules cleared.")
    elif cmd in ("welcome", "goodbye"):
        if args and args[0].lower() in ("on", "off"):
            settings[cmd + "_on"] = args[0].lower() == "on"
            _save_group_settings(chat_id, settings)
            _send_group(ctx, chat_id, f"✅ {cmd} {'enabled' if settings[cmd + '_on'] else 'disabled'}.")
        else:
            _send_group(ctx, chat_id, f"Usage: /{cmd} on  or  /{cmd} off")
    elif cmd in ("setwelcome", "setgoodbye"):
        key = "welcome" if cmd == "setwelcome" else "goodbye"
        settings[key] = " ".join(args)
        settings[key + "_on"] = True
        _save_group_settings(chat_id, settings)
        _send_group(ctx, chat_id, f"✅ {key} message saved and enabled.")
    elif cmd == "cleanservice":
        if args and args[0].lower() in ("on", "off"):
            settings["cleanservice"] = args[0].lower() == "on"
            _save_group_settings(chat_id, settings)
            _send_group(ctx, chat_id, f"✅ Clean service messages {'enabled' if settings['cleanservice'] else 'disabled'}.")
        else:
            _send_group(ctx, chat_id, "Usage: /cleanservice on  or  /cleanservice off")
    elif cmd == "warn":
        target, name = _target_user(msg, args)
        if target is None:
            _send_group(ctx, chat_id, "Reply to a message to warn that member.", reply_to=reply_id)
        else:
            _apply_warn(ctx, chat_id, target, name, " ".join(args), settings)
    elif cmd == "warns":
        target, name = _target_user(msg, args)
        if target is None:
            target, name = user_id, sender.get("first_name") or "You"
        entry = _load_json_file(GROUP_WARNS_PATH).get(str(chat_id), {}).get(str(target), {})
        _send_group(ctx, chat_id, f"⚠️ {name} has {entry.get('count', 0)} warning(s).")
    elif cmd == "resetwarns":
        target, name = _target_user(msg, args)
        if target is None:
            _send_group(ctx, chat_id, "Reply to a message to reset that member's warnings.", reply_to=reply_id)
        else:
            warns = _load_json_file(GROUP_WARNS_PATH)
            warns.setdefault(str(chat_id), {}).pop(str(target), None)
            _save_json_file(GROUP_WARNS_PATH, warns)
            _send_group(ctx, chat_id, f"✅ Warnings cleared for {name}.")
    elif cmd == "setwarnlimit":
        if args and args[0].isdigit() and int(args[0]) > 0:
            settings["warn_limit"] = int(args[0])
            _save_group_settings(chat_id, settings)
            _send_group(ctx, chat_id, f"✅ Warn limit set to {args[0]}.")
        else:
            _send_group(ctx, chat_id, "Usage: /setwarnlimit <number>")
    elif cmd == "setwarnmode":
        if args and args[0] in ("ban", "mute", "kick", "tban", "tmute"):
            settings["warn_mode"] = " ".join(args)
            _save_group_settings(chat_id, settings)
            _send_group(ctx, chat_id, f"✅ Warn mode set to {' '.join(args)}.")
        else:
            _send_group(ctx, chat_id, "Usage: /setwarnmode ban|mute|kick|tban <dur>|tmute <dur>")
    elif cmd in ("ban", "unban", "mute", "unmute", "kick"):
        target, name = _target_user(msg, args)
        if target is None:
            _send_group(ctx, chat_id, "Reply to a message to act on that member.", reply_to=reply_id)
        elif cmd == "ban":
            _send_group(ctx, chat_id, f"🚫 {name} banned." if _ban(ctx, chat_id, target) else "Ban failed — is the bot admin?")
        elif cmd == "unban":
            _send_group(ctx, chat_id, f"✅ {name} unbanned." if _unban(ctx, chat_id, target) else "Unban failed.")
        elif cmd == "mute":
            _send_group(ctx, chat_id, f"🔇 {name} muted." if _restrict(ctx, chat_id, target) else "Mute failed — is the bot admin?")
        elif cmd == "unmute":
            _send_group(ctx, chat_id, f"🔊 {name} unmuted." if _restrict(ctx, chat_id, target, muted=False) else "Unmute failed.")
        elif cmd == "kick":
            if _ban(ctx, chat_id, target):
                _unban(ctx, chat_id, target)
                _send_group(ctx, chat_id, f"👢 {name} kicked.")
            else:
                _send_group(ctx, chat_id, "Kick failed — is the bot admin?")
    elif cmd in ("tban", "tmute"):
        target, name = _target_user(msg, args)
        secs = _parse_duration(args[0]) if args else None
        if target is None:
            _send_group(ctx, chat_id, "Reply to a message to act on that member.", reply_to=reply_id)
        elif secs is None:
            _send_group(ctx, chat_id, f"Usage: /{cmd} <duration> (reply) — e.g. /{cmd} 1h")
        elif cmd == "tban":
            _send_group(ctx, chat_id, f"🚫 {name} banned for {args[0]}." if _ban(ctx, chat_id, target, int(time.time()) + secs) else "Tban failed.")
        else:
            _send_group(ctx, chat_id, f"🔇 {name} muted for {args[0]}." if _restrict(ctx, chat_id, target, int(time.time()) + secs) else "Tmute failed.")
    elif cmd in ("fban", "unfban"):
        target, name = _target_user(msg, args)
        if target is None:
            _send_group(ctx, chat_id, "Reply to a message to federally ban that member.", reply_to=reply_id)
        else:
            tracked = _load_json_file(GROUP_TRACKED_PATH)
            done = 0
            for gid in list(tracked.keys()):
                try:
                    gid_int = int(gid)
                except ValueError:
                    continue
                if cmd == "fban":
                    done += 1 if _ban(ctx, gid_int, target) else 0
                else:
                    done += 1 if _unban(ctx, gid_int, target) else 0
            _send_group(ctx, chat_id, f"✅ {name} {'federally banned' if cmd == 'fban' else 'federally unbanned'} in {done} tracked group(s).")
    elif cmd == "pin":
        reply = msg.get("reply_to_message") or {}
        if reply.get("message_id") is None:
            _send_group(ctx, chat_id, "Reply to a message to pin it.", reply_to=reply_id)
        else:
            try:
                ctx["call"]("pinChatMessage", {"chat_id": chat_id, "message_id": reply["message_id"]})
                _send_group(ctx, chat_id, "📌 Pinned.")
            except Exception:
                _send_group(ctx, chat_id, "Pin failed — is the bot admin with pin rights?")
    elif cmd == "unpin":
        try:
            ctx["call"]("unpinChatMessage", {"chat_id": chat_id})
            _send_group(ctx, chat_id, "📌 Unpinned.")
        except Exception:
            _send_group(ctx, chat_id, "Unpin failed — is the bot admin?")
    elif cmd == "setflood":
        if args and args[0].lower() == "off":
            settings["flood_limit"] = 0
            _save_group_settings(chat_id, settings)
            _send_group(ctx, chat_id, "✅ Antiflood disabled.")
        elif len(args) >= 2 and args[0].isdigit() and args[1].isdigit():
            settings["flood_limit"] = int(args[0])
            settings["flood_window"] = int(args[1])
            _save_group_settings(chat_id, settings)
            _send_group(ctx, chat_id, f"✅ Antiflood: more than {args[0]} messages in {args[1]}s triggers {settings.get('flood_mode', 'mute')}.")
        else:
            _send_group(ctx, chat_id, "Usage: /setflood <count> <seconds>  or  /setflood off")
    elif cmd == "setfloodmode":
        if args and args[0] in ("ban", "mute", "kick", "tban", "tmute"):
            settings["flood_mode"] = " ".join(args)
            _save_group_settings(chat_id, settings)
            _send_group(ctx, chat_id, f"✅ Flood mode set to {' '.join(args)}.")
        else:
            _send_group(ctx, chat_id, "Usage: /setfloodmode ban|mute|kick|tban <dur>|tmute <dur>")
    elif cmd in ("lock", "unlock"):
        types = ("links", "photo", "video", "document", "sticker", "animation", "forward")
        if not args or args[0] not in types:
            _send_group(ctx, chat_id, f"Usage: /{cmd} <type> — types: {', '.join(types)}")
        else:
            locks = list(settings.get("locks", []))
            if cmd == "lock" and args[0] not in locks:
                locks.append(args[0])
            if cmd == "unlock" and args[0] in locks:
                locks.remove(args[0])
            settings["locks"] = locks
            _save_group_settings(chat_id, settings)
            _send_group(ctx, chat_id, f"✅ {args[0]} {'locked' if cmd == 'lock' else 'unlocked'}.")
    elif cmd == "locks":
        locks = settings.get("locks", [])
        _send_group(ctx, chat_id, "🔒 Locked: " + (", ".join(locks) if locks else "nothing"))
    elif cmd in ("addblocklist", "unblocklist"):
        if not args:
            _send_group(ctx, chat_id, f"Usage: /{cmd} <word>")
        else:
            word = " ".join(args).lower()
            blocklist = list(settings.get("blocklist", []))
            if cmd == "addblocklist" and word not in blocklist:
                blocklist.append(word)
            if cmd == "unblocklist" and word in blocklist:
                blocklist.remove(word)
            settings["blocklist"] = blocklist
            _save_group_settings(chat_id, settings)
            _send_group(ctx, chat_id, f"✅ Blocklist {'added' if cmd == 'addblocklist' else 'removed'}: {word}")
    elif cmd == "blocklist":
        blocklist = settings.get("blocklist", [])
        _send_group(ctx, chat_id, "🚫 Blocked words: " + (", ".join(blocklist) if blocklist else "none"))
    elif cmd == "clearblocklist":
        settings["blocklist"] = []
        _save_group_settings(chat_id, settings)
        _send_group(ctx, chat_id, "✅ Blocklist cleared.")
    elif cmd == "save":
        if len(args) >= 2:
            notes = _load_json_file(GROUP_NOTES_PATH)
            notes.setdefault(str(chat_id), {})[args[0].lower()] = " ".join(args[1:])
            _save_json_file(GROUP_NOTES_PATH, notes)
            _send_group(ctx, chat_id, f"✅ Note saved: #{args[0].lower()}")
        else:
            _send_group(ctx, chat_id, "Usage: /save <name> <text>")
    elif cmd == "get":
        if not args:
            _send_group(ctx, chat_id, "Usage: /get <name>")
        else:
            note = _load_json_file(GROUP_NOTES_PATH).get(str(chat_id), {}).get(args[0].lower())
            _send_group(ctx, chat_id, note if note else f"No note named #{args[0].lower()}.")
    elif cmd == "notes":
        names = list(_load_json_file(GROUP_NOTES_PATH).get(str(chat_id), {}).keys())
        _send_group(ctx, chat_id, "📝 Notes: " + (", ".join("#" + n for n in names) if names else "none"))
    elif cmd == "clear":
        if not args:
            _send_group(ctx, chat_id, "Usage: /clear <name>")
        else:
            notes = _load_json_file(GROUP_NOTES_PATH)
            notes.setdefault(str(chat_id), {}).pop(args[0].lower(), None)
            _save_json_file(GROUP_NOTES_PATH, notes)
            _send_group(ctx, chat_id, f"✅ Note cleared: #{args[0].lower()}")
    else:
        _send_group(ctx, chat_id, "Unknown group command. Try /rosehelp.", reply_to=reply_id)
    return True


def _handle_group_message(ctx: dict, msg: dict) -> bool:
    """Filters for ordinary group messages. Returns True when handled
    (which is always, for group messages — the caller must not fall
    through to private Q&A). Commands are routed to _handle_group_command."""
    chat = msg.get("chat", {})
    chat_id = chat.get("id")
    sender = msg.get("from") or {}
    user_id = sender.get("id")
    if chat_id is None or user_id is None:
        return True
    if ctx.get("bot_id") is not None and user_id == ctx["bot_id"]:
        return True
    _track_group(chat)
    text = (msg.get("text") or "").strip()
    if text.startswith("/"):
        token = text.split(None, 1)[0][1:].split("@")[0]
        rest = text.split(None, 1)[1] if " " in text else ""
        return _handle_group_command(ctx, msg, token, rest.split() if rest else [])
    # Note trigger: #name
    if text.startswith("#"):
        name = text[1:].split()[0].lower() if len(text) > 1 else ""
        note = _load_json_file(GROUP_NOTES_PATH).get(str(chat_id), {}).get(name) if name else None
        if note:
            _send_group(ctx, chat_id, note)
        return True
    # Admins are exempt from filters (fail OPEN on a broken check).
    if _is_group_admin(ctx, chat_id, user_id, default=True):
        return True
    settings = _group_settings(chat_id)
    body = (msg.get("text") or "") + " " + (msg.get("caption") or "")
    # Blocklist
    lowered = body.lower()
    for word in settings.get("blocklist", []):
        if word and word in lowered:
            _delete_msg(ctx, chat_id, msg["message_id"])
            return True
    # Locks
    locks = set(settings.get("locks", []))
    if locks:
        if "links" in locks and re.search(r"https?://|t\.me/", body):
            _delete_msg(ctx, chat_id, msg["message_id"])
            return True
        if "forward" in locks and msg.get("forward_origin"):
            _delete_msg(ctx, chat_id, msg["message_id"])
            return True
        if "photo" in locks and msg.get("photo"):
            _delete_msg(ctx, chat_id, msg["message_id"])
            return True
        if "video" in locks and msg.get("video"):
            _delete_msg(ctx, chat_id, msg["message_id"])
            return True
        if "document" in locks and msg.get("document"):
            _delete_msg(ctx, chat_id, msg["message_id"])
            return True
        if "sticker" in locks and msg.get("sticker"):
            _delete_msg(ctx, chat_id, msg["message_id"])
            return True
        if "animation" in locks and msg.get("animation"):
            _delete_msg(ctx, chat_id, msg["message_id"])
            return True
    # Antiflood
    limit = int(settings.get("flood_limit", 0))
    if limit > 0:
        now = time.time()
        window = int(settings.get("flood_window", 10))
        key = (chat_id, user_id)
        stamps = [t for t in _FLOOD_TRACKER.get(key, []) if now - t < window]
        stamps.append(now)
        _FLOOD_TRACKER[key] = stamps
        if len(stamps) > limit:
            _FLOOD_TRACKER[key] = []
            _delete_msg(ctx, chat_id, msg["message_id"])
            mode = str(settings.get("flood_mode", "mute"))
            parts = mode.split(None, 1)
            result = _apply_punishment(ctx, chat_id, user_id,
                                       parts[0], parts[1] if len(parts) == 2 else None)
            _send_group(ctx, chat_id,
                        f"🚨 {sender.get('first_name') or 'Member'} flooded and was {result}.")
    return True


def _handle_group_join_welcome(msg: dict, ctx: dict) -> None:
    """Welcome/goodbye/clean-service for groups WITHOUT the force-join
    gate. Force-join groups skip this entirely — their joiners are
    handled privately, and a public welcome would leak the verification
    step's existence in the group chat."""
    chat = msg.get("chat", {})
    chat_id = chat.get("id")
    if chat_id is None:
        return
    if (chat.get("username") or "").lower() in load_assign_force_join_groups():
        return
    settings = _group_settings(chat_id)
    for member in msg.get("new_chat_members", []):
        if ctx.get("bot_id") is not None and member.get("id") == ctx["bot_id"]:
            continue
        if settings.get("welcome_on"):
            text = settings.get("welcome") or "Welcome {name} to {group}! Please read the rules with /rules."
            _send_group(ctx, chat_id, text.replace("{name}", member.get("first_name") or "there")
                        .replace("{group}", chat.get("title") or "this group"))
    if msg.get("left_chat_member"):
        member = msg["left_chat_member"]
        if settings.get("goodbye_on"):
            text = settings.get("goodbye") or "Goodbye {name}."
            _send_group(ctx, chat_id, text.replace("{name}", member.get("first_name") or "there")
                        .replace("{group}", chat.get("title") or "this group"))
    if settings.get("cleanservice"):
        _delete_msg(ctx, chat_id, msg["message_id"])


def handle_update(upd: dict, ctx: dict) -> None:
    menus = ctx["load_menus"]()
    msg = upd.get("message")
    # Group force-join: a new member in a listed group is restricted until
    # they join the assignment channel and tap Verify. Existing members are
    # never touched (this event only fires for joins).
    if msg and msg.get("new_chat_members"):
        _handle_new_members(msg, ctx)
        _handle_group_join_welcome(msg, ctx)
        return
    # Left-member service message: goodbye + clean-service only (the
    # force-join gate never touches departures).
    if msg and msg.get("left_chat_member"):
        _handle_group_join_welcome(msg, ctx)
        return
    # Rose-style group management: every other group message (commands,
    # ordinary text, media) is handled here and NEVER falls through to
    # the private Q&A fallback.
    if msg and msg.get("chat", {}).get("type") in ("group", "supergroup"):
        _handle_group_message(ctx, msg)
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
            # Private verification delivery: a joiner whose private
            # prompt could not be sent at join time (never started the
            # bot) gets it now, on their first private message. A /start
            # re-delivers even a previously sent prompt, in case it was
            # lost; other messages only deliver never-sent prompts.
            try:
                is_start = (msg.get("text") or "").strip().startswith("/start")
                _deliver_pending_prompts(ctx, sender["id"], force=is_start)
            except Exception as e:
                print("pending verify: delivery error:", e, flush=True)
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
        if text.startswith("/"):
            # Typed commands (button equivalents + /calc + /simple).
            # Unknown commands get a help hint — they are not doubts.
            if _handle_private_command(ctx, msg["chat"]["id"], text, menus):
                return
            ctx["call"]("sendMessage", {
                "chat_id": msg["chat"]["id"],
                "text": "Unknown command. Type /help for the list.",
                "reply_markup": ctx["main_keyboard"](),
            })
            return
        _handle_private_free_text(ctx, msg["chat"]["id"], text)
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
    # Assignment choice from a multi-programme code: handled with its own
    # answer, before the generic spinner-clearing answer below.
    if data.startswith("assign-get:"):
        _handle_assign_get(cb, ctx, menus)
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
        _send_quiz(ctx, chat_id)
        return
    if data == "menu:daily-notes":
        _send_notes(ctx, chat_id)
        return
    if data == "menu:daily-subscribe":
        # Legacy button: the subscription flow now starts here.
        ctx["show_menu"](chat_id, cb["message"]["message_id"],
                         "sub-choose-university", menus)
        return
    if data == "menu:my-subscription":
        _send_my_subscription(ctx, chat_id)
        return
    if data == "menu:unsubscribe":
        if unsubscribe(chat_id):
            msg = "✅ You are unsubscribed from Daily Study."
        else:
            msg = "You have no subscription to stop."
        ctx["call"]("sendMessage", {"chat_id": chat_id, "text": _fmt(chat_id, msg)})
        return
    if data.startswith("menu:sub-do-"):
        _do_subscribe(ctx, chat_id, data[len("menu:sub-do-"):])
        return
    if data.startswith("menu:"):
        key = data[len("menu:"):]
        if key.endswith("-assignments"):
            # Subject Assignments: forward the channel booklet. Falls
            # through to the ordinary menu page when the page carries no
            # single course code (year/semester pages).
            if _handle_assignments_page(cb, ctx, menus, key):
                return
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
