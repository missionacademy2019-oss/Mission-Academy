"""Admin view tests: owner-only, private-only, invisible to members."""
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import handlers  # noqa: E402


def make_ctx(fake, shown):
    return {"call": fake, "load_menus": lambda: {},
            "show_menu": lambda chat, mid, key, menus: shown.append(key),
            "main_keyboard": lambda: None}


class FakeCall:
    def __init__(self):
        self.calls = []

    def __call__(self, method, payload):
        self.calls.append((method, payload))
        return {"ok": True, "result": {}}


def methods(fake, name):
    return [p for m, p in fake.calls if m == name]


def private_msg(text, uid=111, username="someone"):
    return {"message": {"chat": {"id": uid, "type": "private"},
                        "from": {"id": uid, "username": username},
                        "text": text}}


def callback(data, chat, uid=111, username="someone"):
    return {"callback_query": {"id": "q", "data": data,
                               "from": {"id": uid, "username": username},
                               "message": {"chat": {"id": chat,
                                                    "type": "private" if chat > 0 else "supergroup"},
                                           "message_id": 1}}}


ADMIN = {"id": 999, "username": "Shafeque_rayaroth"}


class AdminTests(unittest.TestCase):
    def test_admin_command_owner_only(self):
        fake, shown = FakeCall(), []
        handlers.handle_update(private_msg("/admin", uid=ADMIN["id"],
                                           username=ADMIN["username"]),
                               make_ctx(fake, shown))
        self.assertTrue(any("Admin" in s["text"] for s in methods(fake, "sendMessage")))
        # Non-admin gets "Unknown command", never an admin hint.
        fake2, shown2 = FakeCall(), []
        handlers.handle_update(private_msg("/admin", uid=222, username="student"),
                               make_ctx(fake2, shown2))
        self.assertTrue(any("Unknown command" in s["text"] for s in methods(fake2, "sendMessage")))
        self.assertFalse(any("Admin" in s["text"] for s in methods(fake2, "sendMessage")))

    def test_admin_callbacks_owner_only(self):
        fake, shown = FakeCall(), []
        handlers.handle_update(callback("menu:admin-doubts", 999,
                                        uid=ADMIN["id"], username=ADMIN["username"]),
                               make_ctx(fake, shown))
        self.assertTrue(any("doubts" in s["text"].lower() for s in methods(fake, "sendMessage")))
        fake2, shown2 = FakeCall(), []
        handlers.handle_update(callback("menu:admin-doubts", 222,
                                        uid=222, username="student"),
                               make_ctx(fake2, shown2))
        self.assertEqual(methods(fake2, "sendMessage"), [])

    def test_non_admin_pdf_not_queued(self):
        # Non-admin document in private chat must not be queued for Notes.
        fake, shown = FakeCall(), []
        upd = {"message": {"chat": {"id": 222, "type": "private"},
                           "from": {"id": 222, "username": "student"},
                           "document": {"file_id": "f1", "file_name": "x.pdf"}}}
        handlers.handle_update(upd, make_ctx(fake, shown))
        self.assertTrue(any("Only the admin" in s["text"] for s in methods(fake, "sendMessage")))


if __name__ == "__main__":
    unittest.main()
