"""Free-tier AI answer routing — pure logic, no network in tests.

Order (see ai_answer_spec.md):
  1. course_info.json first (16 Mission Academy courses)
  2. verified university facts (caller-supplied, never invented here)
  3. free-tier AI API (env only: AI_PROVIDER, AI_API_KEY, AI_MODEL)
  4. honest fallback: doubt saved, no fake answer, phone only for
     human-needed cases.

This module never invents deadlines, fees, eligibility, prices or
batch dates. If a question asks for one of those and no verified
fact was supplied, the answer must say it is unverified.
"""

import json
import os
import re

CONTACT_PHONE = "+91 86066 56245"
CONTACT_SITE = "www.missionacademys.com"
SENSITIVE_WORDS = ("deadline", "last date", "fee", "fees", "price",
                    "eligibility", "eligible", "batch", "admission date",
                    "exam date", "result date")


def is_malayalam(text):
    return bool(re.search(r"[\u0d00-\u0d7f]", text or ""))


def load_courses(path):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    if isinstance(data, dict):
        return data.get("courses", [])
    return data


def find_course(query, courses):
    """Return the course entry whose name words best match the query.

    Matching is on whole words, case-insensitive, ignoring punctuation
    and the generic word 'course/courses'. Returns None on no match.
    """
    q = re.sub(r"[^a-z0-9 ]", " ", (query or "").lower())
    q_words = set(q.split()) - {"course", "courses"}
    best, best_score = None, 0
    for entry in courses:
        name = entry.get("name", "")
        n = re.sub(r"[^a-z0-9 ]", " ", name.lower())
        n_words = set(n.split()) - {"course", "courses"}
        score = len(q_words & n_words)
        # Require at least 2 matching words, or the full short name.
        if score > best_score and (score >= 2 or n_words <= q_words):
            best, best_score = entry, score
    return best


def needs_human(question):
    """True only for cases that genuinely need a human at Mission Academy."""
    q = (question or "").lower()
    return any(w in q for w in (
        "pay", "payment", "paid", "refund", "my admission", "my application",
        "my document", "document problem", "certificate problem",
        "my enrollment", "my result", "personal"))


def route_question(question, courses, verified_fact=None):
    """Decide the answer route. Returns (route, course_or_fact).

    Routes: 'course', 'verified', 'ai', 'human', 'unverified_sensitive'.
    """
    if not (question or "").strip():
        return "human", None
    course = find_course(question, courses)
    if course:
        return "course", course
    if verified_fact:
        return "verified", verified_fact
    if needs_human(question):
        return "human", None
    q = (question or "").lower()
    if any(w in q for w in SENSITIVE_WORDS):
        return "unverified_sensitive", None
    return "ai", None


def course_answer(course):
    """Short bot answer from a course_info entry. No price unless confirmed."""
    price = course.get("price", "") if course.get("price_status") == "confirmed" else "Price: ask Mission Academy counsellor"
    lines = [course.get("name", ""), "", course.get("overview", ""), ""]
    for point in (course.get("structure") or [])[:5]:
        lines.append(f"- {point}")
    lines += ["", price, f"Admissions and guidance: {CONTACT_PHONE} | {CONTACT_SITE}"]
    return "\n".join(lines)


def fallback_message(question, lang_malayalam=False):
    if lang_malayalam:
        return ("AI ഇപ്പോൾ ഫ്രീ ലിമിറ്റിൽ ആണ്, അതുകൊണ്ട് ഉത്തരം നൽകാൻ "
                "കഴിയുന്നില്ല. നിങ്ങളുടെ ചോദ്യം സേവ് ചെയ്തിട്ടുണ്ട്, "
                "Mission Academy WhatsApp വഴി ഫോളോ അപ്പ് ചെയ്യും.")
    return ("The AI is at its free limit right now, so I can't answer "
            "that yet. Your question is saved, and Mission Academy "
            "will follow up on WhatsApp.")


def ai_config_from_env(env=None):
    env = os.environ if env is None else env
    return {
        "provider": env.get("AI_PROVIDER", ""),
        "model": env.get("AI_MODEL", ""),
        "has_key": bool(env.get("AI_API_KEY")),
    }


def call_ai_available(env=None):
    """True only when a provider, model and key are all configured.

    No network call here — the live caller does the HTTP request.
    Tests and the bot use this gate so a missing key never produces
    a fake answer.
    """
    cfg = ai_config_from_env(env)
    return bool(cfg["provider"] and cfg["model"] and cfg["has_key"])


def call_free_ai(question, env=None):
    """Call the configured free-tier AI. Returns (answer_text, error).

    Gemini free tier only in this first build (provider 'gemini'):
    POST generateContent with the key as a query param, stdlib urllib
    only, 20s timeout. Any other provider, missing key, HTTP error,
    rate limit or unparsable reply returns (None, error) — the caller
    must then use the honest fallback, never a fake answer.
    The prompt instructs the model to explain generally, in the
    question's language, and to NOT invent university deadlines,
    fees, eligibility or prices.
    """
    import urllib.request
    import urllib.error
    env = os.environ if env is None else env
    cfg = ai_config_from_env(env)
    if not cfg["has_key"] or cfg["provider"] != "gemini" or not cfg["model"]:
        return None, "not_configured"
    lang = "Malayalam" if is_malayalam(question) else "English"
    prompt = (
        "You are a helpful study assistant for Mission Academy students. "
        "Answer the question clearly, from every relevant aspect, with "
        "examples, in " + lang + ". "
        "Do NOT invent university deadlines, fees, eligibility, prices, "
        "batch dates, jobs or exam results. If you do not know a "
        "university fact, say you do not know it. Question: " + question
    )
    url = ("https://generativelanguage.googleapis.com/v1beta/models/"
           + cfg["model"] + ":generateContent?key=" + env["AI_API_KEY"])
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode("utf-8")
    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        parts = data["candidates"][0]["content"]["parts"]
        text = "".join(p.get("text", "") for p in parts).strip()
        return (text, None) if text else (None, "empty_reply")
    except Exception as e:
        return None, str(e)[:200]
