"""Tests for experimental follow-meeting mute helper."""
from __future__ import annotations

import unittest

from app.core.mic_usage import desired_follow_meeting_mute


class TestDesiredFollowMeetingMute(unittest.TestCase):
    def test_mute_when_nobody_else(self) -> None:
        self.assertTrue(desired_follow_meeting_mute(False))

    def test_unmute_when_others(self) -> None:
        self.assertFalse(desired_follow_meeting_mute(True))


if __name__ == "__main__":
    unittest.main()
