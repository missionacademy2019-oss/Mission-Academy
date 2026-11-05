#!/usr/bin/env python3
"""Unit tests for the group force-join feature (handlers.py).

Stdlib only, no network: ctx["call"] is a recording stub whose
getChatMember answers are driven by the test scenario. Run with:
    python3 test_group_force_join.py
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import handlers


class FakeCall:
    def __init__(self, member_status="member", fail_on=None, raise_on_get=False):
        self.calls = []
        self.member_status = member_status  # "member"/"left"/"kicked"/None (= ok:false)
        self.fail_on = fail_on or set()
        self.raise_on_get = raise_on_get

    def __call__(self, method, payload, timeout=15):
        self.calls.append((method, payload))
        if method in self.fail_on:
            raise RuntimeError("simulated API failure: " + method)
        if method == "getChatMember":
            if self.raise_on_get:
                raise RuntimeError("simulated network failure")
            if self.member_status is None:
                return {"ok": False}
            return {"ok": True, "result": {"status": self.member_status}}
        return {"ok": True, "result": {}}


def make_ctx(fake, bot_id=999):
    return {
        "call": fake,
        "load_menus": lambda: {"home": {"text": "home", "buttons": []}},
        "main_keyboard": lambda: {},
        "show_menu": lambda *a: None,
        "bot_id": bot_id,
    }


GROUP_CHAT = {"id": -100123, "username": "meg01new", "type": "supergroup"}
OTHER_CHAT = {"id": -100999, "username": "randomgroup", "type": "supergroup"}


def join_update(chat, members):
    return {"update_id": 1,
            "message": {"chat": chat, "new_chat_members": members}}


def verify_update(chat, user_id):
    return {"update_id": 2,
            "callback_query": {
                "id": "cb1",
                "from": {"id": user_id, "first_name": "Test"},
                "message": {"chat": chat},
                "data": "verify-assign:%d" % user_id,
            }}


def verify_private_update(user_id, group_id, from_id=None):
    return {"update_id": 2,
            "callback_query": {
                "id": "cb1",
                "from": {"id": from_id if from_id is not None else user_id,
                         "first_name": "Test"},
                "message": {"chat": {"id": user_id, "type": "private"},
                            "message_id": 777},
                "data": "verify-assign:%d:%d" % (user_id, group_id),
            }}


def methods(fake, name):
    return [p for m, p in fake.calls if m == name]


class TestGroupForceJoin(unittest.TestCase):
    def setUp(self):
        # Point the starters + pending files at temp paths so tests never
        # touch the real bot_starters.json / pending_verify.json.
        fd, self._tmp_path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        os.unlink(self._tmp_path)
        self._orig_path = handlers.BOT_STARTERS_PATH
        handlers.BOT_STARTERS_PATH = self._tmp_path
        fd, self._tmp_pending = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        os.unlink(self._tmp_pending)
        self._orig_pending = handlers.PENDING_VERIFY_PATH
        handlers.PENDING_VERIFY_PATH = self._tmp_pending

    def tearDown(self):
        handlers.BOT_STARTERS_PATH = self._orig_path
        if os.path.exists(self._tmp_path):
            os.unlink(self._tmp_path)
        handlers.PENDING_VERIFY_PATH = self._orig_pending
        if os.path.exists(self._tmp_pending):
            os.unlink(self._tmp_pending)

    def read_pending(self):
        if not os.path.exists(self._tmp_pending):
            return []
        with open(self._tmp_pending, encoding="utf-8") as f:
            return json.load(f)

    def set_starters(self, user_ids):
        with open(self._tmp_path, "w", encoding="utf-8") as f:
            json.dump(list(user_ids), f)

    def read_starters(self):
        if not os.path.exists(self._tmp_path):
            return []
        with open(self._tmp_path, encoding="utf-8") as f:
            return json.load(f)

    def test_join_in_listed_group_restricts_and_prompts_privately(self):
        # Private verification: restrict in the group, prompt ONLY in the
        # joiner's private chat — nothing is sent to the group itself.
        fake = FakeCall()
        handlers.handle_update(
            join_update(GROUP_CHAT, [{"id": 111, "first_name": "Asha"}]),
            make_ctx(fake))
        restricts = methods(fake, "restrictChatMember")
        self.assertEqual(len(restricts), 1)
        self.assertEqual(restricts[0]["user_id"], 111)
        self.assertTrue(all(v is False
                            for v in restricts[0]["permissions"].values()))
        sends = methods(fake, "sendMessage")
        self.assertEqual(len(sends), 1)
        self.assertEqual(sends[0]["chat_id"], 111)
        self.assertNotEqual(sends[0]["chat_id"], GROUP_CHAT["id"])
        buttons = sends[0]["reply_markup"]["inline_keyboard"]
        self.assertEqual(len(buttons), 2)
        self.assertEqual(buttons[0][0]["url"],
                         "https://t.me/ignouassignmentsofficial")
        self.assertEqual(buttons[1][0]["callback_data"],
                         "verify-assign:111:-100123")
        pending = self.read_pending()
        self.assertEqual(len(pending), 1)
        self.assertTrue(pending[0]["prompt_sent"])

    def test_private_prompt_has_join_and_verify_buttons(self):
        fake = FakeCall()
        handlers.handle_update(
            join_update(GROUP_CHAT, [{"id": 111, "first_name": "Asha"}]),
            make_ctx(fake))
        buttons = methods(fake, "sendMessage")[0]["reply_markup"]["inline_keyboard"]
        flat = [b for row in buttons for b in row]
        self.assertEqual(flat[0]["text"], "📢 Join @ignouassignmentsofficial")
        self.assertEqual(flat[1]["text"], "✅ I've joined — Verify")

    def test_verify_member_and_started_unrestricts(self):
        self.set_starters([111])
        fake = FakeCall(member_status="member")
        handlers.handle_update(verify_update(GROUP_CHAT, 111), make_ctx(fake))
        restricts = methods(fake, "restrictChatMember")
        self.assertEqual(len(restricts), 1)
        self.assertTrue(all(v is True
                            for v in restricts[0]["permissions"].values()))
        answers = methods(fake, "answerCallbackQuery")
        self.assertEqual(len(answers), 1)
        self.assertNotIn("show_alert", answers[0])

    def test_verify_member_not_started_stays_restricted(self):
        # Channel OK but bot never started: stays restricted + start alert.
        fake = FakeCall(member_status="member")
        handlers.handle_update(verify_update(GROUP_CHAT, 111), make_ctx(fake))
        self.assertEqual(methods(fake, "restrictChatMember"), [])
        answers = methods(fake, "answerCallbackQuery")
        self.assertEqual(len(answers), 1)
        self.assertTrue(answers[0].get("show_alert"))
        self.assertIn("Start", answers[0].get("text", ""))

    def test_verify_left_started_stays_restricted(self):
        # Channel left wins over bot-started: stays restricted, channel alert.
        self.set_starters([111])
        fake = FakeCall(member_status="left")
        handlers.handle_update(verify_update(GROUP_CHAT, 111), make_ctx(fake))
        self.assertEqual(methods(fake, "restrictChatMember"), [])
        answers = methods(fake, "answerCallbackQuery")
        self.assertEqual(len(answers), 1)
        self.assertTrue(answers[0].get("show_alert"))
        self.assertIn("join", answers[0].get("text", "").lower())

    def test_verify_check_error_fail_open(self):
        # Both error shapes (exception and ok:false) must unrestrict.
        for variant in ("raise", "notok"):
            fake = FakeCall(raise_on_get=(variant == "raise"),
                            member_status=None if variant == "notok" else "member")
            handlers.handle_update(verify_update(GROUP_CHAT, 111), make_ctx(fake))
            restricts = methods(fake, "restrictChatMember")
            self.assertEqual(len(restricts), 1)
            self.assertTrue(all(v is True
                                for v in restricts[0]["permissions"].values()))

    def test_join_in_non_listed_group_ignored(self):
        fake = FakeCall()
        handlers.handle_update(
            join_update(OTHER_CHAT, [{"id": 111, "first_name": "Asha"}]),
            make_ctx(fake))
        self.assertEqual(fake.calls, [])

    def test_bot_own_join_ignored(self):
        fake = FakeCall()
        handlers.handle_update(
            join_update(GROUP_CHAT, [{"id": 999, "first_name": "Bot"}]),
            make_ctx(fake, bot_id=999))
        self.assertEqual(fake.calls, [])

    def test_mixed_join_only_real_user_restricted(self):
        fake = FakeCall()
        handlers.handle_update(
            join_update(GROUP_CHAT, [{"id": 999, "first_name": "Bot"},
                                    {"id": 111, "first_name": "Asha"}]),
            make_ctx(fake, bot_id=999))
        restricts = methods(fake, "restrictChatMember")
        self.assertEqual([r["user_id"] for r in restricts], [111])

    def test_restrict_failure_does_not_crash_and_still_prompts(self):
        fake = FakeCall(fail_on={"restrictChatMember"})
        handlers.handle_update(
            join_update(GROUP_CHAT, [{"id": 111, "first_name": "Asha"}]),
            make_ctx(fake))
        self.assertEqual(len(methods(fake, "sendMessage")), 1)

    def test_private_start_records_starter(self):
        fake = FakeCall()
        handlers.handle_update(
            {"update_id": 3,
             "message": {"chat": {"id": 111, "type": "private"},
                         "from": {"id": 111, "first_name": "Asha"},
                         "text": "/start"}},
            make_ctx(fake))
        self.assertEqual(self.read_starters(), [111])

    def test_private_text_message_records_starter(self):
        # Any private message counts, not just /start.
        fake = FakeCall()
        handlers.handle_update(
            {"update_id": 3,
             "message": {"chat": {"id": 111, "type": "private"},
                         "from": {"id": 111, "first_name": "Asha"},
                         "text": "hello"}},
            make_ctx(fake))
        self.assertEqual(self.read_starters(), [111])

    def test_group_message_does_not_record_starter(self):
        fake = FakeCall()
        handlers.handle_update(
            {"update_id": 3,
             "message": {"chat": {"id": -100123, "type": "supergroup",
                                  "username": "meg01new"},
                         "from": {"id": 111, "first_name": "Asha"},
                         "text": "hello"}},
            make_ctx(fake))
        self.assertEqual(self.read_starters(), [])

    def test_start_then_verify_unrestricts(self):
        # Restricted user starts the bot, then Verify works afterwards.
        fake = FakeCall(member_status="member")
        ctx = make_ctx(fake)
        handlers.handle_update(verify_update(GROUP_CHAT, 111), ctx)
        self.assertEqual(methods(fake, "restrictChatMember"), [])
        handlers.handle_update(
            {"update_id": 3,
             "message": {"chat": {"id": 111, "type": "private"},
                         "from": {"id": 111, "first_name": "Asha"},
                         "text": "/start"}},
            ctx)
        handlers.handle_update(verify_update(GROUP_CHAT, 111), ctx)
        restricts = methods(fake, "restrictChatMember")
        self.assertEqual(len(restricts), 1)
        self.assertTrue(all(v is True
                            for v in restricts[0]["permissions"].values()))

    def test_private_verify_member_unrestricts_and_clears_pending(self):
        fake = FakeCall(member_status="member")
        ctx = make_ctx(fake)
        handlers.handle_update(
            join_update(GROUP_CHAT, [{"id": 111, "first_name": "Asha"}]), ctx)
        self.assertEqual(len(self.read_pending()), 1)
        handlers.handle_update(verify_private_update(111, -100123), ctx)
        restricts = methods(fake, "restrictChatMember")
        self.assertEqual(restricts[-1]["chat_id"], -100123)
        self.assertTrue(all(v is True
                            for v in restricts[-1]["permissions"].values()))
        deletes = methods(fake, "deleteMessage")
        self.assertEqual(len(deletes), 1)
        self.assertEqual(deletes[0]["chat_id"], 111)  # private prompt, not group
        self.assertEqual(deletes[0]["message_id"], 777)
        self.assertEqual(self.read_pending(), [])

    def test_private_verify_by_other_user_rejected(self):
        fake = FakeCall(member_status="member")
        ctx = make_ctx(fake)
        handlers.handle_update(
            join_update(GROUP_CHAT, [{"id": 111, "first_name": "Asha"}]), ctx)
        handlers.handle_update(
            verify_private_update(111, -100123, from_id=222), ctx)
        # No unrestrict: only the initial restrict exists.
        self.assertEqual(len(methods(fake, "restrictChatMember")), 1)
        answers = methods(fake, "answerCallbackQuery")
        self.assertTrue(answers[-1].get("show_alert"))
        self.assertEqual(len(self.read_pending()), 1)

    def test_private_verify_left_stays_restricted_and_pending_kept(self):
        fake = FakeCall(member_status="left")
        ctx = make_ctx(fake)
        handlers.handle_update(
            join_update(GROUP_CHAT, [{"id": 111, "first_name": "Asha"}]), ctx)
        handlers.handle_update(verify_private_update(111, -100123), ctx)
        self.assertEqual(len(methods(fake, "restrictChatMember")), 1)
        self.assertEqual(len(self.read_pending()), 1)
        self.assertEqual(methods(fake, "deleteMessage"), [])

    def test_private_prompt_failure_keeps_pending_delivers_on_start(self):
        # Joiner never started the bot: private send fails, nothing is
        # posted in the group, pending stays unsent.
        fake = FakeCall(fail_on={"sendMessage"})
        ctx = make_ctx(fake)
        handlers.handle_update(
            join_update(GROUP_CHAT, [{"id": 111, "first_name": "Asha"}]), ctx)
        # The private attempt failed; nothing reached the group itself.
        self.assertEqual(
            [s for s in methods(fake, "sendMessage")
             if s["chat_id"] == GROUP_CHAT["id"]], [])
        pending = self.read_pending()
        self.assertEqual(len(pending), 1)
        self.assertFalse(pending[0]["prompt_sent"])
        # Their first private message (/start) delivers the prompt once.
        fake2 = FakeCall()
        handlers.handle_update(
            {"update_id": 3,
             "message": {"chat": {"id": 111, "type": "private"},
                         "from": {"id": 111, "first_name": "Asha"},
                         "text": "/start"}},
            make_ctx(fake2))
        sends = methods(fake2, "sendMessage")
        self.assertEqual(len(sends), 1)
        self.assertEqual(sends[0]["chat_id"], 111)
        self.assertTrue(self.read_pending()[0]["prompt_sent"])


if __name__ == "__main__":
    unittest.main()
