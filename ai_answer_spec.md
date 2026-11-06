# Free-tier AI for the Telegram bot — spec (chosen 28 Oct 2026, 21:23 IST)

## User decision
- Try a free-tier AI first, accept its limits. No paid API yet.
- Limits accepted: free tiers are rate-limited, slower, may cap daily
  queries, and may be unavailable at peak times. When the AI is
  unavailable or rate-limited, the bot must fall back to its programmed
  answers (course info, MAEG quiz/notes, assignments) — never a dead end,
  and never a fake AI answer.

## Architecture (bot code only, grabber-safe)
- New module: ai_answer.py (to be built, pure logic + HTTP client).
- Flow for Ask a Question / free-text question in private chat only:
  1. Check course_info.json first (16 Distance Learners courses).
     If the question is about one of those courses, answer from that
     verified file, not from the AI.
  2. Else check verified university facts (MAEG, BEVAE-181, IGNOU/SGOU
     prospectus research files). If a verified fact answers it, use it.
  3. Else call the free-tier AI API for a general explanation
     (concept, examples, exam angle, in English or Malayalam as asked).
  4. If the AI call fails, is rate-limited, or returns no answer,
     save the doubt to doubts.json (existing behaviour) and say
     honestly: "AI is at its free limit right now — your question is
     saved, and Distance Learners will follow up on WhatsApp."
  5. Phone number is NEVER the default answer. It appears only for
     human-needed cases: admission payment, personal case, document
     problem, or an unverified university fact.
- No AI answer may invent: IGNOU/SGOU deadlines, fees, eligibility,
  prices (except B.Ed 89,000/- confirmed), batch dates, jobs, or exam
  results. Unverified facts must be flagged as unverified.

## Free-tier provider — first choice, to be confirmed at key step
- First free option to try: Google AI Studio (Gemini) free tier,
  key created by the owner in his own Google account.
- Alternatives if Gemini free tier does not fit: OpenRouter free models,
  Groq free tier — same adapter interface, provider name + endpoint +
  model name in an env file only, never in code or GitHub.
- API key rule: the owner enters the key directly on FadeHost
  (env var), never in chat, never in GitHub, never in a file that is
  uploaded. Building and testing the adapter does NOT need a real key
  — tests use a mock response.

## What is NOT done yet
- No real API key has been supplied. No live bot change.
- No paid tier, no cost commitment.
- Course-info content is being built in parallel (separate work,
  from elite-course-copy.md, with proposed prices stripped).
- Wiring ai_answer.py into handlers.py is a second, tested step,
  with its own redeploy — not bundled silently into the pending
  6-file redeploy.
