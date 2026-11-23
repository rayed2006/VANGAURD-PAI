"""
MODULE 3 - Remote Gesture Authorization (operator's laptop camera)

MediaPipe Hand Landmarker gives 21 points per hand:
      4   8  12  16  20      <- finger tips
      3   7  11  15  19
      2   6  10  14  18      <- PIP joints
      1   5   9  13  17      <- knuckles (MCP)
              0              <- wrist
Rule set (distance based, works at any hand rotation):
  finger extended  <=>  dist(wrist, tip) > 1.15 * dist(wrist, PIP)
  thumb extended   <=>  tip further from pinky knuckle (17) than its IP joint (3)
                        AND tip far enough from the index knuckle (5)
"""
import os
import threading
import time
import urllib.request

import cv2
import numpy as np

from . import config

WRIST = 0
FINGERS = {"index": (8, 6), "middle": (12, 10), "ring": (16, 14), "pinky": (20, 18)}
HAND_EDGES = [(0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7), (7, 8), (5, 9), (9, 10),
              (10, 11), (11, 12), (9, 13), (13, 14), (14, 15), (15, 16), (13, 17), (0, 17),
              (17, 18), (18, 19), (19, 20)]


def _d(pts, a, b):
    return float(np.linalg.norm(pts[a] - pts[b]))


def finger_states(pts):
    """pts: (21, 2) array in pixel units. Returns dict finger -> extended(bool)."""
    states = {name: _d(pts, WRIST, tip) > 1.15 * _d(pts, WRIST, pip)
              for name, (tip, pip) in FINGERS.items()}
    palm = _d(pts, 0, 9) + 1e-6
    states["thumb"] = (_d(pts, 4, 17) > _d(pts, 3, 17)) and (_d(pts, 4, 5) > 0.45 * palm)
    return states


def classify(pts):
    s = finger_states(pts)
    four = [s["index"], s["middle"], s["ring"], s["pinky"]]
    if all(four) and s["thumb"]:
        return "OPEN_PALM"
    if not any(four):
        return "FIST"
    if s["index"] and s["middle"] and not s["ring"] and not s["pinky"]:
        return "V_SIGN"
    if s["index"] and not s["middle"] and not s["ring"] and not s["pinky"]:
        return "POINT"
    return "UNKNOWN"


class Authorizer:
    """Turns per-frame gesture labels into a debounced, fail-safe AUTHORIZED flag."""

    def __init__(self, auth_gesture=config.AUTH_GESTURE, hold_s=config.AUTH_HOLD_S,
                 grace_s=config.RELEASE_GRACE_S):
        self.auth_gesture = auth_gesture
        self.hold_s = hold_s
        self.grace_s = grace_s
        self._since = None          # when the auth gesture started
        self._last_seen = 0.0
        self.authorized = False

    def update(self, gesture, now=None):
        now = time.time() if now is None else now
        if gesture == self.auth_gesture:
            if self._since is None:
                self._since = now
            self._last_seen = now
            if now - self._since >= self.hold_s:
                self.authorized = True
        elif gesture == "FIST":                       # deliberate "stop" -> instantly safe
            self._since = None
            self.authorized = False
        else:                                         # no hand / other gesture
            if now - self._last_seen > self.grace_s:
                self._since = None
                self.authorized = False
        return self.authorized


def ensure_model(path=config.HAND_MODEL_PATH, url=config.HAND_MODEL_URL):
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        print(f"[gesture] downloading hand model -> {path}")
        urllib.request.urlretrieve(url, path)
    return path


class HandGestureRecognizer:
    def __init__(self, model_path=config.HAND_MODEL_PATH):
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision
        self._mp = mp
        opts = vision.HandLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=ensure_model(model_path)),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=1,
            min_hand_detection_confidence=0.6,
            min_hand_presence_confidence=0.6,
            min_tracking_confidence=0.5)
        self.landmarker = vision.HandLandmarker.create_from_options(opts)
        self._t0 = time.time()
        self._last_ts = -1

    def process(self, frame_bgr):
        """Returns (gesture_label, pts or None)."""
        h, w = frame_bgr.shape[:2]
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)
        ts = int((time.time() - self._t0) * 1000)
        ts = max(ts, self._last_ts + 1)                # VIDEO mode needs strictly increasing timestamps
        self._last_ts = ts
        result = self.landmarker.detect_for_video(image, ts)
        if not result.hand_landmarks:
            return "NONE", None
        lm = result.hand_landmarks[0]
        pts = np.array([[p.x * w, p.y * h] for p in lm], dtype=np.float32)
        return classify(pts), pts

    def close(self):
        self.landmarker.close()


def draw_hand(frame, pts, color=(0, 255, 255)):
    if pts is None:
        return
    for a, b in HAND_EDGES:
        cv2.line(frame, tuple(pts[a].astype(int)), tuple(pts[b].astype(int)), color, 2)
    for p in pts:
        cv2.circle(frame, tuple(p.astype(int)), 3, (255, 255, 255), -1)


class GestureWorker:
    """Runs Module 3 in its own thread on the operator camera, so it never slows down targeting."""

    def __init__(self, camera, authorizer=None):
        self.camera = camera
        self.authorizer = authorizer or Authorizer()
        self.recognizer = HandGestureRecognizer()
        self.gesture = "NONE"
        self.authorized = False
        self.view = None
        self.updated_at = 0.0
        self._lock = threading.Lock()
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        last_id = -1
        while self._running:
            frame, fid = self.camera.read()
            if frame is None or fid == last_id:
                time.sleep(0.005)
                continue
            last_id = fid
            frame = cv2.flip(frame, 1)                 # mirror view feels natural for the operator
            gesture, pts = self.recognizer.process(frame)
            auth = self.authorizer.update(gesture)
            draw_hand(frame, pts, (0, 0, 255) if auth else (0, 255, 255))
            label = f"{gesture}  ->  {'AUTHORIZED' if auth else 'SAFE'}"
            cv2.putText(frame, label, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                        (0, 0, 255) if auth else (0, 200, 0), 2)
            with self._lock:
                self.gesture, self.authorized, self.view = gesture, auth, frame
                self.updated_at = time.time()

    def state(self, max_age_s=0.5):
        """(gesture, authorized, view). A stale result (camera froze) is never treated as authorized."""
        with self._lock:
            fresh = time.time() - self.updated_at < max_age_s
            return self.gesture, (self.authorized and fresh), self.view

    def stop(self):
        self._running = False
        self._thread.join(timeout=1)
        self.recognizer.close()
