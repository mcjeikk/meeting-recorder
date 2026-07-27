# Feature Specification: Transcription Speed Presets

**Feature Branch**: `002-transcription-speed-presets`

**Created**: 2026-07-27

**Status**: Draft

**Input**: User description: "Transcription speed presets from the Recorder UI (e.g. Rápido / Equilibrado / Máxima calidad) that map to Transcriptor options (model size, beam search aggressiveness, optional skip speaker labeling for the fast path), plus documenting/planning model-load reuse where feasible WITHOUT fusing transcription into the recorder process. Cache of the speech-recognition model may be a Transcriptor-side improvement in the same feature or a clear Phase 2 within the spec."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Choose a speed/quality preset before transcribing (Priority: P1)

As the primary user, I want to pick a named transcription preset (Rápido, Equilibrado, or Máxima calidad) in the Recorder so that each job trades speed vs. accuracy and speaker labeling in a predictable way, without editing sibling-tool config files.

**Why this priority**: Today every job uses the sibling engine’s default high-quality path (~2–2.5× audio duration, with speaker labeling). Choosing a faster path for drafts or a max-quality path for important meetings is the core value of this feature.

**Independent Test**: With auto-transcribe enabled, select each preset, finish a short recording (or enqueue an existing file), and confirm the job’s visible outcome matches the preset’s promised trade-offs (faster vs. speakers/accuracy), and that the choice persists across app restarts.

**Acceptance Scenarios**:

1. **Given** the app is idle and not recording, **When** the user selects “Rápido”, **Then** the UI shows that choice clearly and subsequent transcription jobs use the fast mapping (lower search effort, **no** speaker labeling; recognition model stays in the same class as Equilibrado).
2. **Given** the user selects “Equilibrado”, **When** a job runs, **Then** the job uses the balanced mapping (default-quality recognition with speaker labeling) and completes with the same class of outputs the product already produces today.
3. **Given** the user selects “Máxima calidad”, **When** a job runs, **Then** the job uses the highest-effort mapping (heavier recognition model and speaker labeling) without requiring manual config edits outside the app.
4. **Given** a preset was saved previously, **When** the user restarts the app, **Then** the same preset is selected again.

---

### User Story 2 - Understand the trade-off before starting a job (Priority: P1)

As the user, I want a short plain-language hint next to the preset so I know whether speaker labels and accuracy will be reduced before I spend time waiting.

**Why this priority**: Skipping speaker labeling (or choosing Máxima’s heavier model) changes the transcript usefulness; surprises after a long wait are costly.

**Independent Test**: Change presets and verify the helper text updates to describe relative speed, whether speakers are labeled, and that processing remains local.

**Acceptance Scenarios**:

1. **Given** “Rápido” is selected, **When** the user looks at the transcription controls, **Then** they see that the path is faster and does not label speakers.
2. **Given** “Equilibrado” or “Máxima calidad” is selected, **When** the user looks at the controls, **Then** they see that speakers are labeled and that “Máxima calidad” is slower / more accurate than “Equilibrado”.

---

### User Story 3 - Preset applies to queued and retried jobs without blocking recording (Priority: P2)

As the user, I want new transcription work to honor the current (or job-captured) preset while recording still always wins over background transcription.

**Why this priority**: Aligns with the product promise that capture is irrecoverable and transcripts can wait; presets must not change that priority.

**Independent Test**: Start a recording while a transcription job is running or queued; confirm recording proceeds and the transcription path still respects Recording Always Wins. After stop, new jobs still use the configured preset.

**Acceptance Scenarios**:

1. **Given** auto-transcribe is on and a preset is selected, **When** a recording finishes, **Then** the enqueued job carries enough information to apply that preset even if the user later changes the UI preset before the job starts.
2. **Given** a transcription job is active, **When** the user starts recording, **Then** transcription yields as today (does not starve capture) and completes or resumes according to existing product rules.
3. **Given** a failed job is retried from the UI, **When** retry runs, **Then** it reuses the preset stored with that job (not a silent unrelated default).

---

### User Story 4 - Plan faster repeat runs via model reuse (Phase 2) (Priority: P3)

As the user, I want successive transcripts with the same quality settings to avoid paying full model-load cost every time when that can be done without merging the sibling transcription environment into the recorder.

**Why this priority**: Model load is a real cost on CPU-only machines, but a durable long-lived worker is a larger design change; it must not violate the sibling-subprocess constitution. Specifying Phase 2 keeps scope honest.

**Independent Test**: Phase 2 is accepted when a documented approach exists and, once implemented, two back-to-back jobs with the same preset show measurably less wall-clock time attributable to model load than today—without fusing environments.

**Acceptance Scenarios**:

1. **Given** Phase 1 (presets in UI + job mapping) is done, **When** planners review Phase 2, **Then** the plan documents at least one reuse approach that keeps transcription as a separate process/environment and keeps recording priority intact.
2. **Given** Phase 2 is implemented later, **When** two consecutive jobs use the same recognition settings, **Then** the second job spends less time on model initialization than an equivalent cold start (measurable on the same machine), or the product documents why reuse could not be achieved without violating constraints.

---

### Edge Cases

