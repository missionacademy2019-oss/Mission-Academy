#!/usr/bin/env python3
"""Unit tests for Universal Phase 1 + accessibility. Stdlib only.

FakeCall records API calls; getChatMember returns administrator for
user 1 and member for everyone else. State files touched by the tests
(subscribers.json, doubts.json, pending_verify.json, group_tracked.json)
are snapshotted in setUp and restored/removed in tearDown — the real
subscribers list is never left changed by a test run.
Run with: python3 test_universal.py
"""
import json
import os
import re
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import handlers

HERE = Path(__file__).resolve().parent
MENUS = json.load(open(HERE / "menus.json", encoding="utf-8"))
EMOJI_RE = re.compile(r"[\U0001F000-\U0001FAFF\u2600-\u27BF\u2190-\u21FF\uFE0F]")
NEW_MENU_KEYS = ["home", "daily-study", "ask-question"] + \
    [k for k in MENUS if k.startswith("sub-")]


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


def make_ctx(fake, shown):
    return {"call": fake,
            "load_menus": lambda: MENUS,
            "main_keyboard": lambda: {},
            "show_menu": lambda cid, mid, key, menus: shown.append(key),
            "bot_id": 999}


def private_msg(text, chat_id=111):
    return {"update_id": 1,
            "message": {"chat": {"id": chat_id, "type": "private"},
                        "message_id": 10,
                        "from": {"id": chat_id, "first_name": "Test"},
                        "text": text}}


def callback(data, chat_id=111):
    return {"update_id": 1,
            "callback_query": {
                "id": "cb1",
                "from": {"id": chat_id, "first_name": "Test"},
                "message": {"chat": {"id": chat_id, "type": "private"},
                            "message_id": 10},
                "data": data}}


