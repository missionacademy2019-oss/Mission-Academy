#!/usr/bin/env python3
"""Regression tests for the full-coverage IGNOU Notes wiring
(3 Nov 2026): new menus pages exist, are reachable, have valid Back
targets, use one button per row, and the sender's page index resolves
every wired code to exactly one Notes page.

Part (a) runs anywhere (menus.json only). Part (b) needs the grabber
working tree (../telegram-grabber/library-out/) and is skipped when it
is absent (e.g. inside the FadeHost deploy pack).
"""
import json
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
MENUS_PATH = os.path.join(HERE, "menus.json")
GRABBER = os.path.join(HERE, "..", "telegram-grabber")
DECISIONS = os.path.join(GRABBER, "library-out",
                         "notes-coverage-decisions.json")
BACKUP = os.path.join(HERE, "menus.json.pre-coverage-2026-11-03")


def load_menus():
    with open(MENUS_PATH, encoding="utf-8") as f:
        return json.load(f)


def new_keys(menus):
    """Keys added by the coverage build (vs the pre-coverage backup).
    Empty when no backup exists (deploy pack): new-page-scoped tests
    then skip, instead of mis-scoping to the whole menu tree (whose
    entry pages and handler-action targets are legitimately unlinked
    from menus)."""
    if not os.path.isfile(BACKUP):
        return set()
    with open(BACKUP, encoding="utf-8") as f:
        old = json.load(f)
    return set(menus) - set(old)


class TestCoverageMenus(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.menus = load_menus()
        cls.new = new_keys(cls.menus)

    def test_menus_parses_and_has_coverage_pages(self):
        self.assertIn("ignou-common", self.menus)
        self.assertIn("ignou-common-bevae181-notes", self.menus)
        # 420 built notes pages: only checkable against the
        # pre-coverage backup (absent inside the deploy pack)
        if os.path.isfile(BACKUP):
            notes = [k for k in self.new if k.endswith("-notes")]
            self.assertEqual(len(notes), 420)

    def test_every_new_page_reachable(self):
        if not self.new:
            self.skipTest("no pre-coverage backup")
        linked = set()
        for page in self.menus.values():
            for row in page.get("buttons", []):
                for b in row:
                    linked.add(b.get("to"))
        unreached = [k for k in self.new if k not in linked]
        self.assertEqual(unreached, [])

    def test_new_page_back_targets_exist(self):
        if not self.new:
            self.skipTest("no pre-coverage backup")
        bad = []
        for k in self.new:
            for row in self.menus[k].get("buttons", []):
                for b in row:
                    if (b.get("text") or "").startswith("⬅ Back") \
                            and b.get("to") not in self.menus:
                        bad.append((k, b.get("to")))
        self.assertEqual(bad, [])

    def test_one_button_per_row_on_new_pages(self):
        if not self.new:
            self.skipTest("no pre-coverage backup")
        bad = [k for k in self.new
               if any(len(row) != 1
                      for row in self.menus[k].get("buttons", []))]
        self.assertEqual(bad, [])

    def test_new_notes_pages_have_subject_pages(self):
        if not self.new:
            self.skipTest("no pre-coverage backup")
        orphans = [k for k in self.new
                   if k.endswith("-notes") and k[:-6] not in self.menus]
        self.assertEqual(orphans, [])

    def test_no_dead_links_from_new_pages(self):
        if not self.new:
            self.skipTest("no pre-coverage backup")
        dead = []
        for k in self.new:
            for row in self.menus[k].get("buttons", []):
                for b in row:
                    if b.get("to") not in self.menus:
                        dead.append((k, b.get("to")))
        self.assertEqual(dead, [])

    def test_existing_pages_untouched_except_added_buttons(self):
        if not os.path.isfile(BACKUP):
            self.skipTest("no pre-coverage backup")
        with open(BACKUP, encoding="utf-8") as f:
            old = json.load(f)
        for k, page in old.items():
            self.assertEqual(self.menus[k].get("text"), page.get("text"))
            old_tos = {(b.get("text"), b.get("to"))
                       for row in page.get("buttons", []) for b in row}
            new_tos = {(b.get("text"), b.get("to"))
                       for row in self.menus[k].get("buttons", [])
                       for b in row}
            self.assertTrue(old_tos <= new_tos, k)


@unittest.skipUnless(os.path.isfile(DECISIONS),
                     "grabber decisions file absent (deploy pack?)")
class TestSenderPlanMatches(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, GRABBER)
        import harvest_send
        cls.plan, cls.skipped = harvest_send.build_plan()
        with open(DECISIONS, encoding="utf-8") as f:
            cls.decisions = json.load(f)

    def test_plan_pages_match_decisions(self):
        import harvest_send
        menus = load_menus()
        index = harvest_send.build_page_index(menus)
        for code, d in self.decisions.items():
            if d["decision"] == "build":
                # every built code resolves to exactly one Notes page
                norm = harvest_send.norm_code(code)
                self.assertIn(norm, index, code)
        plan_pages = {s["page_key"] for s in self.plan}
        # every existing Notes page with files is in the plan
        for code, d in self.decisions.items():
            if d["decision"] == "existing" and d["files"] > 0:
                self.assertIn(d["page"], plan_pages, code)
        # plan pages == 27 existing + 420 built (no page is left with
        # only bad-disk files, so none drops out of the plan)
        self.assertEqual(len(plan_pages), 447)

    def test_every_plan_page_is_a_notes_page_in_menus(self):
        menus = load_menus()
        for slot in self.plan:
            self.assertTrue(slot["page_key"].endswith("-notes"))
            self.assertIn(slot["page_key"], menus)

    def test_plan_reconciles_with_classification(self):
        total = sum(len(s["files"]) for s in self.plan)
        sk = self.skipped
        # NOTE: second_pass_wired files are already inside total (they
        # sit in the plan slots), so they are NOT added again here.
        recon = (total + sk["unclassified"] + sk["multi_code"]
                 + sk["no_page"] + sk["bad_disk"] + sk["no_join"]
                 + sk["low_unverified"] + sk["large"]
                 + sk["second_pass_no_page"]
                 + sk["second_pass_bad_disk"]
                 + sk["second_pass_no_join"])
        self.assertEqual(recon, 16108)


if __name__ == "__main__":
    unittest.main(verbosity=2)
