---
name: color
description: Sets or inspects the color of the session name badge in the CLI status bar. Usage: /color <name> (e.g. /color yellow, /color cyan, /color magenta).
---

# Color Slash Command

Use this skill when the user runs `/color` or asks to change the color of the session badge.

## Instructions
1. Parse the requested color argument from the prompt (e.g., `yellow`, `cyan`, `blue`, `magenta`, `purple`, `green`, `red`, `orange`, `gray`, `white`).
2. Run the command:
   ```bash
   python3 ~/.gemini/antigravity-cli/color.py <color>
   ```
3. Inform the user that the session badge color has been updated.
