# Customizing Antigravity CLI (agy) Statusline Blocks and Live Tab Status Animation

This guide explains how to customize the **Antigravity CLI (`agy`)** interface to feature:
1. **The two side-by-side pill blocks at the bottom right**: A dynamic state indicator (`WORKING` / `STOPPED`) and a customizable session title badge (inspired by Claude Code), styled with customizable ANSI colors via a `/color` slash command.
2. **The status "GIF" / live braille spinner animation**: A continuous real-time braille spinner (`⠋⠙⠹⠸⠼...`) in the Terminal tab/window title that animates smoothly during agent execution and survives macOS Terminal tab truncation.

---

## 1. Visual Anatomy & Architecture

### What's on Screen

* **Bottom Statusline (`statusline.py statusline`):**
  * **Left:** Dimmed shortcut hint (`? for shortcuts`).
  * **Center/Right:** Model metadata (`auto · Gemini 3.8 Flash (High) · high`).
  * **Block 1 (State Pill):** High-contrast background pill showing agent activity:
    * When active: Vibrant Amber Gold block with animated frame ` ⠸ WORKING ` (`\033[1;38;2;0;0;0;48;2;245;158;11m`).
    * When idle: Vibrant Green block ` ⏹️ STOPPED ` (`\033[1;38;2;0;0;0;48;2;34;197;94m`).
  * **Block 2 (Session Name Pill):** Far-right colored pill showing the conversation title (`AI-management`), rendered in TrueColor pure black text (`\033[1;38;2;0;0;0;...m`) on bright backgrounds and crisp white text (`\033[1;38;2;255;255;255;...m`) on dark backgrounds to ensure high contrast regardless of terminal theme overrides (such as Tokyo Night mapping ANSI `1;30` to slate gray `#565f89`). Its color is configurable on the fly (e.g. Red `\033[1;38;2;255;255;255;48;2;239;68;68m`).
* **Terminal Tab / Window Title ("Status GIF", `statusline.py title`):**
  * Displays `⠸ AI-management ⠸` while the agent is thinking or running commands, actively cycling through braille frames every 120ms.
  * Transitions to `⏹️ AI-management` when the agent is idle.

### How `agy` Hook System Works

Antigravity CLI natively supports external command hooks in `~/.gemini/antigravity-cli/settings.json`:
* `statusLine`: Executed to render the single-row CLI status footer.
* `title`: Executed to update the terminal window/tab title.

Whenever the agent state changes, `agy` pipes a JSON payload via standard input (`stdin`) to the configured script:

```json
{
  "terminal_width": 98,
  "conversation_title": "AI-management",
  "agent_state": "working",
  "model": {
    "display_name": "Gemini 3.8 Flash (High)",
    "effort": "high"
  },
  "cycle_mode": "auto"
}
```

---

## 2. Implementing the Two Bottom-Right Blocks

The statusline hook renders a single row spanning the full terminal width without line wrapping.

### Dynamic Padding & Layout

To keep the blocks aligned flush to the bottom right:
1. The script strips ANSI escape codes to measure the exact printable character width:
   ```python
   def strip_ansi(s):
       return re.sub(r"\033\[[0-9;]*m", "", s)
   ```
2. The padding between the left text (`? for shortcuts`) and the right section is calculated dynamically:
   ```python
   spaces_count = max(2, term_width - left_len - right_len)
   print(f"{left_str}{' ' * spaces_count}{right_str}")
   ```

### Status & Session Pills

```python
# Status pill (24-bit TrueColor high contrast)
if is_working:
    status_pill = f"\033[1;38;2;0;0;0;48;2;245;158;11m {frame} WORKING \033[0m"
elif title:
    status_pill = f"\033[1;38;2;0;0;0;48;2;34;197;94m ⏹️ STOPPED \033[0m"

# Session badge (color read from ~/.gemini/antigravity-cli/session_color)
if title:
    badge_color = get_color_code()
    title_pill = f"{badge_color} {title} \033[0m"
    right_sections.append(title_pill)
```

---

## 3. Implementing the Status "GIF" (Live Tab Animation)

### The Problem: Static Hook Invocations

In `agy`, the `title` command is triggered only once at the beginning of an agent turn and once at completion. If a script simply outputs a single braille character (`⠸`), the title freezes on that frame throughout the execution—it does not animate.

### The Solution: Background Daemon Animator

To achieve fluid, continuous animation:
1. **Detect Controlling TTY:**
   The script inspects the parent process (`ps -p $PPID -o tty=`) or standard descriptors to find the exact terminal device (e.g., `/dev/ttys000`).
