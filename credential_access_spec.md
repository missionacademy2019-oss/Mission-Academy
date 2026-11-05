# Student credential system — spec (confirmed 28 Oct 2026, 20:43 IST)

## What the user confirmed
- Trial period is INCLUDED in the 3-month access. There is no separate
  trial on top of 3 months. Total free access = 3 months from first
  access (first subscription / first credential record), then the gate.
- Build right now, in parallel, ONLY if it does not affect the grabber.
  Building code does not: no Telethon process, no bot polling, no
  grabber restart, no live-bot change until a tested redeploy.
- Erase from the learner interface ONLY. After verification, the learner
  never sees their own phone / enrollment number again in the bot
  (no echo, no /myaccess value, no My Subscription value). At the same
  time, save it privately in admin-only storage, retrievable by the
  owner via /admin, deletable on expiry or on owner order.
- If a specific storage field is needed, the user offered to build it
  himself — the fields below are the proposal; if he builds a different
  store, this module's field names are the contract to match.

## Gate rule
- status "free": now <= free_end (free_start + 90 days = 3 months).
  Quiz, notes, assignments and daily push are allowed.
- status "credentialed": now <= access_end (approval + 90 days).
  Allowed.
- Otherwise ("expired", or free period over with no credential):
  quiz, notes, assignments and daily push are BLOCKED with a prompt
  to complete /credentials. No silent fail, no random content.
- Existing subscribers with no credential record: first gate check
  creates a free record with free_start = now (never backdated, never
  guessed from old files).

## Mandatory fields (after free period)
- university: IGNOU or SGOU (must match the subscription if present)
- course / programme: as in the subscription, e.g. MAEG, MBA
- semester: 1-8, or Year 1/2 where the programme is year-based
  (stored as the string the user entered, e.g. "Sem 2" / "Year 1")
- credential, exactly one of:
  - enrollment number: digits only, 8-12 digits after stripping
    spaces and hyphens. No other format is invented.
  - phone: 10 digits, starting 6-9, after stripping +91 / spaces /
    hyphens. Phone-only path: access is NOT granted until 10
    QUALIFIED referrals are recorded (see below).

## Phone-only referral rule
- A referral counts only when the referred user completes credential
  verification with the SAME university and course as the referrer.
- Referrer is identified by Telegram user id passed in /start payload
  or entered in the credential flow. No referral is counted on a
  mere bot start, a group join, or a self-referral.
- At 10 qualified referrals, phone-only access is approved instantly
  (same instant-approval rule as enrollment), for 90 days.

## Storage (admin-only)
File: credential_access.json in the bot directory (same writable
pattern as subscribers.json / bot_starters.json).
Record per Telegram user id (chat id, as string):
  university, course, semester, credential_type,
  credential_value (raw phone / enrollment — NEVER shown to the
  learner, NEVER logged, NEVER echoed),
  free_start, free_end, access_start, access_end,
  status, referral_count, referrer_id.
Learner-safe view (for /myaccess and My Subscription):
  university, course, semester, status, access_end date ONLY.
  No credential_value, no phone, no enrollment.
Admin view (/admin, owner only): full record, including
  credential_value, for retrieval on owner ask, and delete on
  expiry / owner order.

## What is NOT in this build
- No change to force-join (channel + bot start only, no credentials).
- No change to the 6-file redeploy bundle unless the user says to
  include this module in that redeploy. This module is built and
  tested separately; wiring it into handlers.py is a second, explicit
  step, with its own test run.
- No Telethon, no grabber touch, no live bot polling in tests.
