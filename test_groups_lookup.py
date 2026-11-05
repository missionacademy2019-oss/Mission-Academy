"""Tests for groups_lookup.py — pure logic, no network."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from groups_lookup import find_groups, groups_answer

GROUPS = [
    {"university": "IGNOU", "programme": "MAEG", "subject_code": "",
     "platform": "telegram_group", "link": "https://t.me/maeg"},
    {"university": "IGNOU", "programme": "MAEG", "subject_code": "",
     "platform": "whatsapp_group", "link": "https://chat.whatsapp.com/maeg"},
    {"university": "IGNOU", "programme": "MAEG", "subject_code": "MEG-01",
     "platform": "telegram_group", "link": "https://t.me/meg01"},
    {"university": "IGNOU", "programme": "MAEG", "subject_code": "MEG-01",
     "platform": "whatsapp_group", "link": "https://chat.whatsapp.com/maeg01"},
    {"university": "IGNOU", "programme": "MBA", "subject_code": "",
     "platform": "telegram_group", "link": "https://t.me/mba"},
    {"university": "SGOU", "programme": "MAEG", "subject_code": "",
     "platform": "telegram_group", "link": "https://t.me/sgou-maeg"},
]


def test_keyword_returns_both_platforms():
    out = find_groups("IGNOU MAEG group please", GROUPS)
    assert len(out) == 2, out
    assert any("t.me" in g["link"] for g in out)
    assert any("whatsapp" in g["link"] for g in out)
    print("keyword_both_platforms ok")


def test_university_only_scoping():
    out = find_groups("MAEG", GROUPS)
    # No university named: all MAEG programmes, both universities
    assert len(out) == 3, out
    out = find_groups("SGOU MAEG", GROUPS)
    assert len(out) == 1 and out[0]["university"] == "SGOU", out
    print("university_scoping ok")


def test_subject_code_keyword():
    out = find_groups("I need MEG-01 notes", GROUPS)
    assert len(out) == 2, out
    print("subject_code ok")


def test_subject_code_does_not_dump_programme():
    # Real directory shape: a programme group + many subject groups.
    # A MEG-06 query must return only MEG-06, not the whole programme.
    real = [
        {"university": "IGNOU", "programme": "MAEG", "subject_code": "",
         "platform": "whatsapp_group", "link": "https://chat.whatsapp.com/maeg"},
        {"university": "IGNOU", "programme": "MAEG", "subject_code": "MEG-06",
         "platform": "whatsapp_group", "link": "https://chat.whatsapp.com/meg06"},
        {"university": "IGNOU", "programme": "MAEG", "subject_code": "MEG-07",
         "platform": "whatsapp_group", "link": "https://chat.whatsapp.com/meg07"},
        {"university": "IGNOU", "programme": "MAEG", "subject_code": "",
         "platform": "telegram_group", "link": "https://t.me/ignoumegchapter"},
    ]
    out = find_groups("MEG-06 group", real)
    assert len(out) == 1 and out[0]["link"].endswith("meg06"), out
    out = find_groups("IGNOU MAEG group", real)
    assert len(out) == 2 and all(not g["subject_code"] for g in out), out
    print("subject_code_no_dump ok")


def test_no_match_no_dump():
    assert find_groups("hello", GROUPS) == []
    ans = groups_answer(find_groups("IGNOU MAEG", GROUPS))
    assert "t.me/maeg" in ans and "chat.whatsapp.com/maeg" in ans
    print("no_dump ok")


if __name__ == "__main__":
    test_keyword_returns_both_platforms()
    test_university_only_scoping()
    test_subject_code_keyword()
    test_subject_code_does_not_dump_programme()
    test_no_match_no_dump()
    print("ALL GROUP LOOKUP TESTS PASSED")
