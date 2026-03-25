@echo off
setlocal
powershell -ExecutionPolicy Bypass -File "%~dp0scripts\build_release.ps1"
if errorlevel 1 (
  echo.
  echo Build failed.
  exit /b 1
)
echo.
echo Build finished.
