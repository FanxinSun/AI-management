# macOS iMessage & `chat.db` Automation Guide

**Written 2026-11-28** from operational discoveries during an iMessage automation task on macOS Sequoia (15.7.9). This guide documents the database schema, sandboxing rules, delivery failure modes, and the reliable method for reading, staging, sending multi-attachment messages, and verifying real delivery.

---

## 1. The Database Layer (`~/Library/Messages/chat.db`)

macOS stores all iMessage and SMS history in an SQLite database at `~/Library/Messages/chat.db`.

### Key Tables & Relationships

- `chat`: Represents conversations (1-on-1 or group).
  - `ROWID`: Internal integer ID.
  - `chat_identifier`: Target handle (e.g., phone number `+86...` or email `user@example.com`).
  - `guid`: Format `iMessage;-;user@example.com` or `SMS;-;+86...`.
  - `service_name`: `iMessage` or `SMS`.
- `handle`: Participant contact handles.
  - `id`: Phone number or email.
  - `service`: `iMessage` or `SMS`.
- `message`: Message metadata and body.
  - `ROWID`: Internal message ID.
  - `guid`: Unique message UUID.
  - `date`: Nanoseconds since Apple Cocoa epoch (`2001-01-01 00:00:00 UTC`). To convert to Unix epoch: `date / 1000000000 + 978307200`.
  - `is_from_me`: `1` for outgoing, `0` for incoming.
  - `error`: Error code (`0` = no error; `3` = upload/permission failed; `39` = connection/daemon terminated).
  - `is_sent`: `1` when acknowledged by Apple iMessage servers; `0` if pending, draft, or failed.
  - `is_delivered`: `1` when delivery receipt is received from recipient device.
- `attachment`: Stored file attachments.
  - `filename`: POSIX path on disk (usually `~/Library/Messages/Attachments/...`).
  - `mime_type`, `transfer_name`, `total_bytes`.
  - `transfer_state`: `5` = transferred/uploaded; `6` = transfer error; `0` = unhandled.
- **Join Tables**:
  - `chat_message_join`: Links `chat.ROWID` (`chat_id`) to `message.ROWID` (`message_id`).
  - `message_attachment_join`: Links `message.ROWID` (`message_id`) to `attachment.ROWID` (`attachment_id`).

### The Consecutive-Message Photo Split Phenomenon

When an iOS or macOS user sends a batch of photos (e.g. 9 photos selected together in Photos.app), iMessage frequently splits the batch across adjacent consecutive message bubbles within seconds or minutes (e.g., 1 photo in bubble $N$ at 01:57, and 8 photos in bubble $N+1$ at 02:10).

> [!WARNING]
> Never query solely `SELECT max(ROWID) FROM message WHERE ...` when the user asks for "all images of the last message".
> Always inspect the preceding contiguous cluster from the same sender within a short time window (e.g., 15–20 minutes) to avoid dropping part of a split batch.

---

## 2. Sandbox Traps & System Daemon Constraints

iMessage on macOS relies on sandboxed background daemons:
- `imagent`: Core messaging agent daemon.
- `IMTransferAgent`: Background MMCS file transfer agent responsible for uploading attachments to iCloud / Apple content gateways (`gateway-asset.icloud-content.com`).
- `identityservicesd`: Handles IDS / APNs push connection authentication.

### The Hidden-Directory TCC Sandbox Block

`imagent` and `IMTransferAgent` run under macOS sandbox profiles (`com.apple.imagent`). They have access to:
1. The user's `~/Library/Messages/Attachments/` directory.
2. Standard user content folders (e.g. `~/Pictures/`, `~/Downloads/`).

**They DO NOT have permission to read arbitrary dot-directories or agent runspaces** (such as `~/.gemini/`, `~/.claude/`, or temporary CLI caches).

When an agent stages an image file in `~/.gemini/...` and passes it to Messages, `imagent` fails during copy/upload with:
```text
imagent: (libcopyfile.dylib) open on /Users/.../.gemini/.../IMG_0713.JPG: Operation not permitted
```
This causes the transfer to hang and fail with `error: 3` ("Not Delivered").

> [!IMPORTANT]
> Always stage outbound attachments in standard directories such as `~/Pictures/` before attempting to send them.

---

## 3. Why AppleScript `send file` Fails on Modern macOS (Sonoma / Sequoia)

In modern macOS versions, executing AppleScript dictionary commands:
```applescript
tell application "Messages"
    send (POSIX file "/path/to/file.jpg") to targetChat
end tell
```
or targeting a `participant` creates the message and attachment entries in `chat.db`, but fails the XPC authorization handshake with `IMTransferAgent`. The transfer never uploads, leaving the bubble stuck with a red exclamation mark ("Not Delivered") in the UI.

Furthermore, sending files one-by-one via AppleScript creates separate message bubbles for each image rather than a single unified photo album.

---

## 4. The Reliable Automation Route: Native UI Pasteboard Compose

The most reliable, sandboxing-safe method to send one or multiple attachments via iMessage on modern macOS:

1. **Stage Files in Standard Location**:
   Copy files to `~/Pictures/<folder>/`.