- What happens when the sibling transcription tool is missing or misconfigured? Jobs fail with the same class of clear errors as today; preset selection remains visible but does not invent success.
- What if “Rápido” produces a transcript without speakers? That is expected; the UI must not claim speakers were labeled.
- What if the user changes the preset while a job is already queued or running? In-flight/queued jobs keep the preset captured at enqueue; only new jobs use the new selection.
- What if speaker labeling fails on Equilibrado/Máxima calidad? Existing degraded/retry behavior remains; the preset does not remove recovery paths.
- What if the user selects Máxima calidad on a machine without enough resources? The job may take longer; the product still runs locally and must not upload media to the cloud.
- Empty or unknown saved preset values fall back to Equilibrado (current product default behavior).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The Recorder MUST expose exactly three user-selectable transcription presets labeled **Rápido**, **Equilibrado**, and **Máxima calidad**.
- **FR-002**: The selected preset MUST be persisted in user configuration and restored on next launch.
- **FR-003**: Each preset MUST map to a fixed, documented combination of recognition effort, search aggressiveness, and whether speaker labeling runs, as follows (user-facing intent; exact engine flags belong in the plan):
  - **Rápido**: same class of recognition quality as Equilibrado (not a downgraded/slower model), lower search effort, **no** speaker labeling — the intended speed win is skipping speakers (and lighter search), not a weaker ASR model.
  - **Equilibrado**: current product-default recognition quality, default search effort, **with** speaker labeling (matches today’s typical outcome).
  - **Máxima calidad**: heavier / higher-accuracy recognition model than Equilibrado, equal or higher search effort, **with** speaker labeling.
- **FR-004**: When a transcription job is enqueued, the job MUST store the preset (or equivalent parameters) in effect at enqueue time so later UI changes do not alter that job.
- **FR-005**: The Recorder MUST pass the preset’s parameters to the sibling transcription tool through the existing subprocess + durable queue integration (no fused library / shared environment).
- **FR-006**: The UI MUST show a short explanation of the selected preset’s speed vs. speaker-labeling trade-off.
- **FR-007**: Changing presets MUST NOT require the user to edit files in the sibling transcription project.
- **FR-008**: Presets MUST NOT weaken Recording Always Wins: enumeration or job launch still yields to active/imminent recording per existing rules.
- **FR-009**: All media processing for these presets MUST remain on the user’s machine; no cloud upload of meeting media.
- **FR-010**: Phase 1 MUST deliver UI + job mapping + persistence. Phase 2 (model-load reuse across jobs) MAY be specified and planned in the same feature folder but MUST NOT block shipping Phase 1; Phase 2 MUST keep transcription as a sibling process/environment.
- **FR-011**: Retry of a job MUST honor the preset/parameters stored on that job.
- **FR-012**: An unrecognized or missing saved preset MUST fall back to Equilibrado.

### Key Entities

- **Transcription Preset**: Named user choice (Rápido | Equilibrado | Máxima calidad) with a fixed mapping to recognition effort, search aggressiveness, and speaker-labeling on/off.
- **Transcription Job**: Durable queued unit of work; gains a preset (or equivalent stored parameters) captured at enqueue; drives sibling-tool invocation.
- **User Configuration**: Persisted preference including the last-selected preset (and existing transcription toggles/language).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can select a preset and confirm it is remembered after restart in under 30 seconds of interaction (no file editing).
- **SC-002**: On the same machine and same short sample (~1–3 minutes of audio), a Rápido job finishes in less wall-clock time than Equilibrado, and Equilibrado finishes in less or equal wall-clock time than Máxima calidad (ordering holds when comparing successful runs).
- **SC-003**: Rápido transcripts do not claim speaker labels; Equilibrado and Máxima calidad attempt speaker labeling when the sibling tool’s normal prerequisites are met.
- **SC-004**: 100% of newly enqueued jobs after this feature include an explicit preset/parameter snapshot (no silent “whatever the global UI says later”).
- **SC-005**: Starting a recording while transcription is active still prioritizes capture the same way as before this feature (no regression in Recording Always Wins behavior).
- **SC-006**: Phase 2 plan exists in the feature artifacts describing at least one constitution-compliant reuse approach; if implemented, second same-preset job shows reduced model-init overhead vs. cold start on a documented test.

## Assumptions

- The primary user is a single power user on Windows desktop (Spanish UI labels are appropriate).
- “Equilibrado” intentionally mirrors today’s default sibling-engine quality and speaker labeling so existing expectations remain the middle option.
- Reasonable default mappings (fixed in the plan after evidence review): Rápido → same default recognition model as Equilibrado + low search + no speakers; Equilibrado → current default model + default search + speakers; Máxima calidad → heavier recognition model + default or higher search + speakers. Do not claim absolute wall-clock multipliers (e.g. “2× faster”) as guarantees; SC-002 uses relative ordering on the same machine/sample.
- Language preference remains the existing config value; this feature does not redesign language selection UI.
- Auto-transcribe checkbox behavior remains; presets apply whenever a job is enqueued from the app.
- Model-load reuse across process lifetimes is Phase 2; Phase 1 accepts cold start per job as today.
- Sibling transcription continues to own model binaries and its own environment; Recorder only selects options and launches jobs.
- No LLM/minuta features are introduced.
