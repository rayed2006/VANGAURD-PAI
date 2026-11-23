@echo off
rem Double-click to start the full system (black-shirt tracking + gesture firing).
rem Close the Arduino IDE Serial Monitor first. If the Arduino moved to another COM port, change COM5 below.
cd /d "%~dp0"
.venv\Scripts\python main.py --color black --port COM5
if errorlevel 1 pause
