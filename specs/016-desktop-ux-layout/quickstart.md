# Quickstart: 016 UX layout

```powershell
$env:QT_QPA_PLATFORM='offscreen'
$env:PYTHONIOENCODING='utf-8'
.\.venv\Scripts\python.exe -m unittest tests.test_scroll_guard tests.test_desktop_ux_layout tests.test_transcribe_any_file tests.test_preview_async -v
```

Manual: open the app, hover a dropdown without clicking, roll the wheel — the page scrolls, settings stay. Grabar remains at the bottom while you scroll. Open **Opciones de transcripción** to change calidad/idioma/hablantes.
