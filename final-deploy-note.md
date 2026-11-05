# FINAL deployment — Mission Academy bot (3 Nov 2026)

This zip is the complete, current bot: full-coverage IGNOU Notes wiring
(447 pages, 8,264 files) + harvest mode + the WhatsApp-button fix below.
It supersedes all earlier packs and zips. Nothing in it costs money;
the bot stays on the free tier throughout.

## 1. WhatsApp number fix (the screenshot problem)

Before this fix, the bot printed the bare number `+91 86066 56245` in
its messages, and Telegram auto-linked it to the owner's personal
Telegram profile. That is fixed in this pack:

- No bot message contains the bare number any more (FAQ answers, AI
  fallback, course answers, error fallback — all cleaned).
- Wherever contact is offered, the bot now sends a button instead:
  `📱 +91 86066 56245`, which opens WhatsApp directly at
  `https://wa.me/918606656245`. The number shows as button text, so it
  is never linkified to a Telegram profile.
- The WhatsApp auto-reply receiver (a separate project) is untouched
  and still shows the number in its own messages, which is correct on
  WhatsApp.

## 2. Free-AI-tier setup (the "AI is at its free limit" message)

That message is NOT a bug in the code — it is the honest fallback the
bot sends when the free AI is not configured. The code is already
free-tier-ready (Gemini, stdlib only, no paid service). It answers
only when ALL THREE values are set in FadeHost, otherwise it saves the
question and says so honestly, never faking an answer.

Set these in FadeHost (no key ever goes in chat or in any file):

1. Open the bot app in FadeHost → **Settings** tab → environment
   table (one variable per row, separate name/value boxes).
2. Add three rows:
   - `AI_PROVIDER` = `gemini`
   - `AI_MODEL` = the exact Gemini model name from Google AI Studio
     (free tier)
   - `AI_API_KEY` = your Gemini API key from Google AI Studio
     (free tier — get it at Google AI Studio, never paste it in chat)
3. Tap **Save** — saving redeploys the bot with the new values.
4. Test in a private chat with the bot: ask any question. If it
   answers (instead of the free-limit message), the free AI is live.

If the free-limit message still appears after that, one of the three
values is missing or mistyped (usually the model name) — re-check the
name/value split in the table, not the code.

## 3. Owner taps, in order

1. Upload the contents of `mission-academy-deploy-final.zip` to the
   GitHub repo (same as previous redeploys — Muse cannot write to
   GitHub, connector writes are 403).
2. FadeHost: Redeploy the bot app, wait for it to come back.
3. Set the three AI values above (section 2) and Save, if not done.
4. Verify in a private chat as admin: `/harvest_status` must answer
   "No harvest running" (proves the new code is live). Then ask a
   test question (proves the free AI, if configured) and tap any
   MAEG Notes page as a student (proves the menu pack).
5. Only after step 4, tell Muse to run the sender:
   `python3 ~/workspace/telegram-grabber/harvest_send.py --send --confirm-live`
   It sends MAEG first, then the rest (447 pages, 8,264 files,
   roughly 4–5 hours, resume-safe). Do NOT run the sender before the
   `/harvest_status` check — files sent early would land in the old
   1-hour queue and expire.

## 4. What is in the zip

The full bot app from `fadehost-old-bot/`: `bot.py`, `handlers.py`
(harvest mode + WhatsApp button), `menus.json` (6,526 keys, 1,113
Notes pages), `ai_answer.py` (free-tier Gemini caller + honest
fallback), `course_info.json`, `faqs.json` (number-free answers),
`sgou_materials.json`, `egyankosh.json`, quizzes/notes banks,
`requirements.txt`, `Procfile`, and tests (`test_harvest.py`,
`test_notes_coverage.py`, `test_universal.py`, all passing).

## 5. Still honestly coming-soon after this deploy

- 58 existing subject pages with zero files anywhere in the Library.
- 526 subjects (3,552 files) with no verified placement to build a
  page from, including 29 conflicting ones needing the owner's
  resolution.
- 3,542 unclassified files, 713 multi-code date sheets/guides, and
  2,412 low-confidence files held back rather than risked on the
  wrong button.
- The sender run itself (step 5 above) is what actually fills the
  Notes buttons with files; until it runs, the new pages show the
  honest coming-soon text.
