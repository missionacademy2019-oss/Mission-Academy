#!/usr/bin/env python3
"""Unit tests for Rose-style group management. Stdlib only, no network.

ctx["call"] is a recording stub: getChatMember returns administrator for
user 1 (the admin) and member for everyone else; other methods record
and succeed. State files (group_settings/warns/notes/tracked) are written
next to this test's bot dir and cleaned up by tearDown — they are NOT
shipped. Run with: python3 test_rose.py
"""
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import handlers

HERE = Path(__file__).resolve().parent
STATE_FILES = ["group_settings.json", "group_warns.json",
               "group_notes.json", "group_tracked.json"]


class FakeCall:
    def __init__(self):
        self.calls = []

    def __call__(self, method, payload, timeout=15):
        self.calls.append((method, payload))
        if method == "getChatMember":
            status = "administrator" if payload.get("user_id") == 1 else "member"
            return {"ok": True, "result": {"status": status}}
        return {"ok": True, "result": {}}


def methods(fake, name):
    return [p for m, p in fake.calls if m == name]


def make_ctx(fake):
    return {"call": fake, "load_menus": lambda: {"home": {"text": "home", "buttons": []}},
            "main_keyboard": lambda: {}, "show_menu": lambda *a: None, "bot_id": 999}


def group_msg(text=None, user_id=2, chat_id=100, reply_to=None, **extra):
    msg = {"chat": {"id": chat_id, "type": "supergroup", "title": "Test Group"},
           "message_id": 50,
           "from": {"id": user_id, "first_name": f"User{user_id}"}}
    if text is not None:
        msg["text"] = text
    if reply_to is not None:
        msg["reply_to_message"] = {"message_id": 49,
                                   "from": {"id": reply_to, "first_name": f"User{reply_to}"}}
    msg.update(extra)
    return {"update_id": 1, "message": msg}


class TestRose(unittest.TestCase):
    def tearDown(self):
        for name in STATE_FILES:
            try:
                os.remove(HERE / name)
            except FileNotFoundError:
                pass
        handlers._FLOOD_TRACKER.clear()

    def test_rules_set_by_admin_read_by_anyone(self):
        fake = FakeCall()
        handlers.handle_update(group_msg("/setrules Be kind. No spam.", user_id=1), make_ctx(fake))
        fake2 = FakeCall()
        handlers.handle_update(group_msg("/rules", user_id=2), make_ctx(fake2))
        sends = methods(fake2, "sendMessage")
        self.assertEqual(len(sends), 1)
        self.assertIn("Be kind", sends[0]["text"])

    def test_non_admin_cannot_ban(self):
        fake = FakeCall()
        handlers.handle_update(group_msg("/ban", user_id=2, reply_to=3), make_ctx(fake))
        self.assertEqual(methods(fake, "banChatMember"), [])
        sends = methods(fake, "sendMessage")
        self.assertTrue(any("Only group admins" in s["text"] for s in sends))

    def test_admin_ban_and_warn_limit(self):
        fake = FakeCall()
        handlers.handle_update(group_msg("/ban", user_id=1, reply_to=3), make_ctx(fake))
        self.assertEqual(len(methods(fake, "banChatMember")), 1)
        # Warn twice: counted, not punished. Third warn: ban + reset.
        fake2 = FakeCall()
        ctx = make_ctx(fake2)
        for _ in range(2):
            handlers.handle_update(group_msg("/warn spam", user_id=1, reply_to=3), ctx)
        self.assertEqual(methods(fake2, "banChatMember"), [])
        handlers.handle_update(group_msg("/warn spam", user_id=1, reply_to=3), ctx)
        self.assertEqual(len(methods(fake2, "banChatMember")), 1)
        sends = methods(fake2, "sendMessage")
        self.assertTrue(any("reached 3 warnings" in s["text"] for s in sends))

    def test_blocklist_and_link_lock_delete(self):
        fake = FakeCall()
        ctx = make_ctx(fake)
        handlers.handle_update(group_msg("/addblocklist spamword", user_id=1), ctx)
        handlers.handle_update(group_msg("/lock links", user_id=1), ctx)
        handlers.handle_update(group_msg("this has spamword in it", user_id=2), ctx)
        handlers.handle_update(group_msg("see https://example.com", user_id=2), ctx)
        handlers.handle_update(group_msg("clean message", user_id=2), ctx)
        deletes = methods(fake, "deleteMessage")
        self.assertEqual(len(deletes), 2)

    def test_antiflood_mutes(self):
        fake = FakeCall()
        ctx = make_ctx(fake)
        handlers.handle_update(group_msg("/setflood 2 60", user_id=1), ctx)
        handlers.handle_update(group_msg("one", user_id=2), ctx)
        handlers.handle_update(group_msg("two", user_id=2), ctx)
        handlers.handle_update(group_msg("three", user_id=2), ctx)
        self.assertEqual(len(methods(fake, "deleteMessage")), 1)
        self.assertEqual(len(methods(fake, "restrictChatMember")), 1)

    def test_notes_save_and_hash_trigger(self):
        fake = FakeCall()
        ctx = make_ctx(fake)
        handlers.handle_update(group_msg("/save timetable Mon 9am class", user_id=1), ctx)
        handlers.handle_update(group_msg("#timetable", user_id=2), ctx)
        sends = methods(fake, "sendMessage")
        self.assertTrue(any("Mon 9am class" in s["text"] for s in sends))

    def test_welcome_for_non_force_join_group(self):
        fake = FakeCall()
        ctx = make_ctx(fake)
        handlers.handle_update(group_msg("/setwelcome Welcome {name} to {group}!", user_id=1), ctx)
        handlers.handle_update(
            {"update_id": 2,
             "message": {"chat": {"id": 100, "type": "supergroup", "title": "Test Group"},
                         "message_id": 60,
                         "new_chat_members": [{"id": 7, "first_name": "Asha"}]}},
            ctx)
        sends = methods(fake, "sendMessage")
        self.assertTrue(any("Welcome Asha to Test Group" in s["text"] for s in sends))

    def test_group_text_never_gets_private_qa_fallback(self):
        fake = FakeCall()
        handlers.handle_update(group_msg("hello everyone", user_id=2), make_ctx(fake))
        self.assertEqual(methods(fake, "sendMessage"), [])


if __name__ == "__main__":
    unittest.main()
