# Research: 015

## R1 Double convert

Recorder already writes 16 kHz mono PCM. Transcriptor always converted again. Detect PCM WAV 16 kHz mono and reuse the path.

## R2 condition_on_previous_text

Set False in `model.transcribe` to avoid long-meeting repeat loops.

## R3 OOM order

First: model turbo + usable PC, keep speakers. Second: no_diarize.

## R4 Reuse

Stdin daemon dies when the app closes. Pass multiple wavs on argv; cache models in-process; stdout to a log file.

## R5 Speakers N

CLI `--speakers` already exists. Job field `num_speakers` 0 = auto.

## R6 Batch fingerprint

Same language, model, beam, no_diarize, num_speakers, output_base.
