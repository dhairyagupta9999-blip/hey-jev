"""Phase 6 Test Suite: Open-Vocabulary PC Control ("Do Anything" Layer).

Sub-phase 6a:
  - App index discovers Notepad, Calculator, Paint, and Store/packaged apps
  - Phonetic & fuzzy matching (e.g., "sportify" -> Spotify)
  - Target extraction from natural speech patterns
  - Ambiguity detection & top-two choice generation
  - Closing any app with WM_CLOSE and 1.5s process-tree termination
  - "Close everything" confirmation safety
"""
from __future__ import annotations

import os
import sys
import time
import subprocess
import unittest
from unittest.mock import patch, MagicMock

import app_index
from app_index import AppIndex, get_app_index, phonetic_normalize
import target_extractor


class TestPhase6aOpenVocabularyApps(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = get_app_index()

    def test_01_app_index_finds_standard_apps(self):
        """App index finds Notepad, Calculator, Paint and Store/UWP apps."""
        # 1. Notepad
        app_notepad, score_np, _ = self.index.find_app("notepad")
        self.assertIsNotNone(app_notepad)
        self.assertEqual(app_notepad["name"], "Notepad")
        self.assertGreaterEqual(score_np, 90.0)

        # 2. Calculator
        app_calc, score_calc, _ = self.index.find_app("calculator")
        self.assertIsNotNone(app_calc)
        self.assertEqual(app_calc["name"], "Calculator")
        self.assertGreaterEqual(score_calc, 90.0)

        # 3. Paint
        app_paint, score_paint, _ = self.index.find_app("paint")
        self.assertIsNotNone(app_paint)
        self.assertEqual(app_paint["name"], "Paint")
        self.assertGreaterEqual(score_paint, 90.0)

        # 4. Store app discovery (e.g. apps from shell:AppsFolder)
        store_apps = [a for a in self.index.apps if a.get("source") == "store_app"]
        self.assertGreater(len(store_apps), 0, "Should have discovered at least one Store / UWP app")

    def test_02_fuzzy_sportify_and_phonetic_tolerance(self):
        """Fuzzy-matches speech slips like 'sportify' -> Spotify and 'ms paint' -> Paint."""
        # 'sportify' -> Spotify
        app_spot, score_spot, amb = self.index.find_app("sportify")
        self.assertIsNotNone(app_spot)
        self.assertIn("spotify", app_spot["name"].lower())
        self.assertGreaterEqual(score_spot, 75.0)

        # 'ms paint' -> Paint
        app_mp, score_mp, _ = self.index.find_app("ms paint")
        self.assertIsNotNone(app_mp)
        self.assertEqual(app_mp["name"], "Paint")

        # 'not pad' -> Notepad
        app_np, score_np, _ = self.index.find_app("not pad")
        self.assertIsNotNone(app_np)
        self.assertEqual(app_np["name"], "Notepad")

    def test_03_target_extraction_patterns(self):
        """Extracts target and action from natural transcripts, stripping polite fillers."""
        cases = [
            ("open the calculator please", "open", "calculator"),
            ("Hey Jev, please launch Paint", "open", "Paint"),
            ("can you start Notepad right now", "open", "Notepad"),
            ("close Spotify please", "close", "Spotify"),
            ("quit Discord", "close", "Discord"),
            ("switch to VS Code", "focus", "VS Code"),
            ("refresh apps", "refresh_apps", None),
            ("close everything", "close_all", "all"),
            ("close all windows please", "close_all", "all"),
        ]
        for phrase, expected_action, expected_target in cases:
            action, tgt = target_extractor.extract_target(phrase)
            self.assertEqual(action, expected_action, f"Action mismatch for '{phrase}'")
            if expected_target is not None:
                self.assertEqual(tgt.lower(), expected_target.lower(), f"Target mismatch for '{phrase}'")

    def test_04_ambiguity_two_close_choices(self):
        """When two candidates have close match scores, returns top two choices to ask."""
        # Create a test index with two similarly named apps
        test_index = AppIndex.__new__(AppIndex)
        test_index.cache_file = "test_cache.json"
        test_index._lock = MagicMock()
        test_index._lock.__enter__.return_value = None
        test_index._lock.__exit__.return_value = None
        test_index.apps = [
            {"name": "Visual Studio", "clean_name": "visual studio", "target": "devenv.exe", "source": "test", "aliases": ["visual studio"], "priority": 50},
            {"name": "Visual Studio Code", "clean_name": "visual studio code", "target": "code.exe", "source": "test", "aliases": ["visual studio code"], "priority": 50},
        ]
        # Querying "visual studio" might match Visual Studio and Visual Studio Code closely
        best, score, amb = test_index.find_app("visual")
        self.assertIsNotNone(best)
        self.assertIsNotNone(amb, "Should flag ambiguity between Visual Studio and Visual Studio Code")
        self.assertEqual(len(amb), 2)
        names = {amb[0]["name"], amb[1]["name"]}
        self.assertIn("Visual Studio", names)
        self.assertIn("Visual Studio Code", names)

    def test_05_close_tray_app_process_tree(self):
        """Simulate a tray-minimizing app that ignores WM_CLOSE and verify process-tree termination."""
        # Launch a test background Python process with a child that ignores WM_CLOSE
        parent_code = (
            "import subprocess, sys, time\n"
            "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])\n"
            "try:\n"
            "    time.sleep(30)\n"
            "except KeyboardInterrupt:\n"
            "    pass\n"
        )
        proc = subprocess.Popen([sys.executable, "-c", parent_code])
        time.sleep(0.5)
        self.assertTrue(proc.poll() is None, "Parent process should be running")

        try:
            # We mock the index to target this specific process PID
            mock_entry = {"name": "TestTrayApp", "clean_name": "testtrayapp", "process": "python.exe"}
            with patch.object(self.index, "find_app", return_value=(mock_entry, 100.0, None)):
                # Run close_app targeting this test process
                import psutil
                test_ps = psutil.Process(proc.pid)
                children = test_ps.children(recursive=True)

                # Terminate via close_app
                with patch("psutil.process_iter", return_value=[test_ps]):
                    res = self.index.close_app("TestTrayApp")
                    self.assertTrue(res["success"])

            # Verify parent and children are no longer running
            time.sleep(0.5)
            self.assertFalse(test_ps.is_running())
            for c in children:
                self.assertFalse(c.is_running())
        finally:
            if proc.poll() is None:
                proc.kill()

    def test_06_close_all_confirmation_safety(self):
        """'Close everything' or 'close all windows' requires confirmation."""
        # Unconfirmed
        res_unconf = self.index.close_all_apps(confirmed=False)
        self.assertTrue(res_unconf.get("needs_confirmation"))
        self.assertEqual(res_unconf.get("action"), "close_all")
        self.assertIn("close all", res_unconf.get("message", "").lower())

        # Confirmed
        with patch("win32gui.EnumWindows") as mock_enum:
            res_conf = self.index.close_all_apps(confirmed=True)
            self.assertTrue(res_conf.get("success"))
            self.assertTrue(mock_enum.called)

    def test_07_tier2_resolver_integration(self):
        """Tier 2 resolver handles open, fuzzy-matching, close, close-all, and refresh."""
        import tier2_resolver
        with patch.object(self.index, "launch_app", return_value=True):
            # 1. Open Calculator
            res_calc = tier2_resolver.resolve_tier2("open the calculator please")
            self.assertIsNotNone(res_calc)
            self.assertEqual(res_calc["status"], "done")
            self.assertEqual(res_calc["app"], "Calculator")

            # 2. Fuzzy 'sportify' -> Spotify
            res_spot = tier2_resolver.resolve_tier2("open sportify")
            self.assertIsNotNone(res_spot)
            self.assertEqual(res_spot["status"], "done")
            self.assertIn("spotify", res_spot["app"].lower())

            # 3. Close app
            with patch.object(self.index, "close_app", return_value={"success": True, "matched_processes": 1}):
                res_close = tier2_resolver.resolve_tier2("close Spotify please")
                self.assertIsNotNone(res_close)
                self.assertEqual(res_close["status"], "done")
                self.assertEqual(res_close["action"], "app_quit")

            # 4. Close everything (needs confirmation)
            res_all = tier2_resolver.resolve_tier2("close everything")
            self.assertIsNotNone(res_all)
            self.assertEqual(res_all["status"], "needs_confirmation")

            # 5. Refresh apps
            with patch("tier2_resolver.refresh_apps", return_value=120):
                res_ref = tier2_resolver.resolve_tier2("refresh apps")
                self.assertIsNotNone(res_ref)
                self.assertEqual(res_ref["action"], "refresh_apps")
                self.assertIn("120 applications", res_ref["line"])


if __name__ == "__main__":
    unittest.main()
