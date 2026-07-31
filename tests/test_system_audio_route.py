"""Tests for WASAPI loopback helpers and Bluetooth output detection."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from app.capture.windows_audio import is_bluetooth_audio_name, resolve_wasapi_loopback


class TestBluetoothName(unittest.TestCase):
    def test_detects_common_names(self) -> None:
        self.assertTrue(is_bluetooth_audio_name("Auriculares (WH-1000XM4)"))
        self.assertTrue(is_bluetooth_audio_name("Headset (Galaxy Buds Hands-Free AG Audio)"))
        self.assertTrue(is_bluetooth_audio_name("Headphones Bluetooth Stereo"))
        self.assertFalse(is_bluetooth_audio_name("Altavoces (Realtek(R) Audio)"))
        self.assertFalse(is_bluetooth_audio_name(""))


class TestResolveLoopback(unittest.TestCase):
    def test_exact_name_match(self) -> None:
        pa = MagicMock()
        wasapi = {"defaultOutputDevice": 10, "index": 2}
        pa.get_host_api_info_by_type.return_value = wasapi
        speakers = {
            "name": "Altavoces (Realtek(R) Audio)",
            "isLoopbackDevice": False,
            "index": 10,
        }
        lb = {
            "name": "Altavoces (Realtek(R) Audio) [Loopback]",
            "isLoopbackDevice": True,
            "index": 13,
            "maxInputChannels": 2,
        }
        pa.get_device_info_by_index.return_value = speakers
        pa.get_loopback_device_info_generator.return_value = iter([lb])
        got = resolve_wasapi_loopback(pa)
        self.assertEqual(got["index"], 13)

    def test_fuzzy_match_when_exact_fails(self) -> None:
        pa = MagicMock()
        wasapi = {"defaultOutputDevice": 1, "index": 2}
        pa.get_host_api_info_by_type.return_value = wasapi
        speakers = {
            "name": "Speakers Realtek Audio",
            "isLoopbackDevice": False,
            "index": 1,
        }
        other = {
            "name": "HDMI Output [Loopback]",
            "isLoopbackDevice": True,
            "index": 9,
        }
        lb = {
            "name": "Speakers Realtek [Loopback]",
            "isLoopbackDevice": True,
            "index": 8,
        }
        pa.get_device_info_by_index.return_value = speakers
        pa.get_loopback_device_info_generator.return_value = iter([other, lb])
        got = resolve_wasapi_loopback(pa)
        self.assertEqual(got["index"], 8)


if __name__ == "__main__":
    unittest.main()
