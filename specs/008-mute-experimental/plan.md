# Plan: Mute Experimental

**Feature**: `008-mute-experimental` | **Date**: 2026-07-28

## Summary

Wire an opt-in checkbox to sync `Recorder.set_mic_muted` with `is_microphone_in_use_by_others()`, persist in config, update README honesty. No capture restart.

## Approach

1. `AppConfig.auto_mute_follow_meeting: bool = False`
2. Checkbox under mic usage label (experimental wording + tooltip)
3. `_update_mic_usage`: if enabled, `desired = not is_microphone_in_use_by_others((own_hint,))`; if differs from `is_mic_muted()`, apply + update button
4. Load/save with other config
5. Unit test: pure sync decision helper optional in mic_usage or small function
6. README tweak

## Constitution

Recording Always Wins: mute-only; never PortAudio reinit from this path.
