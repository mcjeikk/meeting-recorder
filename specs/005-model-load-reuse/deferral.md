# Deferral Note: Model-Load Reuse (005)

**Date**: 2026-07-28  
**Verdict**: **Code deferred.** Spec + plan + tasks documentation only.

## Why

1. A useful warm path requires a **long-lived sibling worker + IPC + crash fallback + Recording Always Wins suspend** — too large/risky for one audit pass.
2. A “keep-alive” flag in Transcriptor unused by Recorder would be dead surface area and risk breaking default one-shot CLI.
3. Constitution III/V: prefer not shipping a half-broken daemon for a single power user when presets already offer a fast path.

## What shipped instead (this feature folder)

- Spec, validation, plan, research, quickstart measurement outline, tasks marked deferred.
- Explicit unlock of backlog items **006 multi-monitor**, **007 preview**, **008 mute experimental**.

## What “done later” looks like

See `plan.md` Future pass: warm Transcriptor worker, Recorder prefer-warm-else-cold, measure cold vs warm, never fuse venvs.
