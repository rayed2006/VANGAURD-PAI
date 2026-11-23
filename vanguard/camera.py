"""Threaded webcam reader: always hands out the NEWEST frame, so AI lag never builds a backlog."""
import sys
import threading
import time

import cv2


def dshow_index(device_name):
    """Windows camera name (e.g. "USB Camera") -> its current DirectShow index.
    Numbers change when cameras are replugged; names don't."""
    from pygrabber.dshow_graph import FilterGraph
    devices = FilterGraph().get_input_devices()          # same order as cv2.CAP_DSHOW indexes
    if device_name not in devices:
        raise RuntimeError(f"camera '{device_name}' not found. Connected: {devices}")
    return devices.index(device_name)


class CameraStream:
    def __init__(self, index, size=(640, 480), name="cam", rotate_180=False, msmf=False):
        """index: camera number (0, 1, 2...), camera name ("USB Camera") OR a stream URL"""
        if isinstance(index, str) and index.isdigit():
            index = int(index)
        if isinstance(index, str) and "://" not in index:    # a camera name
            index = dshow_index(index)
        if isinstance(index, str):
            self.cap = cv2.VideoCapture(index)                     # network stream (DroidCam / IP Webcam)
        else:
            backend = cv2.CAP_ANY
            if sys.platform.startswith("win"):
                backend = cv2.CAP_MSMF if msmf else cv2.CAP_DSHOW
            self.cap = cv2.VideoCapture(index, backend)
        if not self.cap.isOpened():
            raise RuntimeError(f"[{name}] cannot open camera index {index}. "
                               f"Run tools/test_cameras.py to find the right index.")
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, size[0])
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, size[1])
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.name = name
        self.rotate_180 = rotate_180
        self._frame = None
        self._frame_id = 0
        self._lock = threading.Lock()
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

        t0 = time.time()                       # wait for the first frame
        while self._frame is None and time.time() - t0 < 5:
            time.sleep(0.01)
        if self._frame is None:
            raise RuntimeError(f"[{name}] camera opened but returned no frames")

    def _loop(self):
        while self._running:
            ok, frame = self.cap.read()
            if not ok:
                time.sleep(0.01)
                continue
            if self.rotate_180:                # camera mounted upside down on the turret
                frame = cv2.rotate(frame, cv2.ROTATE_180)
            with self._lock:
                self._frame = frame
                self._frame_id += 1

    def read(self):
        """Returns (frame_copy, frame_id). frame_id lets callers skip frames they already processed."""
        with self._lock:
            return (None if self._frame is None else self._frame.copy()), self._frame_id

    def stop(self):
        self._running = False
        self._thread.join(timeout=1)
        self.cap.release()
