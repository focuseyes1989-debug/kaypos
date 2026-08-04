"""Configure Telegram settings for ZAY POS from the command line."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from utils.telegram_service import (  # noqa: E402
    TelegramConfig,
    save_telegram_config,
    send_test_message,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Configure Telegram integration.")
    parser.add_argument("--token", default=os.environ.get("TELEGRAM_BOT_TOKEN", ""))
    parser.add_argument("--chat-id", default=os.environ.get("TELEGRAM_CHAT_ID", ""))
    parser.add_argument("--disabled", action="store_true", help="Save config as disabled.")
    parser.add_argument("--test", action="store_true", help="Send a test message after saving.")
    args = parser.parse_args()

    token = args.token.strip()
    chat_id = args.chat_id.strip()

    if not token:
        token = input("Telegram bot token: ").strip()
    if not chat_id:
        chat_id = input("Telegram chat ID: ").strip()

    config = TelegramConfig(
        enabled=not args.disabled,
        bot_token=token,
        chat_id=chat_id,
    )
    env_path = save_telegram_config(config)
    print(f"Telegram settings saved to {env_path}")

    if args.test and config.enabled:
        print(send_test_message())

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
