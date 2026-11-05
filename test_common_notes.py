#!/usr/bin/env python3
"""Tests for the 28 Oct common-course notes rule: every note/quiz
carries its course code, subject and topic; nothing generic is sent.
Run with: python3 test_common_notes.py
"""
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import handlers


class TestCommonNotes(unittest.TestCase):
    def test_bevae_note_is_labelled(self):
        note = handlers.today_subject_note("BEVAE-181", date(2026, 10, 28))
        self.assertIsNotNone(note)
        self.assertIn("BEVAE-181", note)
        self.assertIn("Environmental Studies", note)
        self.assertIn("Topic:", note)

    def test_bevae_notes_rotate_by_topic(self):
        topics = {handlers.today_subject_note("BEVAE-181", date(2026, 10, d)).splitlines()[1]
                  for d in range(28, 31)}
        self.assertGreater(len(topics), 1)

    def test_bevae_quiz_is_banked_and_labelled_by_code(self):
        quiz = handlers.today_subject_quiz("BEVAE-181", date(2026, 10, 28))
        self.assertIsNotNone(quiz)
        self.assertIn("answer", quiz)

    def test_generic_paths_retired(self):
        self.assertIsNone(handlers.today_quiz())
        self.assertIsNone(handlers.today_notes())

    def test_unbanked_subject_gets_nothing(self):
        self.assertIsNone(handlers.today_subject_note("BEGC-101"))
        self.assertIsNone(handlers.today_subject_quiz("BEGC-101"))

    def test_screenshot_card_is_now_a_bevae_card(self):
        # The 28 Oct screenshot card ("Environment = air, water, land…")
        # must only ever go out as BEVAE-181 Block 1, never unlabelled.
        topics = handlers.load_subject_note_topics()["BEVAE-181"]
        joined = "\n".join(c["text"] for c in topics)
        self.assertIn("Environment = air, water, land", joined)
        self.assertTrue(any(c["topic"].startswith("Block 1") and
                            "Environment = air, water, land" in c["text"]
                            for c in topics))

    def test_subscribe_accepts_bevae(self):
        calls = []

        class Fake:
            def __call__(self, method, payload, timeout=15):
                calls.append((method, payload))
                return {"ok": True, "result": {}}
        ctx = {"call": Fake()}
        # private chat id; subscribers.json is snapshotted/restored below
        import json, os
        path = Path(__file__).resolve().parent / "subscribers.json"
        backup = path.read_text(encoding="utf-8") if path.exists() else None
        try:
            handlers._do_subscribe(ctx, 999001, "BEVAE-181")
            sub = handlers.get_subscription(999001)
            self.assertEqual(sub["subject_code"], "BEVAE-181")
            self.assertEqual(sub["subject_name"], "Environmental Studies")
        finally:
            if backup is None:
                if path.exists():
                    os.remove(path)
            else:
                path.write_text(backup, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
