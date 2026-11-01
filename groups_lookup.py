"""Group-link lookup — pure logic, no network.

Rule confirmed 28 Oct 2026, 21:47 IST (owner, in reply to the
open-links rule):
- If a member texts ANY course keyword itself, suggest the course's
  Telegram link AND both group links together, according to
  university only.
- That means: match on university + course keyword, not on an exact
  subject code. Return Telegram + WhatsApp links together for that
  course, in one message. Do not require a subscription, do not
  require a subject-code match, and do not dump other universities'
  or other courses' links.
"""

import re


def _words(text):
    return set(re.findall(r"[a-z0-9]+", (text or "").lower()))


def find_groups(query, groups):
    """Return matching group entries for a course keyword in query.

    Match: query contains the programme name words, or a subject code
    belonging to an entry, and the entry's university is the one the
    query names (IGNOU / SGOU) if named, else any university with
    that programme. All matching entries for that programme are
    returned together (Telegram + WhatsApp, group + channel), in
    directory order. Empty list on no keyword match.
    """
    q = (query or "").lower()
    q_words = _words(q)
    # Subject code in query, e.g. meg-01
    codes = set(re.findall(r"\b([a-z]{2,7}-\d{2,3})\b", q))
    # University named in query, if any
    uni = None
    if "ignou" in q_words:
        uni = "ignou"
    elif "sgou" in q_words or "sreenarayana" in q_words:
        uni = "sgou"
    if codes:
        # A subject-code query returns ONLY that subject's links,
        # not every group of its programme (fixed 28 Oct 2026, when
        # IGNOU MAEG subject groups arrived: a MEG-01 query must
        # not dump all 19 MEG subject groups).
        out = [g for g in groups
               if (g.get("subject_code") or "").lower() in codes
               and (uni is None or g.get("university", "").lower() == uni)]
        return out
    matched_programmes = set()
    for g in groups:
        prog_words = _words(g.get("programme", ""))
        if prog_words and prog_words <= q_words:
            matched_programmes.add((g.get("university", "").lower(),
                                    g.get("programme", "").lower()))
    if not matched_programmes:
        return []
    if uni:
        matched_programmes = {p for p in matched_programmes if p[0] == uni}
    # A programme keyword returns the programme-level links only,
    # not every subject group of that programme.
    return [g for g in groups
            if (g.get("university", "").lower(),
                g.get("programme", "").lower()) in matched_programmes
            and not g.get("subject_code")]


def groups_answer(entries):
    """One message with Telegram + WhatsApp links together."""
    if not entries:
        return None
    lines = ["Study groups for this course:"]
    for g in entries:
        platform = {"telegram_group": "Telegram group",
                    "telegram_channel": "Telegram channel",
                    "whatsapp_group": "WhatsApp group",
                    "whatsapp_channel": "WhatsApp channel"}.get(
                        g.get("platform", ""), g.get("platform", ""))
        subj = g.get("subject_code") or g.get("subject_name") or "Course group"
        lines.append(f"- {platform} ({subj}): {g.get('link', '')}")
    lines.append("Tap a link to join. WhatsApp groups are opened in WhatsApp.")
    return "\n".join(lines)
