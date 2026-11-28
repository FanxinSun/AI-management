#!/usr/bin/env python3
"""Unit tests for codex_auto_resume.py."""

import unittest
from pathlib import Path
import tempfile
import json
import time

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

    def test_inspect_screen_detection(self):
        # Mocking screen text parser logic
        dummy_screen_1 = "Some normal screen output\n5h 77% left · weekly 81% left\n"
        # Mock subprocess
        orig_run = car.subprocess.run

        class MockResult:
            def __init__(self, stdout):
                self.stdout = stdout
                self.returncode = 0

        try:
            car.subprocess.run = lambda *args, **kwargs: MockResult(dummy_screen_1)
            limited, reset = car.inspect_screen_for_limits("dummy")
            self.assertFalse(limited)

            dummy_screen_limit = "You've hit your usage limit. Please try again at 11:30 PM.\n"
            car.subprocess.run = lambda *args, **kwargs: MockResult(dummy_screen_limit)
            limited, reset = car.inspect_screen_for_limits("dummy")
            self.assertTrue(limited)
            self.assertGreater(reset, 0)
        finally:
            car.subprocess.run = orig_run


if __name__ == "__main__":
    unittest.main()
