# Research: Multi-Monitor

## R1 — Index semantics

**Decision**: Use 1-based index into `EnumDisplayMonitors` order — matches `windows-capture` `monitor_index`.

## R2 — Qt screens vs Win32

**Decision**: Enumeration for capture identity = Win32. Preview may use Qt screens; match by geometry when possible, else ordinal.

## R3 — Persistence

**Decision**: MVP does not persist last monitor across restarts.
