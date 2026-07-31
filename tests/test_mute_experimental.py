"""Tests for experimental follow-meeting mute helper."""
from __future__ import annotations

import unittest

from app.core.mic_usage import (
    desired_follow_meeting_mute,
    should_apply_follow_meeting_mute,
)


class TestDesiredFollowMeetingMute(unittest.TestCase):
    def test_mute_when_nobody_else(self) -> None:
        self.assertTrue(desired_follow_meeting_mute(False))

    def test_unmute_when_others(self) -> None:
        self.assertFalse(desired_follow_meeting_mute(True))


class TestShouldApplyFollowMeetingMute(unittest.TestCase):
    def test_first_sample_applies(self) -> None:
        self.assertTrue(should_apply_follow_meeting_mute(False, None))
        self.assertFalse(should_apply_follow_meeting_mute(True, None))

    def test_same_level_does_not_stomp(self) -> None:
        # En llamada estable: no reaplicar (mute manual se respeta).
        self.assertIsNone(should_apply_follow_meeting_mute(True, True))
        # Fuera de llamada estable: tampoco reaplicar.
        self.assertIsNone(should_apply_follow_meeting_mute(False, False))

    def test_edge_into_call_unmutes(self) -> None:
        self.assertFalse(should_apply_follow_meeting_mute(True, False))

    def test_edge_out_of_call_mutes(self) -> None:
        self.assertTrue(should_apply_follow_meeting_mute(False, True))


if __name__ == "__main__":
    unittest.main()
