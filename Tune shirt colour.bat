@echo off
rem Lower "V hi" until only the black shirt is white, press P, paste the printed line into COLOR_RANGES in vanguard\config.py. Q = quit.
cd /d "%~dp0"
.venv\Scripts\python tools\hsv_tuner.py --start black
pause
