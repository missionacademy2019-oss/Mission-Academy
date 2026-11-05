# Groups directory — spec (rule confirmed 28 Oct 2026, 21:32 IST)

## Owner rule
- Send group links to ANYONE who asks for that course.
  No subscription / registration gate for group links.
  (Different from credential-gated quiz/notes/assignments after
  the 3-month free period — group links are open.)

## Entry format
Each entry:
  university: "IGNOU" or "SGOU"
  programme: e.g. "MAEG", "MBA"
  subject_code: e.g. "MEG-01" (or "" for a programme-level group)
  subject_name: e.g. "British Poetry" (or "" if programme-level)
  platform: "telegram_group" | "telegram_channel" |
            "whatsapp_group" | "whatsapp_channel"
  link: full https://t.me/... or https://chat.whatsapp.com/... link
  public_or_private: "public" | "private"
  last_updated: date the owner supplied / confirmed the link

## Bot behaviour (to be wired, not live yet)
- Rule confirmed 28 Oct 2026, 21:47 IST: if a member texts ANY course
  keyword itself, suggest the course's Telegram link AND both group
  links together, according to university only.
- That means: match on university + course keyword, not on an exact
  subject code. A "MAEG" text returns MAEG Telegram + WhatsApp links
  together, in one message. A "MEG-01" text returns that subject's
  Telegram + WhatsApp links together.
- Never dump the whole directory, and never mix universities: an
  IGNOU keyword returns IGNOU links only; if no university is named,
  return that programme's links for both universities, labelled.
- Never guess a subject for an unlabelled link — ask the owner to label it.
- Telegram: tap link to join. WhatsApp: tap link, WhatsApp opens;
  the bot cannot check WhatsApp membership or force a join.
- Private / reset links: if an admin resets an invite, the old link
  dies. The bot cannot auto-refresh it — owner must supply the new
  link, and the directory's last_updated date is shown with the link.

## Source lists already held (not yet in this directory)
- 55 primary Telegram groups (grabber batch 1) — study-material
  groups, not yet labelled by subject in this file.
- 47 force-join groups — assignment-channel gate, not a study-group
  directory. Do not copy force-join entries here without owner
  confirmation that they are also study groups to share.
