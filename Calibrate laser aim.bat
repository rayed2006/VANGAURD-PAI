@echo off
rem Manual jog: SPACE = laser on, click the laser dot, paste the printed AIM_OFFSET_PX line into vanguard\config.py. Q = quit.
cd /d "%~dp0"
.venv\Scripts\python tools\manual_jog.py --port COM5
pause
