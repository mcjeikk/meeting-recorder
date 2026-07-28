# Validation: Mute Experimental

**Date**: 2026-07-28

| Area | Finding |
|------|---------|
| README claim | Describes experimental auto-mute when no meeting app uses mic |
| Code | `mic_usage.py` + label only; **no** checkbox / auto `set_mic_muted` |
| Safe mute path | `Recorder.set_mic_muted` writes silence; does not reinit devices |
| Detection | ConsentStore LastUsedTimeStop==0; exclude own exe |

**GO** — implement opt-in checkbox MVP; keep honest caveats in README.
