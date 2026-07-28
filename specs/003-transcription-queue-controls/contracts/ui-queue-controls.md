# Contract: UI Queue Controls

## Language selector

- Label: `Idioma:`
- Options (display → value):
  - `Español` → `es`
  - `English` → `en`
  - `Auto` → `auto`
- Persists via `AppConfig.transcription_language` on change and on start-recording save path.
- Enabled when Transcriptor is available (same gate as preset/checkbox); tooltip if missing.

## Transcription banner actions

| Action | Visible when | Behavior |
|--------|--------------|----------|
| Cancelar | status ∈ {pending, extracting, running} | Calls worker cancel for current job id |
| Reintentar | status == error | Existing retry |
| Abrir transcripción | status == done | Existing open folder |
| Ver log | status == error (and cancelled MAY show) | Open log file if present |
| Limpiar fallidos | ≥1 error/cancelled in store OR current is error/cancelled | Clears those jobs; updates banner if needed |

✕ still only hides the banner.

## Copy

- Cancelled: `⛔ Transcripción cancelada: {stem}`
- Clear with none: no-op / disabled
