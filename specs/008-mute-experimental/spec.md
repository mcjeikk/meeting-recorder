# Feature Specification: Experimental Follow-Meeting Mic Mute

**Feature Branch**: `008-mute-experimental`

**Created**: 2026-07-28

**Status**: Draft

**Input**: User description: "Mute experimental — README mentions silenciar mi micrófono cuando ninguna app de reunión lo esté usando. Audit: if missing, implement honest MVP using mic_usage.py OR remove misleading README claims. Prefer implement if feasible and safe (Recording Always Wins; never break capture)."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Opt-in auto mute from OS mic usage (Priority: P1)

El usuario activa una casilla experimental. Cuando ninguna otra app (p. ej. Teams) está usando el micrófono según Windows, la pista de micrófono del grabador queda silenciada; cuando una app vuelve a usarlo, se reactiva. El mute manual sigue disponible.

**Why this priority**: El README ya lo promete; el código solo muestra el indicador.

**Independent Test**: Activar casilla; sin apps de reunión en mic → botón muestra silenciado; simular/usar app que tome el mic → se reactiva (o verificar con el indicador existente).

**Acceptance Scenarios**:

1. **Given** casilla OFF, **When** cambia el uso del mic del SO, **Then** el mute del grabador no cambia solo.
2. **Given** casilla ON y ninguna otra app usa el mic, **When** corre el poll de uso, **Then** el grabador queda muteado (silencio en pista, sync intacta).
3. **Given** casilla ON y otra app usa el mic, **When** corre el poll, **Then** el grabador deja de estar muteado.
4. **Given** casilla ON durante grabación, **When** auto-mute cambia, **Then** la captura no se reinicia ni se detiene (solo `set_mic_muted`).

---

### User Story 2 - Honest docs (Priority: P1)

README y UI dejan claro que es experimental, que depende de que la app de reunión **libere** el micrófono a nivel Windows (no del mute interno de Teams si sigue capturando), y que el mute manual / atajo siguen siendo la vía fiable.

**Acceptance Scenarios**:

1. **Given** la UI, **When** el usuario ve la opción, **Then** está marcada como experimental y tiene hint breve.
2. **Given** el README, **When** describe la opción, **Then** alinea con el comportamiento real implementado.

### Edge Cases

- Fallo al leer registro → no cambiar mute; indicador como hoy.
- El propio proceso Python usa el mic (medidor/grabación) → excluido de “otros”.
- Preferencia persistida entre sesiones.

## Requirements *(mandatory)*

- **FR-001**: MUST offer an opt-in experimental control to follow OS mic-in-use (via existing mic_usage detection).
- **FR-002**: When enabled, MUST set recorder mic mute when no other apps use the mic; MUST clear mute when others use it.
- **FR-003**: MUST NOT stop/reinit capture devices to apply mute (Recording Always Wins / existing silence path).
- **FR-004**: MUST persist the preference in AppConfig.
- **FR-005**: Docs/UI MUST not claim knowledge of in-app Teams mute when OS still shows mic in use.

## Success Criteria

- **SC-001**: With option ON and no other mic users, mute state becomes muted within one usage poll (~1–2 s).
- **SC-002**: Applying auto-mute mid-recording does not drop audio device streams.
- **SC-003**: README no longer describes a missing feature.

## Assumptions

- `microphone_users` / ConsentStore LastUsedTimeStop==0 is the same signal as the tray mic icon.
- Many meeting apps do NOT release the mic on in-app mute — experimental value is limited; honesty in docs is mandatory.
