#!/usr/bin/env python3
"""Unit tests for codex_auto_resume.py."""

import unittest
from pathlib import Path
import tempfile
import json
import time
import datetime

import codex_auto_resume as car


class TestCodexAutoResume(unittest.TestCase):
    def test_format_countdown(self):
        self.assertEqual(car.format_countdown(0), "00:00:00")
        self.assertEqual(car.format_countdown(-10), "00:00:00")
        self.assertEqual(car.format_countdown(59), "00:00:59")
        self.assertEqual(car.format_countdown(60), "00:01:00")
        self.assertEqual(car.format_countdown(3665), "01:01:05")
        self.assertEqual(car.format_countdown(5 * 3600), "05:00:00")

    def test_state_load_save(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_state = Path(tmpdir) / "state.json"
            orig_state = car.STATE_FILE
            car.STATE_FILE = tmp_state
            try:
                self.assertEqual(car.load_state(), {})
                test_data = {"test_session:1234": {"resumed_for_reset": 123456789}}
                car.save_state(test_data)
                loaded = car.load_state()
                self.assertEqual(loaded, test_data)
            finally:
                car.STATE_FILE = orig_state

    def test_inspect_screen_detection_strict(self):
        orig_run = car.subprocess.run

        class MockResult:
            def __init__(self, stdout):
                self.stdout = stdout
                self.returncode = 0

        try:
            # 1. Normal screen with quota readout
            car.subprocess.run = lambda *args, **kwargs: MockResult("5h 77% left · weekly 81% left\n")
            limited, reset = car.inspect_screen_for_limits("dummy")
            self.assertFalse(limited)

            # 2. Scrollback mentioning 'usage limit' casually in instructions/git log
            casual_scrollback = (
                "Commit 6531047: feat(codex): auto-resume watcher on quota reset\n"
                "Fixing usage limit issue in executor regulations...\n"
                "Remaining tasks: check for 0% left in other files\n"
            )
            car.subprocess.run = lambda *args, **kwargs: MockResult(casual_scrollback)
            limited, reset = car.inspect_screen_for_limits("dummy")
            self.assertFalse(limited)

            # 3. Explicit active rate limit error banner
            dummy_screen_limit = "You've hit your usage limit. Please try again at 11:30 PM.\n"
            car.subprocess.run = lambda *args, **kwargs: MockResult(dummy_screen_limit)
            limited, reset = car.inspect_screen_for_limits("dummy")
            self.assertTrue(limited)
            self.assertGreater(reset, 0)

            # 4. Status line with 5h 0% left
            dummy_screen_zero = "Codex status: 5h 0% left · resets at 19:04\n"
            car.subprocess.run = lambda *args, **kwargs: MockResult(dummy_screen_zero)
            limited, reset = car.inspect_screen_for_limits("dummy")
            self.assertTrue(limited)
            self.assertGreater(reset, 0)
        finally:
            car.subprocess.run = orig_run

    def test_cmd_check_two_phase_state_machine(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_state = Path(tmpdir) / "state.json"
            orig_state = car.STATE_FILE
            orig_get_records = car.get_session_records
            orig_resume = car.resume_session
            car.STATE_FILE = tmp_state

            resumed_targets = []
            car.resume_session = lambda target, pid, reason="": resumed_targets.append((target, pid)) or True

            now = time.time()
            future_reset = int(now + 1800)  # resets in 30 minutes

            # Mock session actively rate limited
            mock_session = {
                "target": "e2-codex",
                "pid": 12345,
                "rate_limited": True,
                "resets_at": future_reset,
                "5h_used": 100.0,
                "weekly_used": 10.0,
                "seconds_remaining": 1800,
                "status": "RATE_LIMITED",
                "cwd": "/home/rog/test",
                "tty": "pts/0",
            }
            car.get_session_records = lambda: [mock_session]

            try:
                # Phase 1: Session is waiting for future reset
                ret = car.cmd_check()
                self.assertEqual(ret, 2)  # code 2 means sessions waiting
                self.assertEqual(len(resumed_targets), 0)
                state = car.load_state()
                self.assertIn("e2-codex:12345", state)
                self.assertEqual(state["e2-codex:12345"]["waiting_for_reset"], future_reset)

                # Phase 2: Time has passed reset + 15 seconds
                mock_session["resets_at"] = int(now - 20)  # reset 20s ago
                state["e2-codex:12345"]["waiting_for_reset"] = mock_session["resets_at"]
                car.save_state(state)

                ret = car.cmd_check()
                self.assertEqual(len(resumed_targets), 1)
                self.assertEqual(resumed_targets[0], ("e2-codex", 12345))
                state = car.load_state()
                self.assertEqual(state["e2-codex:12345"]["resumed_for_reset"], mock_session["resets_at"])

                # Phase 3: Immediate subsequent check while still rate-limited on screen
                # Must NOT send resume again!
                ret = car.cmd_check()
                self.assertEqual(len(resumed_targets), 1)  # Still 1, no duplicate resume

                # Phase 4: Session quota reset propagates (rate_limited becomes False)
                mock_session["rate_limited"] = False
                mock_session["5h_used"] = 0.0
                ret = car.cmd_check()
                self.assertEqual(ret, 0)
                state = car.load_state()
                self.assertNotIn("e2-codex:12345", state)  # Cleaned up
            finally:
                car.STATE_FILE = orig_state
                car.get_session_records = orig_get_records
                car.resume_session = orig_resume

    def test_rollout_null_primary_bucket_does_not_clobber_codex_quota(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            rollout = Path(tmpdir) / "rollout-test.jsonl"
            db_path = Path(tmpdir) / "state_5.sqlite"
            import sqlite3
            con = sqlite3.connect(db_path)
            con.execute("CREATE TABLE threads (id TEXT, rollout_path TEXT, title TEXT, cwd TEXT, updated_at INT)")
            con.execute(
                "INSERT INTO threads VALUES (?, ?, ?, ?, ?)",
                ("11111111-1111-1111-1111-111111111111", str(rollout), "test", "/tmp/proj", 100),
            )
            con.commit()
            con.close()

            events = [
                {
                    "payload": {
                        "type": "token_count",
                        "rate_limits": {
                            "limit_id": "codex",
                            "primary": {"used_percent": 100.0, "resets_at": 1795863843},
                            "secondary": {"used_percent": 31.0, "resets_at": 1796403177},
                            "rate_limit_reached_type": None,
                        },
                    }
                },
                {
                    "payload": {
                        "type": "token_count",
                        "rate_limits": {
                            "limit_id": "premium",
                            "primary": None,
                            "secondary": None,
                            "rate_limit_reached_type": None,
                        },
                    }
                },
            ]
            rollout.write_text("\n".join(json.dumps(e) for e in events) + "\n")

            orig_codex_home = car.CODEX_HOME
            car.CODEX_HOME = Path(tmpdir)
            try:
                info = car.get_thread_info_for_proc({
                    "cmd_str": "codex resume 11111111-1111-1111-1111-111111111111",
                    "cwd": "/tmp/proj",
                })
                self.assertEqual(info["primary_used_percent"], 100.0)
                self.assertEqual(info["resets_at"], 1795863843)
                self.assertEqual(info["secondary_used_percent"], 31.0)
            finally:
                car.CODEX_HOME = orig_codex_home


if __name__ == "__main__":
    unittest.main()
