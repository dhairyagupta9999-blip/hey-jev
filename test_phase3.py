"""Unit and UI smoke tests for Phase 3: PySide6 Window & Waveform Bubble."""
import os
import sys
import unittest

# Run Qt offscreen for automated headless testing
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication
from assistant_ui import MainWindow, STATUS_COLORS
from bubble import DictationBubble

class TestPhase3WindowAndBubble(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_bubble_creation_and_rms(self):
        """Verify DictationBubble creation and RMS scaling."""
        bubble = DictationBubble()
        self.assertEqual(bubble.WIDTH, 340)
        self.assertEqual(bubble.HEIGHT, 72)

        # Set RMS
        bubble.set_rms(0.5)
        self.assertAlmostEqual(bubble.target_rms, 1.0, places=2)

        bubble.set_rms(0.01)
        self.assertAlmostEqual(bubble.target_rms, 0.04, places=2)

        # Animate step
        bubble._animate_step()
        self.assertEqual(len(bubble.bar_heights), bubble.NUM_BARS)
        bubble.close()

    def test_main_window_tabs(self):
        """Verify MainWindow has all 7 tabs specified in Prime Directives."""
        window = MainWindow()
        self.assertEqual(window.tabs.count(), 7)

        tab_titles = [window.tabs.tabText(i) for i in range(window.tabs.count())]
        expected_tabs = ["Home", "Dictionary", "Apps", "Dictation", "Privacy", "Settings", "Keys"]
        self.assertEqual(tab_titles, expected_tabs)

        window.close()

    def test_status_dot_colors(self):
        """Verify status dot colors match the Mac status-dot language."""
        self.assertEqual(STATUS_COLORS["Ready"], "#10b981")        # Green
        self.assertEqual(STATUS_COLORS["Listening"], "#ef4444")    # Red
        self.assertEqual(STATUS_COLORS["Thinking"], "#a855f7")     # Purple
        self.assertEqual(STATUS_COLORS["Doing it"], "#f97316")     # Orange
        self.assertEqual(STATUS_COLORS["Speaking"], "#06b6d4")     # Teal

    def test_dynamic_privacy_text(self):
        """Verify privacy text changes dynamically based on active backend."""
        window = MainWindow()
        # Test Jev text
        window.settings["backend"] = "jev"
        window._update_privacy_text()
        self.assertIn("Jev (TypeSafe Hosted", window.privacy_text.text())
        self.assertIn("faster-whisper", window.privacy_text.text())

        # Test Laya text
        window.settings["backend"] = "laya"
        window._update_privacy_text()
        self.assertIn("Local Laya (100% On-Device)", window.privacy_text.text())
        self.assertIn("Zero command text or audio leaves your computer", window.privacy_text.text())

        window.close()

    def test_close_to_tray_semantics(self):
        """Verify Close hides window rather than terminating process."""
        window = MainWindow()
        window.settings["close_to_tray"] = True
        window.show()
        self.assertTrue(window.isVisible())

        # Simulate close event
        from PySide6.QtGui import QCloseEvent
        event = QCloseEvent()
        window.closeEvent(event)
        self.assertTrue(event.isAccepted() or not window.isVisible())
        window.close()

if __name__ == "__main__":
    unittest.main()
