"""Entry point for MpaiBot Discord Music Bot."""
import sys
from bot.main import run_bot


if __name__ == "__main__":
    try:
        run_bot()
    except KeyboardInterrupt:
        print("\nMpaiBot shutting down...")
        sys.exit(0)
