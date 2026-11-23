"""Show each camera with its index and Windows name (use the name in config.py). Any key = next, q = quit."""
import sys

import cv2

backend = cv2.CAP_DSHOW if sys.platform.startswith("win") else cv2.CAP_ANY
try:
    from pygrabber.dshow_graph import FilterGraph
    print("cameras (index: name):", dict(enumerate(FilterGraph().get_input_devices())))
except ImportError:
    pass
for idx in range(5):
    cap = cv2.VideoCapture(idx, backend)
    ok, frame = cap.read() if cap.isOpened() else (False, None)
    if not ok:
        print(f"index {idx}: nothing")
        cap.release()
        continue
    print(f"index {idx}: OK {frame.shape[1]}x{frame.shape[0]}  (window open - press a key)")
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        cv2.putText(frame, f"CAMERA INDEX {idx}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.imshow("camera test", frame)
        k = cv2.waitKey(1) & 0xFF
        if k != 255:
            break
    cap.release()
    if k == ord("q"):
        break
cv2.destroyAllWindows()
