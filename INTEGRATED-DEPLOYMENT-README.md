# SGOU SUBJECT-BUTTON LAUNCH — 1 Nov 2026 (owner chose: launch SGOU today)
This section is NEW and sits on top of the 28 Oct integrated pack below.
The owner explicitly set aside the 28 Oct "one final deployment only
after ALL jobs finish" rule for SGOU on 1 Nov 2026 and chose this launch.

## What changed in this update (source == pack, verified by diff)
- handlers.py — new SGOU material handler (`sgou-mat-*` callbacks):
  Notes / Question Papers / Videos / Semester Assignments for SGOU
  subjects. Materials are sent as CloudFront / YouTube URLs (the host
  cannot read the VM disk). PDF kinds pass the existing force-join
  gate (members of @missionacademy_official; fail-open on check
  errors, exactly as the old Notes handler). YouTube links are NOT
  gated (they are links, not downloads) and are sent with link
  preview ON, per the owner's virtual-content rule.
- menus.json — 5,343 pages (was 3,693): a NEW SGOU subject tree under
  SGOU -> "Subject-wise Materials": Level -> Programme -> Semester ->
  Subject -> Notes / Question Papers / Videos / Assignments. The
  existing SGOU UG/PG semester pages are UNCHANGED (still "Content
  coming soon."). The Universal home screen is UNCHANGED.
- sgou_materials.json (NEW) — the material data the handler reads:
  1,434 subjects, 172 semesters, URLs only, no local file paths.
- test_sgou_subjects.py (source only, NOT in this pack — the pack
  has never carried test files): 14 tests, all passing, plus the
  full existing suite (10 test files, all passing).
- Source backup: telegram-bot/menus.json.pre-sgou-subjects.

## What is live-ready in this update
- 30 SGOU programmes with complete syllabus data, 1,434 subjects:
  BA Afzal-Ul-Ulama 2023, BA Arabic 2022, BA Economics 2023-24,
  BA English FYUGP 2024, BA English Language & Literature 2022,
  BA Hindi 2022, BA History FYUGP 2024-25, BA History 2022,
  BA Malayalam Language & Literature 2022, BA Nano Entrepreneurship
  2024, BA Philosophy 2022, BA Philosophy 2024, BA Political Science
  2024, BA Psychology 2024, BA Sanskrit 2022, BA Sociology FYUGP
  2024, BA Sociology 2022, BBA FYUGP 2024-25, BBA 2022, BCA 2022,
  BCom FYUGP 2024-25, MA Arabic 2023, MA Hindi 2023, MA History 2022,
  MA Philosophy 2023, MA Sanskrit 2023, MA Sociology 2022, MBA 2025,
  MBA 2026, MCom 2023.
- Material wired per subject (exact code match only, nothing guessed):
  SLM links, PYQ links (all 1,007 PYQ PDFs verified on disk 1 Nov),
  YouTube links, semester assignment booklets (64 wired).
  Subjects with no material for a kind honestly show
  "Content coming soon." for that kind. MBA 2026 subjects exist but
  currently have NO material at all (0 SLM, 0 PYQ, 0 videos) — its
  buttons show coming soon throughout.
- NOT launched (pending, honest coming-soon pages only, NO subject
  buttons): 5 PARTIAL programmes (one subject title each still
  missing from extraction) — BA Malayalam FYUGP 2024 (Semester 3
  SGB24PS101VC), BCom 2022 (Semester 6 B21CM03DE), MA Economics 2025
  (Semester 2 M23EC06DC), MA Political Science 2024 (Semester 2
  M23PS06DC), MA Public Administration 2023 (Semester 4 M23PS01CB);
  5 UNREADABLE programmes (scanned-image syllabus PDFs, no text
  layer, no OCR available) — BSc Data Science & Analytics 2024,
  MA English 2022, MA Malayalam 2022, MCA 2025, MCA 2026. Their
  semester assignment booklets (4) and unplaced assignments (9) are
  likewise NOT wired. Unmatched entries overall: SLM 125, PYQ 175,
  YouTube 12, assignments 9 — listed in
  sgou-syllabus/material-mapping-report.md, never forced into a
  subject.

## CRITICAL: this redeploy is NOT SGOU-only
The live bot is ONE codebase (currently the 27 Oct 61c33eb bundle).
This redeploy brings live EVERYTHING in this pack, including the
previously-held 28 Oct items below. The owner accepted this by
choosing the SGOU-today launch.
Going live with this redeploy (previously held since 28 Oct):
  - Quiz private-only guard, no-generic-quiz fallback, BEVAE-181
    fix (generic notes/quizzes retired; environment content now
    under BEVAE-181), owner-only /admin view.
  - Force-join expansion to 47 entries (46 megagroups + 1 channel).
    Ban/restrict in the 23 new groups was NOT re-verified — test
    one clean new-group join after redeploy.
  - IGNOU Batch 1 subject menus (MAAE, MAAUD, MACSR, MADE, MAFCS,
    66 subjects; menus only, no quiz/note banks).
  - AI routing (course info first, verified facts second, free AI
    third) + course_info.json (16 courses; only B.Ed price
    confirmed). General AI answers still need a free-tier Gemini
    key entered directly on FadeHost (never in chat/GitHub).
Still NOT live after this redeploy (present in pack but not wired):
  - Credential gate (credential_access.py is a module only).
  - Group-link keyword lookup (groups_lookup.py + the filled
    groups_directory.json — the 28 Oct note below saying the
    directory was empty is STALE; the file is filled, but the
    handler wiring is still not done).
The IGNOU grabber Batch 1 is still NOT finished, so no IGNOU
grabber material is in this launch.

## How to deploy (owner does this, GitHub writes are 403 for the agent)
1. Upload ALL files in this pack in ONE GitHub upload to
   missionacademy2019-oss/Mission-Academy (replace existing files),
   INCLUDING the new sgou_materials.json.
2. Tap Redeploy once on FadeHost.
3. Test, in a private chat: SGOU -> Subject-wise Materials -> PG ->
   MA Arabic 2023 -> Semester 1 -> one subject -> Notes (PDF link
   arrives only as a @missionacademy_official member; a non-member
   must see the Join prompt), Question Papers, Videos (link preview
   ON), and Semester Assignments. Also test one held-back programme
   page (e.g. MA English 2022) shows coming soon, not subjects.
Until you do 1+2, NOTHING in this update is live. The live bot is
still the 27 Oct 61c33eb bundle.

# INTEGRATED COMBINED DEPLOYMENT — 28 Oct 2026, 21:53 IST

## How to deploy (owner does this, GitHub writes are 403 for the agent)
1. Upload ALL files listed below in ONE GitHub upload to
   missionacademy2019-oss/Mission-Academy (replace existing files).
2. Tap Redeploy once on FadeHost.
3. Test ONE clean new-group join for force-join, and ONE private
   Daily Study quiz/note, before claiming anything is live.
Until you do 1+2, NOTHING in this pack is live. The live bot is
still the 27 Oct 61c33eb bundle.

## Files in this integrated pack (all synced main == pack, 28 Oct 21:53)
- handlers.py — Universal home + private-only quiz/notes + no-random
  fallback + owner-only /admin + force-join 47 + AI routing (course
  info first, verified facts second, free AI third, honest fallback)
  + group-link lookup is BUILT but NOT yet wired into handlers
  (see below).
- menus.json — 3,693 menu pages, including Batch 1 subject menus
  (MAAE 17, MAAUD 10, MACSR 19, MADE 10, MAFCS 10 = 66 subjects).
  Menus alone are NOT quiz/note content.
- quizzes_by_subject.json — MAEG 19 subjects x 5 MCQs = 95, plus
  BEVAE-181 5 quizzes.
- notes_by_subject_topics.json — BEVAE-181 8 topic cards by block.
- notes_by_subject.json — MAEG simple notes.
- daily_send.py — private-only daily push, skips unbanked subjects.
- force-join-assignment-channel-groups.txt — 47 entries:
  46 enforceable megagroups + 1 channel (unenforceable).
- assignment_index.json — IGNOU assignments index, 1,895 codes.
- egyankosh.json — 17 IGNOU programmes, link-only.
- ai_answer.py — free-tier AI routing (Gemini free tier, env key
  only). Works for course-info answers WITHOUT a key; general AI
  answers need AI_PROVIDER + AI_MODEL + AI_API_KEY on FadeHost.
  Key NEVER in chat, NEVER in GitHub.
- course_info.json — 16 missionacademys.com courses, overview +
  structure + 6 FAQs each. ONLY B.Ed price confirmed (89,000/-);
  all other prices stripped to "ask counsellor".
- credential_access.py + spec — 3-month free (trial included),
  then mandatory credentials, learner-interface erasure,
  admin-only storage. MODULE ONLY — gate NOT yet wired into
  handlers.py. Do NOT claim credential gating is live.
- groups_lookup.py + groups_directory.json — keyword rule:
  any course keyword -> Telegram + WhatsApp links together,
  university only, open to anyone. DIRECTORY IS EMPTY —
  awaiting the owner's labelled link list. Lookup is built,
  wiring into handlers is NOT done yet.

## Programme coverage — honest depth, not a blanket claim
FULL Daily Study (quiz + note, private only):
  MEG/MAEG (19 subjects), BEVAE-181 (common AECC).
SUBJECT MENUS ONLY (no quiz/note bank yet):
  MAAE, MAAUD, MACSR, MADE, MAFCS (Batch 1, 66 subjects).
COURSE INFO ONLY (overview/structure/FAQs, no Daily Study):
  16 website courses: Mission Rehab, English B.Ed, English MEd,
  UG D.El.Ed, TESOL/TEFL + IELTS/OET, English UG, Diploma/Certificate,
  English NET, Research Assistant, Functional English UG, HSS classes,
  School Subjects, English AI Courses, KTET/CTET/SET,
  English Spoken Courses, Publications.
  Mission Rehab + Research Assistant are marked to_be_confirmed.
ASSIGNMENTS / LINKS ONLY:
  Many IGNOU programmes via assignment forwarding by course code,
  and eGyankosh links for 17 programmes.
NOT YET AT FULL DEPTH:
  The other 98 verified IGNOU programmes from the 27 Oct research
  (menus may exist, quiz/note banks do not), and SGOU's 30
  programmes (only 2 verified from syllabus PDFs, no subject
  content). Building those programme by programme is the next
  work after this redeploy, in research order (next: MADVS,
  MAEDU, MADJ), not something a single pack copy creates.

## Still needed from the owner
- GitHub upload + FadeHost Redeploy (above).
- Free-tier AI key on FadeHost (for live general AI answers).
- Labelled IGNOU/SGOU group/channel link list (for groups directory).
- What Mission Rehab and Research Assistant cover.
- Prices for the 15 website courses other than B.Ed (if you want
  prices shown at all).
