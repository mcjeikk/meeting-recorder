# Tasks: 013-transcription-oom-queue

- [x] T001 `process_guard.py` OOM + adopt/dedupe transcribe.py
- [x] T002 Worker: adopt before spawn; reconcile by WAV; OOM degrade
- [x] T003 Queue counts + banner line; retry degrades OOM jobs
- [x] T004 Single-instance mutex in `app/main.py`
- [x] T005 Unit tests `tests/test_process_guard.py`
- [x] T006 Cola visible: una fila por archivo (`queue_status.py` + `QListWidget` en sección 4)
