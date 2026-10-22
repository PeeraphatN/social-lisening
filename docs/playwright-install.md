# Playwright setup

Use the pinned package and matching Chromium binary:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m playwright install chromium
```

Playwright pairs each library release with specific browser binaries; rerun the
last command after upgrading the pinned package. Keep the default browser cache
unless CI sets `PLAYWRIGHT_BROWSERS_PATH` for both installation and execution.
