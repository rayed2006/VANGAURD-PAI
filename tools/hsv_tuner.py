"""
Step 7: tune HSV colour ranges under the lighting you will demo in.
Stand in front of the USB cam wearing the shirt, drag sliders until ONLY the shirt is white in the mask,
then copy the printed range into COLOR_RANGES in vanguard/config.py.   q = quit, p = print range
"""
import argparse
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from vanguard import config  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--cam", default=config.TARGET_CAM_INDEX, help="index (0,1,2) or stream URL")
ap.add_argument("--start", default="black", choices=list(config.COLOR_RANGES))
args = ap.parse_args()

lo, hi = config.COLOR_RANGES[args.start][0]
cv2.namedWindow("tuner")
for name, val, mx in [("H lo", lo[0], 179), ("S lo", lo[1], 255), ("V lo", lo[2], 255),
                      ("H hi", hi[0], 179), ("S hi", hi[1], 255), ("V hi", hi[2], 255)]:
    cv2.createTrackbar(name, "tuner", val, mx, lambda _: None)

cap = cv2.VideoCapture(int(args.cam) if str(args.cam).isdigit() else args.cam)
while True:
    ok, frame = cap.read()
    if not ok:
        break
    hsv = cv2.cvtColor(cv2.GaussianBlur(frame, (5, 5), 0), cv2.COLOR_BGR2HSV)
    g = lambda n: cv2.getTrackbarPos(n, "tuner")                         # noqa: E731
    L = (g("H lo"), g("S lo"), g("V lo"))
    H = (g("H hi"), g("S hi"), g("V hi"))
    mask = cv2.inRange(hsv, np.array(L, np.uint8), np.array(H, np.uint8))
    both = np.hstack([frame, cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)])
    cv2.imshow("tuner", cv2.resize(both, None, fx=0.75, fy=0.75))
    k = cv2.waitKey(1) & 0xFF
    if k == ord("p"):
        print(f'"{args.start}": [(({L[0]}, {L[1]}, {L[2]}), ({H[0]}, {H[1]}, {H[2]}))],')
    if k == ord("q"):
        print(f'"{args.start}": [(({L[0]}, {L[1]}, {L[2]}), ({H[0]}, {H[1]}, {H[2]}))],')
        break
cap.release()
cv2.destroyAllWindows()
