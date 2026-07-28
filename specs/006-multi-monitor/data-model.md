# Data Model: Multi-Monitor

## VideoSource (extended)

| Field | Type | Notes |
|-------|------|-------|
| kind | `"screen"` \| `"window"` | unchanged |
| title | str | for screen: human label fragment / device |
| hwnd | int? | windows only |
| monitor_index | int? | screen only; 1-based WGC index |

## Label rules

- Screen primary: `Pantalla {n} (principal)`  
- Screen other: `Pantalla {n}`  
- Optional suffix with resolution in UI combo only.
