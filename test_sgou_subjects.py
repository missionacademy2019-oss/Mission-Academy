#!/usr/bin/env python3
"""Unit tests for SGOU subject buttons (launched 1 Nov 2026).

Stdlib only, no network: ctx["call"] is a recording stub. The tests use
the real menus.json and sgou_materials.json shipped with the bot, so
they also pin the structure the builder produced. Run with:
    python3 test_sgou_subjects.py
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import handlers

HERE = Path(__file__).resolve().parent


class FakeCall:
    """Records calls; getChatMember answers from a per-user status map."""

    def __init__(self, member_status=None):
        self.calls = []
        self.member_status = member_status or {}

    def __call__(self, method, payload, timeout=15):
        self.calls.append((method, payload))
        if method == "getChatMember":
            status = self.member_status.get(payload.get("user_id"), "left")
            return {"ok": True, "result": {"status": status}}
        return {"ok": True, "result": {}}

    def texts(self, method="sendMessage"):
        return [p.get("text", "") for m, p in self.calls if m == method]


def make_ctx(fake):
    return {
        "call": fake,
        "load_menus": lambda: {},
        "main_keyboard": lambda: {},
        "show_menu": lambda *a: None,
        "bot_id": 999,
    }


def make_cb(data, user_id=111):
    return {"id": "cb1", "from": {"id": user_id},
            "message": {"chat": {"id": 222}, "message_id": 5},
            "data": data}


class TestSgouMenus(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.menus = json.load(open(HERE / "menus.json", encoding="utf-8"))
        cls.materials = json.load(open(HERE / "sgou_materials.json",
                                       encoding="utf-8"))

    def test_sgou_menu_links_subject_tree(self):
        targets = [b["to"] for row in self.menus["sgou"]["buttons"]
                   for b in row]
        self.assertIn("sgou-subjects", targets)
        self.assertIn("sgou-subjects", self.menus)
        back = self.menus["sgou-subjects"]["buttons"][-1][0]["to"]
        self.assertEqual(back, "sgou")

    def test_every_subject_button_target_exists(self):
        missing = []
        for key, menu in self.menus.items():
            if not key.startswith("sgou-sub-"):
                continue
            for row in menu.get("buttons", []):
                for b in row:
                    if b["to"] not in self.menus and \
                            not b["to"].startswith("sgou-mat-"):
                        missing.append((key, b["to"]))
        self.assertEqual(missing, [])

    def test_callback_data_within_telegram_limit(self):
        over = [k for k in self.menus if k.startswith("sgou-sub")
                or k.startswith("sgou-mat")
                if len(("menu:" + k).encode("utf-8")) > 64]
        self.assertEqual(over, [])

    def test_pending_programmes_have_no_subject_pages(self):
        pending_slugs = ("mal-fyug", "bcom22", "ma-econ25", "ma-polsci24",
                         "ma-pubadmin23")
        bad = [k for k in self.menus
               if any(k == "sgou-sub-" + s or
                      k.startswith("sgou-sub-" + s + "-")
                      for s in pending_slugs)]
        self.assertEqual(bad, [])
        for slug in pending_slugs:
            self.assertIn("sgou-subjects-pending-" + slug, self.menus)
            self.assertIn("Content coming soon.",
                          self.menus["sgou-subjects-pending-" + slug]["text"])

    def test_launched_counts(self):
        self.assertEqual(len(self.materials["programmes_launched"]), 35)
        self.assertEqual(len(self.materials["programmes_pending"]), 5)
        self.assertEqual(len(self.materials["subjects"]), 1627)


class TestSgouMaterialsData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.materials = json.load(open(HERE / "sgou_materials.json",
                                       encoding="utf-8"))

    def test_urls_are_remote_and_no_local_paths(self):
        blob = json.dumps(self.materials, ensure_ascii=False)
        self.assertNotIn("/home/", blob)
        self.assertNotIn("workspace/", blob)
        for subj in self.materials["subjects"].values():
            urls = ([subj["slm_url"]] if subj["slm_url"] else []) \
                + [p["url"] for p in subj["pyq"]] \
                + [v["url"] for v in subj["videos"]]
            for url in urls:
                self.assertTrue(url.startswith("https://"), url)
                self.assertTrue("cloudfront.net" in url
                                or "youtube.com" in url, url)

    def test_subject_pages_reference_real_material_ids(self):
        menus = json.load(open(HERE / "menus.json", encoding="utf-8"))
        refs = set()
        for key, menu in menus.items():
            if not key.startswith("sgou-sub-"):
                continue
            for row in menu.get("buttons", []):
                for b in row:
                    if b["to"].startswith("sgou-mat-"):
                        refs.add(b["to"])
        for ref in refs:
            kind, ident = ref[len("sgou-mat-"):].split("-", 1)
            if kind == "semassign":
                self.assertIn(ident, self.materials["semesters"], ref)
            else:
                self.assertIn(ident, self.materials["subjects"], ref)


class TestSgouHandler(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Subject ids shift when programmes are added, so resolve the
        # ids these tests need from the built data instead of pinning
        # them: one subject with SLM, one with no SLM, one with videos.
        mats = json.load(open(HERE / "sgou_materials.json",
                              encoding="utf-8"))
        cls.sid_slm = next(sid for sid, s in mats["subjects"].items()
                           if s["slm_url"])
        cls.code_slm = mats["subjects"][cls.sid_slm]["code"]
        cls.sid_no_slm = next(sid for sid, s in mats["subjects"].items()
                              if not s["slm_url"])
        cls.sid_video = next(sid for sid, s in mats["subjects"].items()
                             if s["videos"])

    def setUp(self):
        handlers._MEMBER_CACHE.clear()
        handlers._SGOU_MAT_CACHE.clear()

    def test_notes_gated_for_non_member(self):
        fake = FakeCall(member_status={111: "left"})
        handlers._handle_sgou_material(
            make_cb("menu:sgou-mat-notes-" + self.sid_slm),
            make_ctx(fake), "sgou-mat-notes-" + self.sid_slm)
        joined = "\n".join(fake.texts())
        button_texts = " ".join(
            b.get("text", "")
            for _, p in fake.calls
            for row in (p.get("reply_markup") or {}).get("inline_keyboard", [])
            for b in row)
        self.assertIn("Join Mission Academy Channel", button_texts)
        self.assertIn("join our Mission Academy channel", joined)
        self.assertNotIn("cloudfront.net", joined)

    def test_notes_sent_for_member(self):
        fake = FakeCall(member_status={111: "member"})
        handlers._handle_sgou_material(
            make_cb("menu:sgou-mat-notes-" + self.sid_slm),
            make_ctx(fake), "sgou-mat-notes-" + self.sid_slm)
        joined = "\n".join(fake.texts())
        self.assertIn("cloudfront.net", joined)
        self.assertIn(self.code_slm, joined)

    def test_notes_coming_soon_when_no_slm(self):
        # A subject with no SLM: coming soon wins over the gate,
        # so a non-member is NOT shown a Join prompt for empty material.
        fake = FakeCall(member_status={111: "left"})
        handlers._handle_sgou_material(
            make_cb("menu:sgou-mat-notes-" + self.sid_no_slm),
            make_ctx(fake), "sgou-mat-notes-" + self.sid_no_slm)
        joined = "\n".join(fake.texts())
        self.assertIn("Content coming soon.", joined)
        self.assertNotIn("Join Mission Academy Channel", joined)

    def test_papers_sent_for_member(self):
        fake = FakeCall(member_status={111: "member"})
        handlers._handle_sgou_material(
            make_cb("menu:sgou-mat-papers-" + self.sid_slm),
            make_ctx(fake), "sgou-mat-papers-" + self.sid_slm)
        self.assertIn("cloudfront.net", "\n".join(fake.texts()))

    def test_videos_preview_on_and_not_gated(self):
        fake = FakeCall(member_status={111: "left"})
        handlers._handle_sgou_material(
            make_cb("menu:sgou-mat-videos-" + self.sid_video),
            make_ctx(fake), "sgou-mat-videos-" + self.sid_video)
        video_calls = [p for m, p in fake.calls if m == "sendMessage"
                       and "youtube.com" in p.get("text", "")]
        self.assertTrue(video_calls)
        self.assertEqual(video_calls[0]["link_preview_options"],
                         {"is_disabled": False})

    def test_semester_assignments_for_member(self):
        fake = FakeCall(member_status={111: "member"})
        handlers._handle_sgou_material(
            make_cb("menu:sgou-mat-semassign-afsal23-s1"),
            make_ctx(fake), "sgou-mat-semassign-afsal23-s1")
        self.assertIn("cloudfront.net", "\n".join(fake.texts()))

    def test_unknown_id_degrades_to_coming_soon(self):
        fake = FakeCall(member_status={111: "member"})
        handlers._handle_sgou_material(make_cb("menu:sgou-mat-notes-s9999"),
                                       make_ctx(fake), "sgou-mat-notes-s9999")
        self.assertIn("Content coming soon.", "\n".join(fake.texts()))


if __name__ == "__main__":
    unittest.main()
