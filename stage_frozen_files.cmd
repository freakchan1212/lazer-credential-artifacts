@echo off
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\stage_frozen_files.ps1"
if errorlevel 1 (
  echo FAILED. Do not commit or publish until this is resolved.
) else (
  echo Done. Review Changes in GitHub Desktop.
)
pause