class TestUniversal(unittest.TestCase):
    def setUp(self):
        self.subs_path = HERE / "subscribers.json"
        self.subs_backup = self.subs_path.read_bytes() if self.subs_path.exists() else None
        self.doubts_path = HERE / "doubts.json"
        self.doubts_existed = self.doubts_path.exists()
        self.shown = []

    def tearDown(self):
        if self.subs_backup is not None:
            self.subs_path.write_bytes(self.subs_backup)
        elif self.subs_path.exists():
            self.subs_path.unlink()
        if not self.doubts_existed and self.doubts_path.exists():
            self.doubts_path.unlink()
        for name in ("pending_verify.json", "group_tracked.json",
                     "group_settings.json", "group_warns.json", "group_notes.json"):
            try:
                (HERE / name).unlink()
            except FileNotFoundError:
                pass
        handlers._FLOOD_TRACKER.clear()

    def test_home_clean_and_new_menus_accessible(self):
        home = MENUS["home"]
        total = sum(len(row) for row in home["buttons"])
        self.assertLessEqual(total, 5)
        for key in NEW_MENU_KEYS:
            for row in MENUS[key]["buttons"]:
                self.assertLessEqual(len(row), 2, key)
                for button in row:
                    # Descriptive words, never emoji-only or symbol-only.
                    self.assertRegex(button["text"], r"[A-Za-z]")

    def test_subscription_migrate_save_show_unsubscribe(self):
        self.subs_path.write_text("[111]", encoding="utf-8")
        subs = handlers.load_subscriptions()
        self.assertIn("111", subs)
        self.assertIsNone(subs["111"]["subject_code"])
        handlers.set_subscription(111, "IGNOU", "MAEG", "MEG-05",
                                  "Literary Theory and Criticism")
        got = handlers.get_subscription(111)
        self.assertEqual(got["subject_code"], "MEG-05")
        fake = FakeCall()
        handlers.handle_update(callback("menu:my-subscription", 111),
                               make_ctx(fake, self.shown))
        sends = methods(fake, "sendMessage")
        self.assertTrue(any("MEG-05" in s["text"] for s in sends))
        fake2 = FakeCall()
        handlers.handle_update(callback("menu:unsubscribe", 111),
                               make_ctx(fake2, self.shown))
        self.assertIsNone(handlers.get_subscription(111))

    def test_per_subject_quiz_differs_and_rotates(self):
        for code, items in handlers.load_subject_quizzes().items():
            self.assertEqual(len(items), 5, code)
            for item in items:
                self.assertEqual(len(item["options"]), 4)
                self.assertTrue(0 <= item["answer"] < 4)
        day = date(2026, 10, 27)
        q1 = handlers.today_subject_quiz("MEG-01", day)
        q2 = handlers.today_subject_quiz("MEG-02", day)
        self.assertNotEqual(q1["q"], q2["q"])
        self.assertNotEqual(handlers.today_subject_quiz("MEG-01", date(2026, 10, 28))["q"],
                            q1["q"])

    def test_quiz_button_uses_subject_and_plain_explanation(self):
        handlers.set_subscription(111, "IGNOU", "MAEG", "MEG-05",
                                  "Literary Theory and Criticism")
        fake = FakeCall()
        handlers.handle_update(callback("menu:daily-quiz-take", 111),
                               make_ctx(fake, self.shown))
        polls = methods(fake, "sendPoll")
        self.assertEqual(len(polls), 1)
        self.assertEqual(polls[0]["question"],
                         handlers.today_subject_quiz("MEG-05")["q"])
        self.assertNotIn("open_period", polls[0])  # no time pressure
        sends = methods(fake, "sendMessage")
        self.assertTrue(any("Answer:" in s["text"] for s in sends))
        # Unsubscribed user gets NO poll — a random generic quiz on
        # an unrelated topic is not a study programme. They get the
        # choose-a-subject message instead.
        fake2 = FakeCall()
        handlers.handle_update(callback("menu:daily-quiz-take", 222),
                               make_ctx(fake2, self.shown))
        self.assertEqual(methods(fake2, "sendPoll"), [])
        self.assertTrue(any("No quiz for your course yet" in s["text"]
                            for s in methods(fake2, "sendMessage")))

    def test_calc_correct_and_rejects_unsafe(self):
        cases = [("/calc 2+3*4", "Answer: 14"),
                 ("/calc (10-2)/4", "Answer: 2"),
                 ("/calc 1/0", "Cannot divide by zero"),
                 ("/calc __import__('os')", "not allowed"),
                 ("/calc os.system('x')", "not allowed"),
                 ("/calc 2 +", "not clear")]
        for text, expected in cases:
            fake = FakeCall()
            handlers.handle_update(private_msg(text), make_ctx(fake, self.shown))
            sends = methods(fake, "sendMessage")
            self.assertEqual(len(sends), 1, text)
            self.assertIn(expected, sends[0]["text"], text)
            self.assertEqual(methods(fake, "sendPoll"), [])

    def test_subject_note_doubt_and_unknown_doubt_saved(self):
        fake = FakeCall()
        handlers.handle_update(private_msg("Tell me about MEG-01"),
                               make_ctx(fake, self.shown))
        sends = methods(fake, "sendMessage")
        self.assertTrue(any("Chaucer" in s["text"] for s in sends))
        fake2 = FakeCall()
        # Keyword-free text (the word "doubt" itself is an FAQ keyword,
        # so a doubt containing it is rightly answered by the FAQ).
        handlers.handle_update(private_msg("blorptastic zizzle wobble"),
                               make_ctx(fake2, self.shown))
        sends2 = methods(fake2, "sendMessage")
        self.assertTrue(any("Saved for the team" in s["text"] for s in sends2))
        # The bare number must never appear as message text (Telegram
        # would link it to the owner's personal profile); contact is a
        # wa.me button instead.
        self.assertFalse(any("+91 86066 56245" in s["text"] for s in sends2))
        self.assertTrue(any(
            "wa.me/918606656245" in str(s.get("reply_markup"))
            for s in sends2))
        doubts = json.load(open(self.doubts_path, encoding="utf-8"))
        self.assertTrue(any(d["question"] == "blorptastic zizzle wobble"
                            for d in doubts))

    def test_simple_mode_toggles_plain_form(self):
        fake = FakeCall()
        handlers.handle_update(private_msg("/simple on"), make_ctx(fake, self.shown))
        self.assertTrue(handlers.is_simple(111))
        fake2 = FakeCall()
        handlers.handle_update(callback("menu:sub-do-MEG-01", 111),
                               make_ctx(fake2, self.shown))
        plain = methods(fake2, "sendMessage")[0]["text"]
        self.assertIsNone(EMOJI_RE.search(plain))
        handlers.handle_update(private_msg("/simple off"), make_ctx(fake, self.shown))
        self.assertFalse(handlers.is_simple(111))
        handlers.unsubscribe(111)
        fake3 = FakeCall()
        handlers.handle_update(callback("menu:sub-do-MEG-01", 111),
                               make_ctx(fake3, self.shown))
        normal = methods(fake3, "sendMessage")[0]["text"]
        self.assertIn("✅", normal)

    def test_every_button_action_has_command(self):
        fake = FakeCall()
        handlers.handle_update(private_msg("/help"), make_ctx(fake, self.shown))
        help_text = methods(fake, "sendMessage")[0]["text"]
        for cmd in ("/home", "/ignou", "/sgou", "/dailystudy", "/quiz",
                    "/notes", "/subscribe", "/mysubscription", "/unsubscribe",
                    "/ask", "/calc", "/simple", "/help"):
            self.assertIn(cmd, help_text, cmd)
        # Command equivalents actually work like the buttons.
        fake2 = FakeCall()
        handlers.handle_update(private_msg("/quiz"), make_ctx(fake2, self.shown))
        self.assertEqual(len(methods(fake2, "sendPoll")), 1)
        fake3 = FakeCall()
        handlers.handle_update(private_msg("/mysubscription"),
                               make_ctx(fake3, self.shown))
        self.assertTrue(any("Subscription" in s["text"]
                            for s in methods(fake3, "sendMessage")))

    def test_group_and_assignments_behaviour_unchanged(self):
        fake = FakeCall()
        handlers.handle_update(
            {"update_id": 1,
             "message": {"chat": {"id": -100, "type": "supergroup", "title": "G"},
                         "message_id": 20,
                         "from": {"id": 2, "first_name": "User2"},
                         "text": "hello everyone"}},
            make_ctx(fake, self.shown))
        self.assertEqual(methods(fake, "sendMessage"), [])
        fake2 = FakeCall()
        handlers.handle_update(
            callback("menu:ignou-pg-maeg-yr1-meg01-assignments", 111),
            make_ctx(fake2, self.shown))
        forwards = methods(fake2, "forwardMessage")
        self.assertEqual(len(forwards), 1)
        self.assertEqual(forwards[0]["message_id"], 43)
        # Force-join: a new member in a listed group is restricted.
        fake3 = FakeCall()
        handlers.handle_update(
            {"update_id": 1,
             "message": {"chat": {"id": -100123, "type": "supergroup",
                                  "title": "MEG 01", "username": "meg01new"},
                         "message_id": 30,
                         "new_chat_members": [{"id": 7, "first_name": "Asha"}]}},
            make_ctx(fake3, self.shown))
        self.assertTrue(any(p["user_id"] == 7
                            for p in methods(fake3, "restrictChatMember")))


if __name__ == "__main__":
    unittest.main()
