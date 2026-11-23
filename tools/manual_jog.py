"""
Step 5b: drive the turret by keyboard to test serial + mechanics (no AI).
  A/D = pan  W/S = tilt  SPACE = toggle trigger  H = home  Q = quit
  LEFT-CLICK on the laser dot = calibrate the aim point (prints the AIM_OFFSET_PX line for config.py)
Watch the USB camera view: when you press D the image should move as if the turret turns RIGHT.
If it turns left instead, set INVERT_PAN = True in vanguard/config.py (same idea for tilt with W/S).
Red cross = image centre, green cross = where the laser should hit (AIM_OFFSET_PX).
"""
import argparse
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from vanguard import config                      # noqa: E402
from vanguard.serial_link import TurretLink      # noqa: E402
from vanguard.camera import CameraStream         # noqa: E402
from vanguard.tracker import laser_point         # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--port", default=None)
ap.add_argument("--cam", type=lambda s: int(s) if s.isdigit() else s,
                default=config.TARGET_CAM_INDEX,
                help="camera index (0,1,2) or stream URL")
ap.add_argument("--dry-run", action="store_true")
args = ap.parse_args()

link = TurretLink(args.port, dry_run=args.dry_run)
print("ping:", link.ping())
try:
    cam = CameraStream(args.cam, config.TARGET_CAM_SIZE, "jog", config.TARGET_CAM_ROTATE_180)    # newest frame, no backlog
except RuntimeError as e:
    print(e, "- continuing with a blank window")
    cam = None
pan, tilt, trig = config.PAN_HOME, config.TILT_HOME, False
STEP = 3
# same convention as tracker.py: D = toward +x (right), S = toward +y (down), honouring the INVERT flags,
# so if these keys move the right way here, auto-tracking will move the right way too
PAN_SIGN = -1 if config.INVERT_PAN else 1
TILT_SIGN = -1 if config.INVERT_TILT else 1
size = {"w": 1, "h": 1}


def on_click(event, x, y, *_):
    if event == cv2.EVENT_LBUTTONDOWN:
        config.AIM_OFFSET_PX = (x - size["w"] // 2, y - size["h"] // 2)   # live preview of the new green cross
        print(f"AIM_OFFSET_PX = {config.AIM_OFFSET_PX}   <- paste into vanguard/config.py")


cv2.namedWindow("manual jog")
cv2.setMouseCallback("manual jog", on_click)
try:
    while True:
        frame = cam.read()[0] if cam else None
        if frame is None:
            frame = np.full((240, 480, 3), 40, np.uint8)      # no camera: blank window still takes keys
        h, w = frame.shape[:2]
        size["w"], size["h"] = w, h
        cv2.drawMarker(frame, (w // 2, h // 2), (0, 0, 255), cv2.MARKER_CROSS, 30, 2)
        cv2.drawMarker(frame, tuple(map(int, laser_point(w, h))), (0, 255, 0), cv2.MARKER_CROSS, 40, 2)
        cv2.putText(frame, f"pan={pan} tilt={tilt} trigger={int(trig)}", (10, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        cv2.imshow("manual jog", frame)
        k = cv2.waitKey(30) & 0xFF
        if k == ord("q"):
            break
        elif k == ord("a"):
            pan -= PAN_SIGN * STEP
        elif k == ord("d"):
            pan += PAN_SIGN * STEP
        elif k == ord("w"):
            tilt -= TILT_SIGN * STEP
        elif k == ord("s"):
            tilt += TILT_SIGN * STEP
        elif k == ord(" "):
            trig = not trig
        elif k == ord("h"):
            pan, tilt = config.PAN_HOME, config.TILT_HOME
        pan = max(config.PAN_LIMITS[0], min(config.PAN_LIMITS[1], pan))
        tilt = max(config.TILT_LIMITS[0], min(config.TILT_LIMITS[1], tilt))
        link.send(pan, tilt, trig)               # sent every loop -> keeps the watchdog fed
finally:
    link.close()
    if cam:
        cam.stop()
    cv2.destroyAllWindows()