2. **Spawn a Detached Daemon:**
   When `is_working == True`, `statusline.py` forks a daemon process (`statusline.py __daemon__ <tty> <title> <pid_file>`) in a new process session:
   ```python
   subprocess.Popen(
       [sys.executable, os.path.abspath(__file__), "__daemon__", tty_dev, title, pid_file],
       stdout=subprocess.DEVNULL,
       stderr=subprocess.DEVNULL,
       stdin=subprocess.DEVNULL,
       start_new_session=True,
   )
   ```
3. **120ms Braille Frame Loop:**
   The daemon loops over `SPINNERS = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]`, writing standard OSC terminal title escape sequences (`\033]0;...\007\033]1;...\007\033]2;...\007`) directly into the controlling `/dev/tty` file:
   ```python
   while time.time() - start_time < 1800:
       frame = SPINNERS[i % len(SPINNERS)]
       disp = f"{frame} {title} {frame}" if title else f"{frame} agy {frame}"
       tty.write(f"\033]0;{disp}\007\033]1;{disp}\007\033]2;{disp}\007")
       tty.flush()
       time.sleep(0.12)
       i += 1
   ```
4. **Surviving macOS Terminal Tab Truncation:**
   In Terminal.app, tabs are displayed as `~ — <Title> — agy`. When multiple tabs are open, Terminal preserves the trailing process name and left-truncates the title (`...`). By wrapping the title with spinners on **both sides** (`⠸ AI-management ⠸`), the trailing spinner stays visible even if the left is truncated.
5. **Clean Termination:**
   When `is_working` becomes `False`, the main process reads the PID file `/tmp/agy_anim_<tty>.pid`, sends `SIGTERM`, removes the lock files, and writes `⏹️  <title>` to the terminal title.

---

## 4. Dynamic Badge Coloring via `/color`

To allow changing the session badge color interactively during an active session without modifying code:

1. **Helper Script (`color.py`):**
   Accepts color names and writes them into `~/.gemini/antigravity-cli/session_color`:
   ```bash
   ~/.gemini/antigravity-cli/color.py red
   ```
2. **Supported Palette:**
   `yellow`, `cyan`, `blue`, `magenta`, `purple`, `green`, `red`, `orange`, `gray`, `white`.
3. **Slash Command Integration:**
   A custom skill is defined in `~/.gemini/config/skills/color/SKILL.md`:
   ```markdown
   ---
   name: color
   description: Sets or inspects the color of the session name badge in the CLI status bar. Usage: /color <name> (e.g. /color yellow, /color cyan, /color magenta).
   ---

   # Color Slash Command
   Use this skill when the user runs `/color` or asks to change the color of the session badge.
   ```
   Now typing `/color red` or `/color yellow` immediately updates the session badge on the next refresh.

---

## 5. Step-by-Step Installation

The necessary files are provided in the `agy-statusline/` directory of this repository.

### Step 1: Install Statusline and Color Scripts

```bash
mkdir -p ~/.gemini/antigravity-cli
cp agy-statusline/statusline.py ~/.gemini/antigravity-cli/statusline.py
cp agy-statusline/color.py ~/.gemini/antigravity-cli/color.py
chmod +x ~/.gemini/antigravity-cli/statusline.py ~/.gemini/antigravity-cli/color.py
```

### Step 2: Install `/color` Slash Command Skill

```bash
mkdir -p ~/.gemini/config/skills/color
cp agy-statusline/skills/color/SKILL.md ~/.gemini/config/skills/color/SKILL.md
```

### Step 3: Configure `settings.json`

Add the `statusLine` and `title` hooks to `~/.gemini/antigravity-cli/settings.json`:

```json
{
  "statusLine": {
    "type": "command",
    "command": "/path/to/.gemini/antigravity-cli/statusline.py statusline",
    "enabled": true
  },
  "title": {
    "type": "command",
    "command": "/path/to/.gemini/antigravity-cli/statusline.py title",
    "enabled": true
  }
}
```
*(Replace `/path/to` with your actual `$HOME` path).*

---

## 6. Usage & Verification

1. **Rename Conversation:**
   Run `/rename <session_name>` (e.g. `/rename AI-management`). The name immediately displays in the bottom-right badge and tab title.
2. **Change Badge Color:**
   Run `/color red` or `/color yellow`. The badge instantly reflects the chosen color.
3. **Observe Live Animation:**
   Run any command or ask a question. The tab title actively spins through `⠋⠙⠹⠸⠼...`, and the bottom right displays `⠸ WORKING`. When execution completes, it switches to `⏹️ STOPPED`.
