@echo off
rem Double-click to start the MVP: any person, pan only, keyboard trigger (F = fire, A = arm/disarm, Q = quit).
rem Close the Arduino IDE Serial Monitor first. If the Arduino moved to another COM port, change COM5 below.
cd /d "%~dp0"
.venv\Scripts\python main.py --mvp --port COM5
if errorlevel 1 pause
