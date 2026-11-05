#!/usr/bin/env python3
"""Unit tests for Assignments buttons wired to the channel index.

Stdlib only, no network: ctx["call"] is a recording stub. The tests use
the real assignment_index.json shipped with the bot (1,895 codes), so
they also pin the index entries for the MAEG papers they cover. Run with:
    python3 test_assignments.py
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import handlers


class FakeCall:
    def __init__(self, fail_on=None):
        self.calls = []
        self.fail_on = fail_on or set()

    def __call__(self, method, payload, timeout=15):
        self.calls.append((method, payload))
        if method in self.fail_on:
            raise RuntimeError("simulated API failure: " + method)
        return {"ok": True, "result": {}}


MENUS = {
    "home": {"text": "home", "buttons": []},
    "ignou-pg-maeg-yr1-meg01": {"text": "MAEG — Year 1 — MEG-01 · British Poetry", "buttons": []},
    "ignou-pg-maeg-yr1-meg01-assignments": {
        "text": "MAEG — Year 1 — MEG-01 · British Poetry — Assignments\n\nContent coming soon.",
        "buttons": []},
    "ignou-pg-maeg-yr1-meg08": {"text": "MAEG — Year 1 — MEG-08 · New Literatures in English", "buttons": []},
    "ignou-pg-maeg-yr1-meg08-assignments": {
        "text": "MAEG — Year 1 — MEG-08 · New Literatures in English — Assignments\n\nContent coming soon.",
        "buttons": []},
    "ignou-pg-test-mev021-assignments": {
        "text": "Test — MEV-021 · Test Paper — Assignments\n\nContent coming soon.",
        "buttons": []},
    "ignou-pg-test-zzz99-assignments": {
        "text": "Test — ZZZ-99 · Missing Paper — Assignments\n\nContent coming soon.",
        "buttons": []},
    "ignou-ug-baegh-sem1-assignments": {
        "text": "BAEGH — Semester 1 — Assignments\n\nContent coming soon.",
        "buttons": []},
}


def make_ctx(fake):
    return {
        "call": fake,
        "load_menus": lambda: MENUS,
        "main_keyboard": lambda: {},
        "show_menu": lambda *a: None,
        "bot_id": 999,
    }


def menu_update(key, chat_id=111):
    return {"update_id": 1,
            "callback_query": {
                "id": "cb1",
                "from": {"id": chat_id, "first_name": "Test"},
                "message": {"chat": {"id": chat_id, "type": "private"},
                            "message_id": 10},
                "data": "menu:" + key,
            }}


def methods(fake, name):
    return [p for m, p in fake.calls if m == name]


class TestAssignments(unittest.TestCase):
    def test_meg01_forwards_channel_booklet(self):
        fake = FakeCall()
        handlers.handle_update(
            menu_update("ignou-pg-maeg-yr1-meg01-assignments"), make_ctx(fake))
        forwards = methods(fake, "forwardMessage")
        self.assertEqual(len(forwards), 1)
        self.assertEqual(forwards[0]["from_chat_id"], "@ignouassignmentsofficial")
        self.assertEqual(forwards[0]["message_id"], 43)
        self.assertEqual(forwards[0]["chat_id"], 111)
        captions = methods(fake, "sendMessage")
        self.assertTrue(any("MEG-01" in c["text"] for c in captions))

    def test_meg08_prefers_maeg_entry(self):
        # MEG-08 also has a MEG/PGDNLEG booklet (819); the MAEG hub must
        # forward the MAEG booklet (25), not the other programme's.
        fake = FakeCall()
        handlers.handle_update(
            menu_update("ignou-pg-maeg-yr1-meg08-assignments"), make_ctx(fake))
        forwards = methods(fake, "forwardMessage")
        self.assertEqual([f["message_id"] for f in forwards], [25])

    def test_multi_programme_code_offers_choice_then_forwards(self):
        fake = FakeCall()
        handlers.handle_update(
            menu_update("ignou-pg-test-mev021-assignments"), make_ctx(fake))
        self.assertEqual(methods(fake, "forwardMessage"), [])
        sends = methods(fake, "sendMessage")
        self.assertEqual(len(sends), 1)
        buttons = sends[0]["reply_markup"]["inline_keyboard"]
        flat = [b for row in buttons for b in row]
        datas = [b["callback_data"] for b in flat if "callback_data" in b]
        # Choice callbacks carry the parent hub for the Back button.
        self.assertTrue(any(d.startswith("assign-get:1366") for d in datas))
        self.assertTrue(any(d.startswith("assign-get:3") for d in datas))
        # Choose the PGCCC booklet (message 3).
        fake2 = FakeCall()
        handlers.handle_update(
            {"update_id": 2,
             "callback_query": {
                 "id": "cb2",
                 "from": {"id": 111, "first_name": "Test"},
                 "message": {"chat": {"id": 111, "type": "private"},
                             "message_id": 11},
                 "data": "assign-get:3"}},
            make_ctx(fake2))
        forwards = methods(fake2, "forwardMessage")
        self.assertEqual([f["message_id"] for f in forwards], [3])

    def test_missing_code_reports_honestly_no_forward(self):
        fake = FakeCall()
        handlers.handle_update(
            menu_update("ignou-pg-test-zzz99-assignments"), make_ctx(fake))
        self.assertEqual(methods(fake, "forwardMessage"), [])
        sends = methods(fake, "sendMessage")
        self.assertEqual(len(sends), 1)
        self.assertIn("No current assignment booklet", sends[0]["text"])

    def test_forward_failure_falls_back_to_channel_link(self):
        fake = FakeCall(fail_on={"forwardMessage"})
        handlers.handle_update(
            menu_update("ignou-pg-maeg-yr1-meg01-assignments"), make_ctx(fake))
        sends = methods(fake, "sendMessage")
        self.assertEqual(len(sends), 1)
        buttons = sends[0]["reply_markup"]["inline_keyboard"]
        flat = [b for row in buttons for b in row]
        self.assertEqual(flat[0]["url"], "https://t.me/ignouassignmentsofficial/43")

    def test_semester_page_without_code_falls_through(self):
        # Year/semester pages carry no single code: no forward, no send —
        # the ordinary menu page (show_menu stub) handles them.
        fake = FakeCall()
        handlers.handle_update(
            menu_update("ignou-ug-baegh-sem1-assignments"), make_ctx(fake))
        self.assertEqual(methods(fake, "forwardMessage"), [])
        self.assertEqual(methods(fake, "sendMessage"), [])


if __name__ == "__main__":
    unittest.main()
