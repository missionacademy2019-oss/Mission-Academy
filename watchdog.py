#!/usr/bin/env python3
"""Watchdog: keep the 3 Distance Learners Telegram bots running.

DRAFT — not applied. Replaces the vault pre-check gate with
start-and-observe (see watchdog-start-and-observe-fix-DRAFT.md).

For each bot:
  1. If a bot.py process is already running in that bot's directory, skip it.
  2. If that bot died with an auth error in the last 60 minutes, skip it
     (cooldown — avoids re-spawning a bot whose vault token is genuinely
     dead every 5 minutes; it is retried once the hour passes).
  3. Otherwise, start `python3 bot.py`, wait 25s, then judge by the bot's
     own behaviour: still running + a `bot: @<username>` line in the NEW
     bot.log lines = up. Exited + 401/Unauthorized in the new lines =
     token truly invalid -> record auth failure, skip for 60 minutes.
     Exited with any other error -> log it, retry next run.

Run every 5 minutes via cron. Safe to run concurrently: the bot's own
single-instance file lock (bot.lock) makes a duplicate exit.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request  # noqa: F401  (kept for parity; not used by the new logic)

BOTS = [
    # (label, directory)
    ("old", os.path.expanduser("~/workspace/telegram-bot")),
    ("ignou", os.path.expanduser("~/workspace/telegram-bot-ignou")),
    ("sgou", os.path.expanduser("~/workspace/telegram-bot-sgou")),
]

STATE_PATH = os.path.expanduser(
    "~/workspace/goals/telegram-bot-auto-restart/hidden_files/"
    "watchdog-auth-failures.json"
)
COOLDOWN_SECS = 3600
OBSERVE_SECS = 25


def is_running(bot_dir: str) -> bool:
    r = subprocess.run(["pgrep", "-f", "python3 bot.py"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return False
    # pgrep -f matches our own watchdog too (it contains "bot.py" in argv);
    # confirm a process whose cwd is the bot dir.
    for pid in r.stdout.split():
        try:
            cwd = os.readlink(f"/proc/{pid}/cwd")
        except OSError:
            continue
        if os.path.realpath(cwd) == os.path.realpath(bot_dir):
            return True
    return False


def load_state() -> dict:
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_state(state: dict) -> None:
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)


def log_size(bot_dir: str) -> int:
    try:
        return os.path.getsize(os.path.join(bot_dir, "bot.log"))
    except OSError:
        return 0


def new_log_lines(bot_dir: str, offset: int) -> str:
    try:
        with open(os.path.join(bot_dir, "bot.log"), "rb") as f:
            f.seek(offset)
            return f.read().decode("utf-8", errors="ignore")
    except OSError:
        return ""


def start_bot(bot_dir: str) -> None:
    log_path = os.path.join(bot_dir, "bot.log")
    log = open(log_path, "ab")
    subprocess.Popen(
        ["python3", "bot.py"], cwd=bot_dir,
        stdout=log, stderr=subprocess.STDOUT,
        start_new_session=True, close_fds=True,
    )
    print(f"  started bot in {bot_dir} (log: {log_path})", flush=True)


def main() -> int:
    state = load_state()
    now = time.time()
    for label, bot_dir in BOTS:
        print(f"[{label}] {bot_dir}", flush=True)
        if is_running(bot_dir):
            print("  already running, skipping", flush=True)
            continue
        last_auth_fail = state.get(label, 0)
        if now - last_auth_fail < COOLDOWN_SECS:
            remaining = int(COOLDOWN_SECS - (now - last_auth_fail))
            print(f"  SKIP: died with an auth error recently; "
                  f"cooling down for {remaining}s more", flush=True)
            continue
        offset = log_size(bot_dir)
        start_bot(bot_dir)
        time.sleep(OBSERVE_SECS)
        new_lines = new_log_lines(bot_dir, offset)
        if is_running(bot_dir):
            if "bot: @" in new_lines:
                print("  UP: process alive and authenticated", flush=True)
            else:
                print("  UP (process alive; no 'bot: @' line in new log "
                      "lines yet — will confirm on next run)", flush=True)
            state.pop(label, None)
        elif "401" in new_lines or "Unauthorized" in new_lines:
            print("  DOWN: auth error (401/Unauthorized) — token truly "
                  "invalid; cooling down 60 min", flush=True)
            state[label] = now
        else:
            print("  DOWN: exited without an auth error; new log lines:\n"
                  + (new_lines.strip() or "(no new log lines)"), flush=True)
    save_state(state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
