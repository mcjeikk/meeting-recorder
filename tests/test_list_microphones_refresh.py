"""Unit tests: list_microphones PortAudio refresh (hotplug)."""
from __future__ import annotations

import sys
import unittest
from unittest.mock import MagicMock, patch

# Import once before any sys.modules patching (numpy must not reload mid-suite).
from app.capture.windows_audio import list_microphones


def _make_sd(devices=None):
    sd = MagicMock()
    sd.query_hostapis.return_value = [
        {"name": "MME"},
        {"name": "Windows WASAPI"},
    ]
    sd.query_devices.return_value = devices or [
        {
            "name": "Speakers",
            "max_input_channels": 0,
            "hostapi": 1,
            "default_samplerate": 48000,
        },
        {
            "name": "Mic Array",
            "max_input_channels": 2,
            "hostapi": 1,
            "default_samplerate": 48000,
        },
        {
            "name": "Mic MME dup",
            "max_input_channels": 1,
            "hostapi": 0,
            "default_samplerate": 44100,
        },
        {
            # A2DP / Stereo headset: output-only — must be filtered out
            "name": "Headphones (BT Stereo)",
            "max_input_channels": 0,
            "hostapi": 1,
            "default_samplerate": 48000,
        },
    ]
    return sd


class TestListMicrophonesRefresh(unittest.TestCase):
    def test_wasapi_only_and_skips_zero_input(self) -> None:
        sd = _make_sd()
        with patch.dict(sys.modules, {"sounddevice": sd}):
            mics = list_microphones()
        self.assertEqual([m.name for m in mics], ["Mic Array"])
        sd._terminate.assert_not_called()
        sd._initialize.assert_not_called()

    def test_refresh_reinits_portaudio_before_query(self) -> None:
        sd = _make_sd()
        call_order: list[str] = []

        def _term():
            call_order.append("terminate")

        def _init():
            call_order.append("initialize")

        def _query():
            call_order.append("query")
            return sd.query_devices.return_value

        sd._terminate.side_effect = _term
        sd._initialize.side_effect = _init
        sd.query_devices.side_effect = _query

        with patch.dict(sys.modules, {"sounddevice": sd}):
            mics = list_microphones(refresh=True)

        self.assertEqual([m.name for m in mics], ["Mic Array"])
        self.assertEqual(call_order[:3], ["terminate", "initialize", "query"])
        sd._terminate.assert_called_once()
        sd._initialize.assert_called_once()

    def test_refresh_still_lists_if_reinit_fails(self) -> None:
        sd = _make_sd()
        sd._terminate.side_effect = RuntimeError("busy")
        with patch.dict(sys.modules, {"sounddevice": sd}):
            mics = list_microphones(refresh=True)
        self.assertEqual([m.name for m in mics], ["Mic Array"])

    def test_includes_hands_free_input_device(self) -> None:
        sd = _make_sd(
            [
                {
                    "name": "Headset (BT Hands-Free AG Audio)",
                    "max_input_channels": 1,
                    "hostapi": 1,
                    "default_samplerate": 16000,
                },
                {
                    "name": "Headphones (BT Stereo)",
                    "max_input_channels": 0,
                    "hostapi": 1,
                    "default_samplerate": 48000,
                },
            ]
        )
        with patch.dict(sys.modules, {"sounddevice": sd}):
            mics = list_microphones(refresh=True)
        self.assertEqual(len(mics), 1)
        self.assertIn("Hands-Free", mics[0].name)
        self.assertEqual(mics[0].sample_rate, 16000)


if __name__ == "__main__":
    unittest.main()
