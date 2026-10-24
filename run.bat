@echo off
rem Double-click to start the LogiBridge stack and the dashboard. Close the window or press Ctrl+C to stop.
cd /d "%~dp0"
python run.py %*
pause