2. **Load URLs onto General Pasteboard**:
   Use Swift / AppKit to populate `NSPasteboard.general` with file URLs (`public.file-url` / `«class furl»`).
3. **Focus Compose Field in Target Window**:
   Locate the chat window for the recipient and focus the accessibility element `AXTextField` with description `"Message"`.
4. **Paste and Send (`Cmd+V` + `Return`)**:
   Synthesize `Cmd+V` (virtual key `0x09`) to let Messages ingest all files through its native UI pipeline, then synthesize `Return` (virtual key `0x24`).

### Complete Swift Script Pattern

```swift
import AppKit
import ApplicationServices
import Foundation

// 1. Stage file URLs on NSPasteboard
let filePaths = [
    "/Users/username/Pictures/images/IMG_0001.JPG",
    "/Users/username/Pictures/images/IMG_0002.JPG"
]
let urls = filePaths.map { URL(fileURLWithPath: $0) }
let pb = NSPasteboard.general
pb.clearContents()
pb.writeObjects(urls as [NSURL])

// 2. Activate Messages
guard let app = NSWorkspace.shared.runningApplications.first(where: { $0.bundleIdentifier == "com.apple.MobileSMS" }) else {
    exit(1)
}
app.activate()
Thread.sleep(forTimeInterval: 0.5)

// 3. Find target window and compose element
let appElement = AXUIElementCreateApplication(app.processIdentifier)
var windowsRef: CFTypeRef?
AXUIElementCopyAttributeValue(appElement, kAXWindowsAttribute as CFString, &windowsRef)
guard let windows = windowsRef as? [AXUIElement] else { exit(1) }

let targetWindow = windows.first(where: {
    var titleRef: CFTypeRef?
    AXUIElementCopyAttributeValue($0, kAXTitleAttribute as CFString, &titleRef)
    return (titleRef as? String ?? "").contains("<RecipientName>")
}) ?? windows.first!

func findCompose(element: AXUIElement) -> AXUIElement? {
    var roleRef: CFTypeRef?; AXUIElementCopyAttributeValue(element, kAXRoleAttribute as CFString, &roleRef)
    var descRef: CFTypeRef?; AXUIElementCopyAttributeValue(element, kAXDescriptionAttribute as CFString, &descRef)
    if (roleRef as? String) == "AXTextField" && (descRef as? String) == "Message" { return element }
    var childrenRef: CFTypeRef?
    if AXUIElementCopyAttributeValue(element, kAXChildrenAttribute as CFString, &childrenRef) == .success,
       let children = childrenRef as? [AXUIElement] {
        for child in children {
            if let found = findCompose(element: child) { return found }
        }
    }
    return nil
}

guard let compose = findCompose(element: targetWindow) else { exit(1) }
AXUIElementSetAttributeValue(compose, kAXFocusedAttribute as CFString, kCFBooleanTrue)

// 4. Paste Cmd+V and Send Return
let src = CGEventSource(stateID: .combinedSessionState)
let vDown = CGEvent(keyboardEventSource: src, virtualKey: 0x09, keyDown: true); vDown?.flags = .maskCommand
let vUp = CGEvent(keyboardEventSource: src, virtualKey: 0x09, keyDown: false); vUp?.flags = .maskCommand
vDown?.post(tap: .cghidEventTap); Thread.sleep(forTimeInterval: 0.05); vUp?.post(tap: .cghidEventTap)

Thread.sleep(forTimeInterval: 1.0)

let retDown = CGEvent(keyboardEventSource: src, virtualKey: 0x24, keyDown: true)
let retUp = CGEvent(keyboardEventSource: src, virtualKey: 0x24, keyDown: false)
retDown?.post(tap: .cghidEventTap); Thread.sleep(forTimeInterval: 0.05); retUp?.post(tap: .cghidEventTap)
```

---

## 5. Daemon Recovery (`killall imagent`)

If `imagent` gets stuck trying to process unreadable sandbox paths from earlier failed attempts, the background upload queue can jam.
- Run `killall imagent`.
- macOS `launchd` restarts the daemon cleanly in < 1 second.
- Any subsequent UI send triggers a fresh `IMTransferAgent` upload task.

---

## 6. Verification Protocol: A Check Must Be Able to Fail

Never claim delivery based on `chat.db` row creation alone:

1. **Database Check (`chat.db`)**:
   - `message.is_sent == 1` (confirmed sent to Apple server).
   - `message.error == 0` (no delivery or transport error).
   - `attachment.transfer_state == 5` (clean MMCS upload completed).
2. **Network Log Check (`IMTransferAgent`)**:
   Verify in `/usr/bin/log show --predicate 'process == "IMTransferAgent"' --last 1m`:
   - `Server Receipt Received`
   - `Uploads complete. All done!` (`response_status=200`).
3. **UI Status Check (Accessibility)**:
   Inspect the target bubble in the Messages accessibility tree:
   - Must contain: `AXHeading | Delivered`
   - Must NOT contain: `AXHeading | Not Delivered` or `Message Send Failure`.
