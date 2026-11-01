"""Student credential access — pure, testable logic.

No Telegram API, no Telethon, no file I/O in the core functions:
callers load/save credential_access.json themselves. This keeps the
module safe to build and test while the grabber is running.

Rules (see credential_access_spec.md):
- Free access = 90 days, trial INCLUDED (no extra trial on top).
- After free access ends, mandatory credentials are required.
- Learner interface never shows the credential value; admin view does.
- Phone-only access needs 10 qualified referrals (same university
  and course, referred user credential-verified, no self-referral).
"""

import re
import time

FREE_DAYS = 90
ACCESS_DAYS = 90
SECONDS_PER_DAY = 86400
QUALIFIED_REFERRALS_NEEDED = 10


def _clean_digits(value):
    if value is None:
        return ""
    s = str(value).strip()
    if s.startswith("+91"):
        s = s[3:]
    elif s.startswith("91") and len(s) == 12:
        s = s[2:]
    return re.sub(r"[\s\-]", "", s)


def check_enrollment(value):
    """Return cleaned enrollment number, or None if format fails.

    Conservative format only: digits, 8-12 long. No university-specific
    format is invented.
    """
    s = _clean_digits(value)
    if re.fullmatch(r"\d{8,12}", s):
        return s
    return None


def check_phone(value):
    """Return cleaned 10-digit Indian mobile, or None if format fails."""
    s = _clean_digits(value)
    if re.fullmatch(r"[6-9]\d{9}", s):
        return s
    return None


def check_credential(credential_type, value):
    """credential_type: 'enrollment' or 'phone'. Returns cleaned value or None."""
    if credential_type == "enrollment":
        return check_enrollment(value)
    if credential_type == "phone":
        return check_phone(value)
    return None


def new_free_record(now=None):
    now = int(now if now is not None else time.time())
    return {
        "university": None,
        "course": None,
        "semester": None,
        "credential_type": None,
        "credential_value": None,
        "free_start": now,
        "free_end": now + FREE_DAYS * SECONDS_PER_DAY,
        "access_start": None,
        "access_end": None,
        "status": "free",
        "referral_count": 0,
        "referrer_id": None,
    }


def is_allowed(record, now=None):
    """True if quiz/notes/assignments/daily may be served now."""
    if not record:
        return False
    now = int(now if now is not None else time.time())
    if record.get("status") == "free":
        return now <= int(record["free_end"])
    if record.get("status") == "credentialed":
        end = record.get("access_end")
        return end is not None and now <= int(end)
    return False


def needs_credentials(record, now=None):
    """True only when the free period is over and no valid credentialed access exists."""
    return not is_allowed(record, now)


def approve_credential(record, university, course, semester,
                       credential_type, value, now=None):
    """Approve instantly on a valid credential. Returns (record, error).

    On error the record is unchanged. On success the credential value
    is stored (admin-only) and access runs 90 days from approval.
    Phone-only approval is NOT granted here — use
    record_qualified_referral() until 10 are reached, then approve.
    """
    cleaned = check_credential(credential_type, value)
    if cleaned is None:
        return record, "invalid_format"
    if credential_type == "phone":
        return record, "phone_needs_referrals"
    now = int(now if now is not None else time.time())
    record.update({
        "university": university,
        "course": course,
        "semester": semester,
        "credential_type": credential_type,
        "credential_value": cleaned,
        "access_start": now,
        "access_end": now + ACCESS_DAYS * SECONDS_PER_DAY,
        "status": "credentialed",
    })
    return record, None


def start_phone_path(record, university, course, semester, value, now=None):
    """Start a phone-only record: format-checked, but NOT approved yet."""
    cleaned = check_phone(value)
    if cleaned is None:
        return record, "invalid_format"
    record.update({
        "university": university,
        "course": course,
        "semester": semester,
        "credential_type": "phone",
        "credential_value": cleaned,
        "status": "phone_pending_referral",
        "referral_count": int(record.get("referral_count") or 0),
    })
    return record, None


def record_qualified_referral(referrer_record, referred_record, now=None):
    """Count one qualified referral, if it qualifies.

    Qualifies only when: referrer is on the phone path, referred user
    is credentialed, same university and course, and not a self-referral
    (checked by the caller via ids — this function compares records only).
    Returns (referrer_record, approved_bool).
    """
    if referrer_record.get("status") != "phone_pending_referral":
        return referrer_record, False
    if referred_record.get("status") != "credentialed":
        return referrer_record, False
    if (referred_record.get("university") != referrer_record.get("university")
            or referred_record.get("course") != referrer_record.get("course")):
        return referrer_record, False
    referrer_record["referral_count"] = int(referrer_record.get("referral_count") or 0) + 1
    if referrer_record["referral_count"] >= QUALIFIED_REFERRALS_NEEDED:
        now = int(now if now is not None else time.time())
        referrer_record["access_start"] = now
        referrer_record["access_end"] = now + ACCESS_DAYS * SECONDS_PER_DAY
        referrer_record["status"] = "credentialed"
        return referrer_record, True
    return referrer_record, False


def learner_view(record):
    """Learner-safe view: NO credential value, ever. Erased from the
    learner interface, as the user instructed 28 Oct 2026."""
    if not record:
        return {}
    return {
        "university": record.get("university"),
        "course": record.get("course"),
        "semester": record.get("semester"),
        "status": record.get("status"),
        "access_end": record.get("access_end"),
        "free_end": record.get("free_end"),
    }


def admin_view(record):
    """Admin-only view: full record, including credential value."""
    return dict(record) if record else {}
