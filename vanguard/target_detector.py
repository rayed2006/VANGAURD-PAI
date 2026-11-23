"""
MODULE 1 - Attribute-Based Target Identification
  YOLOv8 (nano) finds people  ->  HSV mask on each person's torso  ->  keep people wearing the chosen colour.
"""
from dataclasses import dataclass, field

import cv2
import numpy as np

from . import config


@dataclass
class Person:
    box: tuple                      # (x1, y1, x2, y2) in pixels
    conf: float
    torso: tuple = None             # (x1, y1, x2, y2)
    color_scores: dict = field(default_factory=dict)

    @property
    def aim_point(self):
        """Centre of the torso box: the turret aims at the chest, never at the head."""
        x1, y1, x2, y2 = self.torso
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)


def torso_box(box, frame_shape):
    x1, y1, x2, y2 = box
    w, h = x2 - x1, y2 - y1
    tx1 = int(x1 + config.TORSO_X[0] * w)
    tx2 = int(x1 + config.TORSO_X[1] * w)
    ty1 = int(y1 + config.TORSO_Y[0] * h)
    ty2 = int(y1 + config.TORSO_Y[1] * h)
    H, W = frame_shape[:2]
    return (max(0, tx1), max(0, ty1), min(W - 1, tx2), min(H - 1, ty2))


# COCO keypoint indices used by YOLOv8-pose
L_SHO, R_SHO, L_HIP, R_HIP = 5, 6, 11, 12


def torso_from_keypoints(kxy, kconf, box, frame_shape, min_conf=0.5):
    """Torso = shoulders -> hips from pose keypoints. Returns None if shoulders aren't visible."""
    if kconf[L_SHO] < min_conf or kconf[R_SHO] < min_conf:
        return None
    sx = sorted([kxy[L_SHO][0], kxy[R_SHO][0]])
    sy = (kxy[L_SHO][1] + kxy[R_SHO][1]) / 2
    cx, sw = (sx[0] + sx[1]) / 2, sx[1] - sx[0]
    sw = max(sw, 0.5 * (box[2] - box[0]))           # person side-on: shoulders overlap
    if kconf[L_HIP] >= min_conf and kconf[R_HIP] >= min_conf:
        hy = (kxy[L_HIP][1] + kxy[R_HIP][1]) / 2      # hips visible: real torso height
    else:
        hy = sy + 1.3 * sw                            # hips out of frame: estimate from shoulder width
    H, W = frame_shape[:2]
    x1, x2 = cx - 0.4 * sw, cx + 0.4 * sw             # inner 80% of the shoulder span (avoid arms)
    y1 = sy + 0.1 * (hy - sy)                         # start just below the collarbone
    return (int(max(0, x1)), int(max(0, y1)), int(min(W - 1, x2)), int(min(H - 1, hy)))


def color_fraction(hsv_roi, color):
    """Fraction (0..1) of pixels in the ROI that fall inside the colour's HSV range(s)."""
    if hsv_roi.size == 0:
        return 0.0
    mask = np.zeros(hsv_roi.shape[:2], dtype=np.uint8)
    for lo, hi in config.COLOR_RANGES[color]:
        mask |= cv2.inRange(hsv_roi, np.array(lo, np.uint8), np.array(hi, np.uint8))
    return float(np.count_nonzero(mask)) / mask.size


class TargetDetector:
    def __init__(self, weights=config.YOLO_WEIGHTS, imgsz=config.YOLO_IMGSZ, conf=config.YOLO_CONF):
        from ultralytics import YOLO
        self.model = YOLO(weights)
        self.imgsz = imgsz
        self.conf = conf

    def detect(self, frame):
        res = self.model.predict(frame, imgsz=self.imgsz, conf=self.conf,
                                 classes=[0], verbose=False)[0]          # class 0 = person
        people = []
        if res.boxes is None or len(res.boxes) == 0:
            return people
        boxes = res.boxes.xyxy.cpu().numpy().astype(int)
        confs = res.boxes.conf.cpu().numpy()
        kps = None
        if getattr(res, "keypoints", None) is not None and res.keypoints.conf is not None:
            kps = (res.keypoints.xy.cpu().numpy(), res.keypoints.conf.cpu().numpy())
        hsv = cv2.cvtColor(cv2.GaussianBlur(frame, (5, 5), 0), cv2.COLOR_BGR2HSV)
        for i, (b, c) in enumerate(zip(boxes, confs)):
            p = Person(box=tuple(int(v) for v in b), conf=float(c))
            p.torso = None
            if kps is not None:
                p.torso = torso_from_keypoints(kps[0][i], kps[1][i], p.box, frame.shape)
            if p.torso is None or p.torso[2] <= p.torso[0] or p.torso[3] <= p.torso[1]:
                p.torso = torso_box(p.box, frame.shape)      # fallback: fixed box ratios
            tx1, ty1, tx2, ty2 = p.torso
            roi = hsv[ty1:ty2, tx1:tx2]
            p.color_scores = {name: color_fraction(roi, name) for name in config.COLOR_RANGES}
            people.append(p)
        return people


def iou(a, b):
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


class TargetSelector:
    """Chooses ONE person to track and sticks with them (no flipping between two people)."""

    def __init__(self):
        self.last_box = None

    def select(self, people, color=None):
        if color:
            candidates = [p for p in people if p.color_scores.get(color, 0) >= config.COLOR_MATCH_MIN]
        else:
            candidates = list(people)
        if not candidates:
            return None

        if self.last_box is not None:                    # 1) stay on the same person if possible
            best = max(candidates, key=lambda p: iou(p.box, self.last_box))
            if iou(best.box, self.last_box) > 0.2:
                self.last_box = best.box
                return best

        if color:                                        # 2) else strongest colour match
            best = max(candidates, key=lambda p: p.color_scores[color])
        else:                                            # 3) else biggest (closest) person
            best = max(candidates, key=lambda p: (p.box[2] - p.box[0]) * (p.box[3] - p.box[1]))
        self.last_box = best.box
        return best

    def reset(self):
        self.last_box = None
