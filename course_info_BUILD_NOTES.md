# Course-info knowledge base — build notes

Source: `~/workspace/website/elite-course-copy.md`
Output: `~/workspace/telegram-bot/course_info.json`
Built: 28 Oct 2026, in parallel, grabber-safe — no Telethon run, no bot
polling, no change to `handlers.py`, nothing uploaded, shared, or redeployed.

## 16 courses included (website order, names exactly as on missionacademys.com)

1. Mission Rehab
2. English- B.Ed
3. English - MEd
4. UG. - D.El.Ed (source heading: "UG - D.El.Ed")
5. TESOL/TEFL, IELTS/OET
6. English- U.G
7. Diploma, Certificate
8. English- NET
9. Research Assistant
10. Functional English- U.G
11. H.S.S classes
12. School Subjects
13. English AI Courses
14. KTET, CTET, SET
15. English Spoken Courses
16. Publications

Each entry has: name, overview (short, from the source overview),
structure (5 blueprint points, shortened), faqs (6 Q&A, shortened),
contact (+91 86066 56245, www.missionacademys.com), price,
price_status, detail_status.

## Prices stripped

- KEPT (confirmed): English- B.Ed — 89,000/- for one year only.
- STRIPPED (all PROPOSED, unconfirmed — figures are deliberately NOT
  repeated here): English - MEd, UG. - D.El.Ed, TESOL/TEFL, IELTS/OET,
  English- U.G, Diploma, Certificate, English- NET, Research Assistant,
  Functional English- U.G, H.S.S classes, School Subjects,
  English AI Courses, KTET, CTET, SET, English Spoken Courses,
  Publications, Mission Rehab.
  All 15 of those entries say only: "Price: ask Mission Academy
  counsellor" with price_status "on-enquiry".

## Internal material stripped

- Every "INTERNAL ONLY — DO NOT PUBLISH" line removed.
- No university / board / provider curriculum basis is included in the
  output (no TNTEU, IGNOU-based, or IGNOU-pattern strings remain).
- No batch dates, job guarantees, or exam-result guarantees were added.

## Missing / provisional detail — do NOT present as final

- **Mission Rehab** (`detail_status: to_be_confirmed_by_owner`):
  source section exists but is itself marked "deliberately generic and
  must be reviewed by the owner before publishing" — the academy had
  not supplied what Mission Rehab covers. Entry is included only from
  that provisional source text, with a note flagging it for owner
  confirmation.
- **Research Assistant** (`detail_status: to_be_confirmed_by_owner`):
  source section exists, but what it covers was previously flagged as
  still needed from the owner. Same provisional treatment as above.
- **UG. - D.El.Ed**: full section included, but the source itself notes
  its curriculum basis was "NOT specified in the owner's brief" —
  owner to confirm the correct basis before any public use.
- No other course had a missing section; all 16 source sections were
  present. Nothing was invented for any course.

## Verification check (run 28 Oct 2026)

- JSON loads: yes
- Entries: 16
- Each entry: 5 structure points, 6 FAQs
- "PROPOSED PRICE" in output: no
- "INTERNAL ONLY" in output: no
- Comma price figures in output: only 89,000 (English- B.Ed)
- Result: PASS
