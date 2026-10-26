# Mission Academy — Old Combined Bot (@Shafeeque_rayaroth_bot) — FadeHost deploy pack

Prepared 21 Oct 2026. Clean copy of `~/workspace/telegram-bot/` (code + data only;
no logs, locks, caches, or backups). Python standard library only — no pip packages.

## FadeHost settings

- Deploy source: this folder pushed to a GitHub repository, connected in FadeHost
  (GitHub App one-click, or paste repo URL).
- Runtime: Python (detected via requirements.txt).
- Environment variable: `TELEGRAM_BOT_TOKEN` = the bot's current @BotFather token
  (paste it in the FadeHost dashboard only — never in chat, never in the repo).
- Start command: `echo "$TELEGRAM_BOT_TOKEN" | python3 bot.py --token-stdin`
  (also in the Procfile as a worker entry).
- Mode: long polling — no webhook, no port, no public address needed.

## Verify after deploy

In Telegram open @Shafeeque_rayaroth_bot → /start → IGNOU → UG → any course →
Notes. Menus should load. Then also stop any copy of the bot still running on
the Muse VM so only the hosted instance polls.

## Notes

- FadeHost apps run on a read-only filesystem, so this copy (bot.py /
  handlers.py only — the originals in ~/workspace/telegram-bot are unchanged)
  writes its runtime state (bot.lock, subscribers.json, pending_files.json,
  notes_files.json) under /data when /data exists and is writable, and next
  to the code otherwise. Attached Notes PDFs and subscribers live in /data,
  so they survive restarts; a redeploy keeps /data too.
- Free tier (verified on fadehost.com, 19–21 Oct 2026): one always-on app per
  verified account, 256 MB RAM, 3 GB disk, no card, no sleep timer.

## Backup route (noted 21 Oct)

Node 24 + npx exist on the Muse VM, so the FadeHost CLI is a viable
backup if the panel flow stalls: Mohammed runs/approves `npx fadehost login`
(a code he approves in the panel), then the CLI can create the app from a
repo URL, deploy, restart, tail logs and set env vars from the VM side.
The TELEGRAM_BOT_TOKEN value itself should still be entered by him (panel),
not passed through the VM.
