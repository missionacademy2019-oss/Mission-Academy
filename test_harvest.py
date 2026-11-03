"""Bulk-harvest mode tests: admin-only, direct attach, no queue expiry.

Covers /harvest_start, /harvest_stop, /harvest_status and the direct
attach of admin documents while a harvest target is set. State files
are redirected to a temp dir so the real bot state is never touched.
"""

import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import handlers  # noqa: E402


def make_ctx(fake, shown, menus):
    return {"call": fake, "load_menus": lambda: menus,
            "show_menu": lambda chat, mid, key, menus: shown.append(key),
            "main_keyboard": lambda: None}


class FakeCall:
    def __init__(self):
        self.calls = []

    def __call__(self, method, payload):
        self.calls.append((method, payload))
        return {"ok": True, "result": {}}


def texts(fake, name="sendMessage"):
    return [p["text"] for m, p in fake.calls if m == name]


def private_msg(text, uid=111, username="someone"):
    return {"message": {"chat": {"id": uid, "type": "private"},
                        "from": {"id": uid, "username": username},
                        "text": text}}


def private_doc(file_id, file_name, uid=111, username="someone"):
    return {"message": {"chat": {"id": uid, "type": "private"},
                        "from": {"id": uid, "username": username},
                        "document": {"file_id": file_id,
                                     "file_name": file_name}}}


ADMIN = {"id": 999, "username": "Shafeque_rayaroth"}
PAGE = "ignou-pg-maeg-yr1-meg05-notes"
MENUS = {PAGE: {"text": "MAEG — Year 1 — Notes"}}


class HarvestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._orig = {}
        for attr, name in (("PENDING_PATH", "pending_files.json"),
                           ("NOTES_FILES_PATH", "notes_files.json"),
                           ("HARVEST_STATE_PATH", "harvest_state.json"),
                           ("BOT_STARTERS_PATH", "bot_starters.json")):
            self._orig[attr] = getattr(handlers, attr)
            setattr(handlers, attr, os.path.join(self.tmp.name, name))

    def tearDown(self):
        for attr, val in self._orig.items():
            setattr(handlers, attr, val)
        self.tmp.cleanup()

    def run_update(self, upd):
        fake, shown = FakeCall(), []
        handlers.handle_update(upd, make_ctx(fake, shown, MENUS))
        return fake, shown

    def _read(self, name):
        path = os.path.join(self.tmp.name, name)
        if not os.path.exists(path):
            return {}
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def test_non_admin_harvest_refused_nothing_recorded(self):
        fake, _ = self.run_update(private_msg("/harvest_start " + PAGE,
                                              uid=222, username="student"))
        self.assertTrue(any("Only the admin" in t for t in texts(fake)))
        self.assertEqual(self._read("harvest_state.json"), {})

    def test_start_unknown_page_records_nothing(self):
        fake, _ = self.run_update(private_msg("/harvest_start bogus-page",
                                              uid=ADMIN["id"],
                                              username=ADMIN["username"]))
        self.assertTrue(any("Unknown Notes page" in t for t in texts(fake)))
        self.assertEqual(self._read("harvest_state.json"), {})

    def test_start_stop_status_cycle(self):
        fake, _ = self.run_update(private_msg("/harvest_start " + PAGE,
                                              uid=ADMIN["id"],
                                              username=ADMIN["username"]))
        self.assertTrue(any("Harvest on: " + PAGE in t for t in texts(fake)))
        state = self._read("harvest_state.json")
        self.assertEqual(state[str(ADMIN["id"])]["page_key"], PAGE)

        fake, _ = self.run_update(private_msg("/harvest_status",
                                              uid=ADMIN["id"],
                                              username=ADMIN["username"]))
        self.assertTrue(any("Harvest on: " + PAGE in t for t in texts(fake)))

        fake, _ = self.run_update(private_msg("/harvest_stop",
                                              uid=ADMIN["id"],
                                              username=ADMIN["username"]))
        self.assertTrue(any("Harvest stopped: " + PAGE in t
                            for t in texts(fake)))
        self.assertTrue(any("0 file(s)" in t for t in texts(fake)))
        self.assertEqual(self._read("harvest_state.json"), {})

    def test_status_without_harvest(self):
        fake, _ = self.run_update(private_msg("/harvest_status",
                                              uid=ADMIN["id"],
                                              username=ADMIN["username"]))
        self.assertTrue(any("No harvest running" in t for t in texts(fake)))

    def test_direct_attach_bypasses_queue_and_dedupes(self):
        self.run_update(private_msg("/harvest_start " + PAGE,
                                    uid=ADMIN["id"],
                                    username=ADMIN["username"]))
        # Two distinct files + a duplicate of the first.
        self.run_update(private_doc("fid-1", "MEG-5.pdf",
                                    uid=ADMIN["id"],
                                    username=ADMIN["username"]))
        self.run_update(private_doc("fid-2", "MEG-5-notes.pdf",
                                    uid=ADMIN["id"],
                                    username=ADMIN["username"]))
        fake, _ = self.run_update(private_doc("fid-1", "MEG-5.pdf",
                                              uid=ADMIN["id"],
                                              username=ADMIN["username"]))
        mapping = self._read("notes_files.json")
        self.assertEqual(len(mapping.get(PAGE, [])), 2)
        self.assertEqual(mapping[PAGE][0]["file_name"], "MEG-5.pdf")
        # Nothing went into the pending queue.
        self.assertEqual(self._read("pending_files.json"), {})
        # No per-file chatter: only the start reply so far (progress
        # notes fire every 50 files).
        self.assertFalse(any("Got MEG-5" in t for t in texts(fake)))

    def test_no_harvest_document_uses_queue(self):
        fake, _ = self.run_update(private_doc("fid-9", "plain.pdf",
                                              uid=ADMIN["id"],
                                              username=ADMIN["username"]))
        pending = self._read("pending_files.json")
        self.assertEqual(len(pending.get(str(ADMIN["id"]), [])), 1)
        self.assertTrue(any("Got plain.pdf" in t for t in texts(fake)))
        self.assertEqual(self._read("notes_files.json"), {})


if __name__ == "__main__":
    unittest.main()
