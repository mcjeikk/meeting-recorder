"""Opciones persistentes compartidas entre Grabar, Ajustes y la cola."""
from pathlib import Path

from PySide6.QtCore import QObject, Property, Signal, Slot

from app.core.config import apply_selected_output_dir, default_output_dir, resolve_output_dir
from app.transcription.jobs import normalize_language, normalize_num_speakers
from app.transcription.pc_impact import PC_IMPACT_ORDER, get_pc_impact, normalize_pc_impact
from app.transcription.presets import PRESET_ORDER, get_preset, normalize_preset


class Preferences(QObject):
    changed = Signal()
    edited = Signal(str)

    FLAGS = {"capture_system_audio", "reduce_echo", "auto_mute_follow_meeting",
             "exclude_window_from_capture", "transcribe_after_recording"}
    OPTIONS = {
        "transcription_preset": [(i, get_preset(i).label_es) for i in PRESET_ORDER],
        "transcription_pc_impact": [(i, get_pc_impact(i).label_es) for i in PC_IMPACT_ORDER],
        "transcription_language": [("es", "Español"), ("en", "English"), ("auto", "Detectar idioma")],
        "transcription_num_speakers": [(0, "Detectar automáticamente")] + [(n, str(n)) for n in range(1, 13)],
    }

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config

    @property
    def directory(self):
        try:
            return resolve_output_dir(self.config.output_dir or default_output_dir())
        except ValueError:
            return Path.home()

    @Property("QVariantMap", notify=changed)
    def values(self):
        cfg = self.config
        fields = {key: bool(getattr(cfg, key)) for key in self.FLAGS}
        fields["output_dir"] = str(self.directory)
        for key, choices in self.OPTIONS.items():
            fields[key] = next((i for i, (value, _) in enumerate(choices)
                                if value == getattr(cfg, key)), 0)
        fields["presetHint"] = get_preset(cfg.transcription_preset).hint_es
        fields["impactHint"] = get_pc_impact(cfg.transcription_pc_impact).hint_es
        return fields

    @Property("QVariantMap", constant=True)
    def choices(self):
        return {name: [label for _, label in choices] for name, choices in self.OPTIONS.items()}

    def _store(self, key, value):
        if getattr(self.config, key) != value:
            setattr(self.config, key, value)
            self.config.save()
            self.changed.emit()
            self.edited.emit(key)

    @Slot(str, bool)
    def flag(self, key, value):
        if key in self.FLAGS:
            self._store(key, value)

    @Slot(str, int)
    def choose(self, key, index):
        choices = self.OPTIONS.get(key, ())
        if 0 <= index < len(choices):
            self._store(key, choices[index][0])

    def set_directory(self, folder):
        path = apply_selected_output_dir(self.config, folder)
        self.config.save()
        self.changed.emit()
        return path

    def transcription_options(self):
        cfg = self.config
        return dict(language=normalize_language(cfg.transcription_language),
                    preset=normalize_preset(cfg.transcription_preset),
                    pc_impact=normalize_pc_impact(cfg.transcription_pc_impact),
                    num_speakers=normalize_num_speakers(cfg.transcription_num_speakers))
