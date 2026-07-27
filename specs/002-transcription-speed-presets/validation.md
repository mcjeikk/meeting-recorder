# Validation Report: Transcription Speed Presets

**Feature**: `002-transcription-speed-presets`  
**Date**: 2026-07-27  
**Scope**: Evidence grounding of SDD artifacts (no application code implemented)

## What was validated

| Area | Method |
|------|--------|
| Preset ladder (turbo / medium / large-v3) | OpenAI Whisper README relative speeds; faster-whisper community benches (#1030); Transcriptor `config.yaml` defaults |
| `beam_size` 5→1 | CTranslate2 Whisper docs; OpenAI discussion #177; faster-whisper README; Transcriptor config comments |
| Skip diarization for Rápido | Transcriptor README (~½ time); CLI `--no-diarize`; pyannote STT+diarization product patterns |
| Phase 2 model reuse | CTranslate2 `load_model`/`unload_model`; keep-model-in-process guidance; constitution III/V |
| UX naming | MacWhisper model pickers; Otter/Descript accuracy tips (not identical preset UIs) |
| Local integration | Recorder `build_command` / worker; Transcriptor `transcribe.py` flags |
| Constitution | I–V check in plan — no conflicts after mapping fix |

## What changed in artifacts

1. **Rápido mapping**: `medium` → **`large-v3-turbo`** + beam `1` + `--no-diarize` (research, plan, data-model, CLI/UI contracts, tasks, quickstart).
2. **Spec FR-003 / assumptions / US1**: Rápido is no longer “lighter model”; speed = no speakers + lighter search; absolute “2× faster” not promised.
3. **UI hints**: Honest copy (same recognition engine as Equilibrado; ~2× as soft CPU estimate).
4. **`research.md`**: New **Evidence Review** (E1–E6) with Claim → Verdict → Sources → Implication.
5. **`plan.md` Phase 2**: Clarified realistic sibling warm-worker scope.

## Residual risks

- **SC-002 ordering** still depends on local measurement; ASR turbo+beam1 vs turbo+beam5 is a modest gap — the large gap is diarization on/off. Short samples may compress differences.
- **First download** of `large-v3` for Máxima adds cold-start cost not reflected in “model speed” alone.
- **Spanish meeting WER** not re-benchmarked here; turbo-as-Rápido ASR quality is assumed from public WER claims + current product default.
- **Phase 2 daemon** remains design-only; complexity vs single-user value may justify “wontfix.”
- Transcriptor README still suggests `--model medium` for drafts — slightly diverges from Recorder presets until that doc is updated (out of Phase 1 scope unless desired).

## Recommendation

**GO-WITH-CHANGES**

Phase 1 is ready to implement with the revised mapping. Proceed to `/speckit-implement` for Phase 1 (US1–US3). Do **not** implement Phase 2 model daemon unless explicitly requested.
