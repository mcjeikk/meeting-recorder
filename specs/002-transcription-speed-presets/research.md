# Research: Transcription Speed Presets

**Feature**: `002-transcription-speed-presets` | **Date**: 2026-07-27  
**Evidence review**: 2026-07-27 (web + local Transcriptor/Recorder code)

## R1 — Where to apply speed/quality knobs

**Decision**: Pass Transcriptor CLI flags from Recorder’s worker (`--model`, `--beam-size`, `--no-diarize`) via existing `build_command(..., extra_args=)`.

**Rationale**: Recorder already builds argv lists and only overrides `--threads` / degraded `--no-diarize`. Transcriptor already exposes these flags; `config.yaml` defaults apply when flags are omitted. No need to edit sibling config files from the UI.

**Alternatives considered**:
- Edit Transcriptor `config.yaml` from Recorder → fragile, races with manual CLI use, worse UX.
- Fuse Whisper into Recorder venv → violates constitution III.
- Expose raw hyperparameter panel → overkill for single power user (constitution V).

## R2 — Preset → parameter mapping

**Decision** (fixed for Phase 1, **revised after evidence review**):

| Preset | `--model` | `--beam-size` | Speaker labeling |
|--------|-----------|---------------|------------------|
| Rápido | `large-v3-turbo` | `1` | off (`--no-diarize`) |
| Equilibrado | `large-v3-turbo` | `5` | on (default) |
| Máxima calidad | `large-v3` | `5` | on (default) |

**Rationale**:
- Equilibrado mirrors today’s Transcriptor default (`config.yaml`: `modelo: large-v3-turbo`, `beam_size: 5`, `diarizar: true`).
- Rápido’s **primary** wall-clock win is skipping diarization (Transcriptor README: ~half the time). Secondary: `beam_size=1` (modest). **Do not** switch Rápido to `medium`: OpenAI and community benches show turbo is substantially faster than medium while retaining near-large accuracy (see Evidence Review E1).
- Máxima uses full `large-v3` (heavier/slower ASR) with speakers — the only preset that upgrades the recognition model.

**Alternatives considered**:
- Rápido with `medium`/`small` → **rejected** after evidence: slower and/or worse than turbo for the “fast draft” path; risks breaking SC-002 ordering vs Equilibrado.
- Rápido with `small` + no diarize → faster still, but quality drop for Spanish meetings likely too steep for one power user; revisit only if measured need.
- Máxima with beam `8` → marginal gain, more CPU; keep beam 5 unless local benchmarks say otherwise.
- Equilibrado without explicit `--model` → less reproducible if sibling `config.yaml` drifts; explicit flags preferred.

## R3 — Job snapshot vs live UI preset

**Decision**: Persist `preset` (and denormalized model/beam/no_diarize) on `TranscriptionJob` at enqueue time; UI changes do not mutate queued/running jobs; retry reuses job fields.

**Rationale**: Spec FR-004 / FR-011; avoids “I changed to Rápido while job waited and got máxima by accident.”

**Alternatives considered**: Always read live `AppConfig` at `_execute` → simpler but violates user expectation and SC-004.

## R4 — Interaction with degraded diarization retry

**Decision**: Existing worker logic that forces `job.no_diarize=True` on degraded retry **overrides** preset’s diarize-on for that attempt.

**Rationale**: Recovery path already exists; presets must not remove it. Rápido already has `no_diarize=True` from the start.

## R5 — Model-load reuse (Phase 2)

**Decision**: Phase 2 is Transcriptor-side only. Options to evaluate at implement time:
1. **In-process cache** inside a single Transcriptor invocation that processes a batch (limited value for one-file-per-job today).
2. **Long-lived sibling worker process** owned by Transcriptor (or a thin launcher), spoken to by argv/stdin/socket protocol, still separate venv; Recorder remains client of durable queue + spawn/connect — models stay loaded between jobs (`WhisperModel` / CTranslate2 instance held in memory; see E4).
3. **Accept cold start** if (2) is too heavy for single-user simplicity — document and close Phase 2 as “wontfix / revisit.”

**Rationale**: Constitution III forbids fused library; V discourages scheduled-task mega-workers. An optional sibling daemon is the only reuse path that keeps Recording Always Wins (Recorder can still refuse to start jobs / suspend child while recording).

**Alternatives considered**:
- Keep model in Recorder process → rejected (III).
- Windows Scheduled Task worker → previously discarded (CLAUDE.md / constitution V).

