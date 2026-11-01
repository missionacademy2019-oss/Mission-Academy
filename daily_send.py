"""Daily Study push sender.

Sends today's quiz poll + notes card to PRIVATE subscribers only.
A subscriber with a banked subject gets that subject's quiz and note,
always labelled with its course code (e.g. "Today's Notes —
BEVAE-181", with the block and topic inside the card). A subscriber
with no subject, or a subject with no bank yet, gets nothing — never
a generic card, and never a push to a group (28 Oct 2026 rule).
Run once a day (e.g. 8 AM IST) via cron once the working bot token is in
the Secure Vault — until then this script has no token to send with.

Usage: python3 daily_send.py --token-stdin < token.txt
"""
import argparse
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
API = "https://api.telegram.org/bot"


def call(token: str, method: str, payload: dict, timeout: int = 15) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(API + token + "/" + method, data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--token-stdin", action="store_true")
    args = ap.parse_args()
    token = sys.stdin.read().strip() if args.token_stdin else ""
    if not token:
        print("no token on stdin", file=sys.stderr)
        return 2
    sys.path.insert(0, HERE)
    import handlers  # reuse today's quiz/notes + subscriber list
    try:
        with open(os.path.join(HERE, "subscribers.json"), encoding="utf-8") as f:
            subs = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        subs = []
    if not subs:
        print("no subscribers")
        return 0
    # subscribers.json may be the old list format or the new dict
    # format (chat_id -> subscription). Normalise to dict items here;
    # handlers.load_subscriptions() does the same migration.
    if isinstance(subs, list):
        subs = {str(cid): {} for cid in subs}
    # No generic quiz/note is loaded for fallback — see the skip rule
    # in the loop below. Unsubscribed or unbanked subjects get nothing.
    sent = 0
    for chat_id, sub in subs.items():
        # PRIVATE ONLY: never push a quiz poll or note to a group or
        # channel (negative chat ids). A group subscriber would notify
        # every member — that is exactly the leak this guard prevents.
        try:
            if int(chat_id) < 0:
                print(f"skipped group/channel subscriber {chat_id} (private only)")
                continue
        except Exception:
            continue
        code = sub.get("subject_code") if isinstance(sub, dict) else None
        quiz = handlers.today_subject_quiz(code) if code else None
        note = handlers.today_subject_note(code) if code else None
        # NO generic fallback: a subscriber with no subject, or a
        # subject with no quiz/note bank yet, gets nothing — never a
        # random quiz on an unrelated topic. Sending nothing is
        # professional; sending a random quiz is not.
        if quiz is None or note is None:
            print(f"skipped {chat_id}: no quiz/note bank for subject {code}")
            continue
        label = f"Today's Quiz — {code}"
        note_text = f"Today's Notes — {code}\n\n{note}"
        try:
            call(token, "sendPoll", {
                "chat_id": chat_id,
                "question": quiz["q"],
                "options": quiz["options"],
                "type": "quiz",
                "correct_option_id": quiz["answer"],
                "explanation": quiz["explanation"],
                "is_anonymous": False,
                "protect_content": True,
            })
            # Plain-text explanation as well as the poll's own text,
            # so the answer is readable without the poll.
            answer_text = quiz["options"][quiz["answer"]] if 0 <= quiz["answer"] < len(quiz["options"]) else ""
            call(token, "sendMessage", {
                "chat_id": chat_id,
                "text": f"{label}\nAnswer: {answer_text}\n{quiz['explanation']}",
                "protect_content": True,
            })
            call(token, "sendMessage", {
                "chat_id": chat_id,
                "text": note_text,
                "protect_content": True,
            })
            sent += 1
        except Exception as exc:  # noqa: BLE001 - one blocked user must not stop the rest
            print(f"failed for {chat_id}: {exc}", file=sys.stderr)
    print(f"sent to {sent}/{len(subs)} subscribers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
