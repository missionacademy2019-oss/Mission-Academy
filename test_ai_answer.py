"""Tests for ai_answer.py — pure logic only, no network, no key."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ai_answer import (
    load_courses, find_course, route_question, course_answer,
    fallback_message, call_ai_available,
)

COURSES = load_courses(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "course_info.json"))


def test_courses_load():
    assert len(COURSES) == 16, len(COURSES)
    print("courses_load ok (16)")


def test_find_course():
    assert find_course("Tell me about English B.Ed", COURSES)["name"] == "English- B.Ed"
    assert find_course("What is KTET CTET SET?", COURSES)["name"] == "KTET, CTET, SET"
    assert find_course("Explain photosynthesis", COURSES) is None
    print("find_course ok")


def test_route_order():
    route, obj = route_question("Tell me about English B.Ed", COURSES)
    assert route == "course"
    route, _ = route_question("What is the IGNOU admission deadline?", COURSES)
    assert route == "unverified_sensitive", route
    route, _ = route_question("Explain Shakespeare's sonnets", COURSES)
    assert route == "ai", route
    route, _ = route_question("I paid but my admission is stuck", COURSES)
    assert route == "human", route
    print("route_order ok")


def test_course_answer_no_invented_price():
    bed = find_course("English B.Ed", COURSES)
    assert "89,000" in course_answer(bed)
    med = find_course("English MEd", COURSES)
    ans = course_answer(med)
    assert "89,000" not in ans and "ask Distance Learners counsellor" in ans
    print("course_price_rule ok")


def test_ai_gate_and_fallback():
    assert not call_ai_available({})
    assert call_ai_available({"AI_PROVIDER": "gemini", "AI_MODEL": "x", "AI_API_KEY": "k"})
    assert "free limit" in fallback_message("q")
    print("ai_gate_fallback ok")


if __name__ == "__main__":
    test_courses_load()
    test_find_course()
    test_route_order()
    test_course_answer_no_invented_price()
    test_ai_gate_and_fallback()
    print("ALL AI ANSWER TESTS PASSED")