## R6 — UI placement

**Decision**: Add preset selector + short hint adjacent to the existing “Transcribir al terminar” checkbox in `MainWindow`.

**Rationale**: Same mental model as auto-transcribe; language stays config-only (assumption). Named presets (Rápido / Equilibrado / Máxima) beat exposing raw model IDs for this product (see E5).

## R7 — Threads / device / compute-type

**Decision**: Phase 1 does **not** expose `--device` / `--compute-type` in presets; keep worker `--threads = cpu_count-2`.

**Rationale**: Device auto-detect already in Transcriptor; thread policy is Recording Always Wins; presets focus on model/beam/diarize trade-off only.

---

## Evidence Review (2026-07-27)

Claim → Verdict → Sources → Implication for Meeting Recorder.

### E1 — Model size vs speed/quality (preset ladder)

| Claim | Verdict | Sources | Implication |
|-------|---------|---------|-------------|
| `large-v3-turbo` is a sensible **default / balanced** choice (near-large accuracy, much faster than full large) | **Supported** | OpenAI Whisper README: turbo ≈ **~8×** relative speed vs large, “minimal degradation in accuracy” ([raw README](https://raw.githubusercontent.com/openai/whisper/main/README.md)). Transcriptor already defaults to `large-v3-turbo` in `config.yaml`. | Keep Equilibrado = turbo + diarize. |
| Full `large-v3` is the **max-quality** ASR step above turbo | **Supported** | Same OpenAI table (large = 1× baseline); blogs note turbo trades a small WER increase for large speedups ([cosmo-edge](https://cosmo-edge.com/whisper-large-v3-vs-turbo-best-stt-models/), [GIGAGPU](https://gigagpu.com/whisper-large-v3-turbo-vs-large-v3-comparison/)). | Máxima = `large-v3` + diarize is honest. |
| Using **`medium` for “Rápido”** is faster than Equilibrado’s turbo | **Unsupported** (anti-pattern) | OpenAI relative speeds: **medium ~2×**, **turbo ~8×** vs large ([README](https://raw.githubusercontent.com/openai/whisper/main/README.md)). Community faster-whisper sequential bench: medium transcribe **106.3 s** vs large-v3-turbo **39.0 s** on same file ([faster-whisper#1030](https://github.com/SYSTRAN/faster-whisper/issues/1030)). Commenter: 10‑min audio Medium 52 s vs Turbo 39 s (same issue). | **Changed mapping**: Rápido keeps `large-v3-turbo`, wins via `--no-diarize` + `beam_size=1`. |
| Transcriptor README tip “use `--model medium` for draft” is still the best fast path vs current default | **Partially** | Local Transcriptor README (sibling project): recommends medium/small + `--no-diarize` + beam 1. Tip is sensible vs **`large-v3`**, but **outdated vs default turbo**. | Prefer turbo+no-diarize for Rápido; leave README tip as historical/manual guidance. |

### E2 — `beam_size` (5 → 1)

| Claim | Verdict | Sources | Implication |
|-------|---------|---------|-------------|
| Lowering beam size speeds decoding | **Supported** (modest) | CTranslate2 Whisper `generate(..., beam_size=5)` documents **“Beam size (1 for greedy search)”** ([docs](https://opennmt.net/CTranslate2/python/ctranslate2.models.Whisper.html)). OpenAI maintainer: greedy is faster, slightly less accurate, more repetition risk ([discussion #177](https://github.com/openai/whisper/discussions/177)). faster-whisper defaults beam 5 and warns comparisons must match beam ([README](https://github.com/SYSTRAN/faster-whisper)). Tuning notes: latency scales with beam; gains diminish after ~5 ([The Neural Base](https://theneuralbase.com/whisper/learn/intermediate/beam-size-tuning/)). Transcriptor config comment: `1 = más rápido, 5 = más preciso`. | Use beam 1 only on Rápido; do **not** market it as the main speed lever. |
| beam 5→1 alone yields ~2× wall-clock on full jobs | **Unsupported** | Sources describe decoding-path effect only; diarization dominates wall-clock on this product (CLAUDE.md / Transcriptor README ~1× ASR + ~1× diarize). | UI/spec: relative language (“algo más rápido en el reconocimiento”), not absolute multipliers. |

### E3 — Skipping diarization for “Rápido”

| Claim | Verdict | Sources | Implication |
|-------|---------|---------|-------------|
| Optional / skippable diarization is a normal product tradeoff | **Supported** | Transcriptor CLI `--no-diarize` + README: “aproximadamente **la mitad** del tiempo (solo transcripción)”. pyannote docs treat diarization as a separate pipeline; STT+diarization takes longer than either alone ([pyannoteAI STT orchestration](https://docs.pyannote.ai/tutorials/speech-to-text-diarization)). Local tools expose “plain text / no speakers” fast paths (e.g. `diarization_declined` / `--no-diarization` patterns in open ASR skills). | Rápido without speakers is acceptable **if UI is explicit**. |
| Empty `hablantes` must not be treated as job failure | **Supported** (local) | Transcriptor degrades without HF token with exit 0; Recorder already has degraded retry. Spec edge cases align. | Contract: Rápido success ≠ speakers present. |

### E4 — Model caching / warm process (Phase 2)

| Claim | Verdict | Sources | Implication |
|-------|---------|---------|-------------|
| Reuse requires a **long-lived process** holding the model object | **Supported** | CTranslate2 `Whisper.load_model` / `unload_model` keep/resume device context ([docs](https://opennmt.net/CTranslate2/python/ctranslate2.models.Whisper.html)). Community rule: load once, reuse; do not reload per request ([whisper_ct2 usage-rules](https://repo.hex.pm/preview/whisper_ct2/0.5.0/usage-rules.md)). HTTP/daemon wrappers cache converted models across requests ([ctranslate2-web-server](https://github.com/jordimas/ctranslate2-web-server)). | Phase 2 = sibling warm worker / in-process cache — **not** Recorder imports. |
| Fusing torch into Recorder venv for cache | **Unsupported** (constitution) | Constitution III; CLAUDE.md discarded unified venv. | Keep Phase 2 sibling-only. |
| Always-on Windows Scheduled Task as default reuse | **Rejected locally** | Constitution V / CLAUDE.md. | Document only as discarded alternative. |

### E5 — UX naming / expectations

| Claim | Verdict | Sources | Implication |
|-------|---------|---------|-------------|
| Consumer tools expose named Fast / Balanced / Max quality | **Partially** | Local Whisper UIs (MacWhisper) emphasize **model picker** (Tiny→Large/Turbo), not always three named presets ([MacWhisper](https://macwhisper.org/), help docs). Otter/Descript optimize accuracy via vocabulary/speakers/model choice, not “Rápido/Equilibrado” labels ([Otter accuracy tips](https://help.otter.ai/hc/en-us/articles/18934488820887-Tips-on-improving-speech-transcript-accuracy), [Descript transcription](https://help.descript.com/hc/en-us/articles/10249424286477-Automatic-transcription)). Automation wishlists still propose `fast` / `balanced` / `accurate` presets. | Three Spanish named presets are fine for a single power user; hints must state **speakers on/off** and **relative** speed/quality — not absolute “2× faster everywhere.” |
| Equilibrado hint “~2× audio duration” | **Partially** | Measured on author’s CPU laptop (Transcriptor README / CLAUDE.md); hardware-dependent. | Keep as soft local estimate (“en este tipo de equipo…”) or relative wording; SC-002 already uses ordering, not absolute RTF. |

### E6 — Anti-patterns in the pre-review 002 plan

| Anti-pattern | Verdict | Fix applied |
|--------------|---------|-------------|
| Rápido → `medium` while Equilibrado → `turbo` | Misleading / can make “Rápido” **slower** ASR | Rápido → turbo + beam 1 + `--no-diarize` |
| Promising large speedups from beam alone | Overclaim | Hints: diarization skip = main lever |
| Absolute wall-clock multipliers in UI as guarantees | Overclaim | Spec SC-002 = ordering; soften Equilibrado copy |
| Phase 2 fused into Recorder | Constitution III conflict | Unchanged rejection; sibling warm process only |
| Wrong CLI flags | None found | `--model`, `--beam-size`, `--no-diarize` match `transcribe.py` |

## Local code anchors (non-web)

- Transcriptor `config.yaml`: `modelo: large-v3-turbo`, `beam_size: 5`, `diarizar: true`.
- Transcriptor `transcribe.py`: `--model`, `--beam-size`, `--no-diarize`.
- Recorder `worker.py`: already appends `--threads` and optional `--no-diarize` via `build_command(..., extra_args=)`.
- CLAUDE.md: transcription ≈ 2–2.5× audio; diarization is the slow phase; Recording Always Wins.
