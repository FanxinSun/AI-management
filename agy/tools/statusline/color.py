#!/usr/bin/env python3
import sys
import os

COLOR_FILE = os.path.expanduser("~/.gemini/antigravity-cli/session_color")
VALID_COLORS = ["yellow", "cyan", "blue", "magenta", "purple", "green", "red", "orange", "gray", "white"]

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        current = "yellow"
        if os.path.exists(COLOR_FILE):
            try:
                with open(COLOR_FILE, "r") as f:
                    current = f.read().strip().lower()
            except Exception:
                pass
        print(f"Current session badge color: {current}")
        print(f"Usage: /color <name>\nAvailable colors: {', '.join(VALID_COLORS)}")
        return

    color = sys.argv[1].strip().lower().lstrip("/")
    if color not in VALID_COLORS:
        print(f"Unknown color: {color}")
        print(f"Available colors: {', '.join(VALID_COLORS)}")
        sys.exit(1)

    os.makedirs(os.path.dirname(COLOR_FILE), exist_ok=True)
    with open(COLOR_FILE, "w") as f:
        f.write(color + "\n")

    print(f"✓ Session badge color set to: {color}")

if __name__ == "__main__":
    main()
