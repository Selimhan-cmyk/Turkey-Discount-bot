#!/usr/bin/env python3
"""Print chats that have sent a message to the Telegram bot; never prints the token."""
import json
import os
import sys
import urllib.error
import urllib.request


def main() -> int:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        print("Önce TELEGRAM_BOT_TOKEN ortam değişkenini ayarlayın.", file=sys.stderr)
        return 1
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/getUpdates")
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            data = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        print(f"Telegram API HTTP {exc.code}; tokenı kontrol edin.", file=sys.stderr)
        return 1
    chats = {}
    for update in data.get("result", []):
        msg = update.get("message") or update.get("channel_post") or update.get("edited_message") or {}
        chat = msg.get("chat") or {}
        if chat.get("id") is not None:
            chats[str(chat["id"])] = chat.get("title") or chat.get("username") or chat.get("first_name") or "Telegram sohbeti"
    if not chats:
        print("Sohbet bulunamadı. Botu açıp /start gönderin; grup için botu ekleyip grupta bir mesaj yazın.")
        return 2
    print("Bulunan sohbetler (uygun ID'yi TELEGRAM_CHAT_ID olarak kullanın):")
    for chat_id, label in chats.items():
        print(f"{chat_id}\t{label}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
