# VANGUARD – vision-guided, gesture-authorized turret

A pan/tilt turret that finds a person wearing a chosen shirt colour, aims a laser at their chest,
and fires only while a human operator shows an **open palm** to the laptop camera.

The laptop does all the thinking (Python, YOLOv8-pose, MediaPipe); an Arduino Uno only drives the
two servos and the trigger, and fails safe on its own if the laptop stops talking.

## How it works

```
Turret webcam ─► Module 1  find people (YOLOv8-pose), pick the one in the target shirt colour
                    │ aim point (chest)
                    ▼
                 Module 2  proportional servo tracking → pan / tilt angles
Laptop camera ─► Module 3  hand gesture (MediaPipe): open palm = AUTHORIZED, fist = instant SAFE
                    ▼
                 Safety interlock: fire ONLY if armed AND target AND locked on AND authorized
                    │ "pan,tilt,trigger\n" over USB serial (115200 baud)
                    ▼
                 Arduino Uno → pan servo, tilt servo, laser/trigger   (500 ms watchdog → trigger OFF)
```

## Hardware

| Part | Arduino pin |
|---|---|
| Pan servo signal | D9 |
| Tilt servo signal | D10 |
| Trigger (laser / transistor / relay) | D7 |
| Status LED | D13 |

Servos are powered from an external supply with its GND tied to the Arduino GND.
Turret camera: any USB (UVC) webcam. Operator camera: the laptop's built-in webcam.

## Setup (Windows)

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```
Upload `firmware/vanguard_firmware/vanguard_firmware.ino` to the Arduino Uno (Arduino IDE, board "Arduino Uno").
The YOLO and hand models download automatically on the first run.

## Run

Double-click **`Start VANGUARD.bat`**, or:
```
.venv\Scripts\python main.py --color black --port COM5
```
For the MVP (any person, pan only, keyboard trigger **F**), double-click **`Start MVP.bat`**
(`.venv\Scripts\python main.py --mvp --port COM5`).
Useful options: `--dry-run` (no Arduino), `--keyboard-trigger` (F key instead of gestures),
`--no-tilt`, `--mvp` (any person, pan only, keyboard trigger).

Keys in the target window: **A** arm/disarm (starts armed) · **C** change colour · **R** pick a new target · **Q** quit.

## Calibration

| Launcher | Tool | Purpose |
|---|---|---|
| `Calibrate laser aim.bat` | `tools/manual_jog.py` | Drive the turret by keyboard; turn the laser on and **click the dot** → paste `AIM_OFFSET_PX` into `vanguard/config.py` |
| `Tune shirt colour.bat` | `tools/hsv_tuner.py` | Adjust HSV sliders until only the shirt is white → paste into `COLOR_RANGES` |
| – | `tools/test_cameras.py` | Show which camera index is which |

All settings (camera indexes, COM port, servo limits/directions, colours, gains, aim offset) are in
**`vanguard/config.py`**.

## Files

| Path | Role |
|---|---|
| `main.py` | Main loop: camera → detect → track → gesture → safety interlock → Arduino |
| `vanguard/config.py` | All tunable settings |
| `vanguard/camera.py` | Threaded camera reader (always the newest frame) |
| `vanguard/target_detector.py` | Module 1: person detection, torso box, shirt-colour scoring, target selection |
| `vanguard/tracker.py` | Module 2: proportional pan/tilt control, scanning, aim offset |
| `vanguard/gesture_auth.py` | Module 3: hand landmarks → gesture → debounced authorization |
| `vanguard/serial_link.py` | USB serial link to the Arduino (fails safe on close) |
| `vanguard/sound.py` | Laptop "shot" sound while firing |
| `firmware/vanguard_firmware/` | Arduino Uno firmware with watchdog |
| `tools/` | Calibration and test helpers |
