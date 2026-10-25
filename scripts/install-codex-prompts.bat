@echo off
setlocal

REM Install the checked-in packages without relying on Python or Store aliases.
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-codex.ps1" -IncludePrompts %*
exit /b %ERRORLEVEL%
