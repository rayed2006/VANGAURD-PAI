"""
VANGUARD - main program (ties Modules 1, 2, 3 together)

Run examples:
  python main.py --mvp                       # MVP: any person, pan only, keyboard trigger
  python main.py --color black               # full system: black-shirt target + gesture authorization
  python main.py --color red --dry-run       # no Arduino attached, just watch the AI

Keys (click the TARGET window first):
  a = ARM / DISARM (master safety switch; starts armed if START_ARMED in config.py)
  c = cycle target colour        f = fire 1 s pulse (MVP keyboard mode only)
  r = reset lock (pick a new person)   q / ESC = quit
"""
import argparse
import time

import cv2

from vanguard import config
from vanguard.camera import CameraStream
from vanguard.serial_link import TurretLink
from vanguard.target_detector import TargetDetector, TargetSelector
from vanguard.tracker import TurretController, laser_point
from vanguard.sound import GunSound

COLORS = ["any"] + list(config.COLOR_RANGES.keys())


def parse_args():
    ap = argparse.ArgumentParser(description="VANGUARD turret")
    ap.add_argument("--color", default="any", choices=COLORS, help="clothing colour to lock on")
    ap.add_argument("--mvp", action="store_true", help="MVP mode: any person, pan only, keyboard trigger")
    ap.add_argument("--no-tilt", action="store_true", help="disable tilt axis")
    ap.add_argument("--keyboard-trigger", action="store_true", help="use 'f' key instead of gesture")
    ap.add_argument("--dry-run", action="store_true", help="run without Arduino")
    ap.add_argument("--mute", action="store_true", help="no gunshot sound from the laptop")
    ap.add_argument("--port", default=None, help="serial port, e.g. COM5")
    ap.add_argument("--target-cam", default=config.TARGET_CAM_INDEX, help="index (0,1,2) or stream URL")
    ap.add_argument("--operator-cam", default=config.OPERATOR_CAM_INDEX, help="index (0,1,2) or stream URL")
    return ap.parse_args()


def draw_hud(frame, people, target, state, color, armed, trigger, fps, err):
    h, w = frame.shape[:2]
    for p in people:
        x1, y1, x2, y2 = p.box
        cv2.rectangle(frame, (x1, y1), (x2, y2), (160, 160, 160), 1)
        if color != "any":
            cv2.putText(frame, f"{color}:{p.color_scores.get(color, 0):.2f}", (x1, y1 - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)
    if target is not None:
        x1, y1, x2, y2 = target.box
        col = (0, 0, 255) if trigger else (0, 255, 0)
        cv2.rectangle(frame, (x1, y1), (x2, y2), col, 2)
        tx1, ty1, tx2, ty2 = target.torso
        cv2.rectangle(frame, (tx1, ty1), (tx2, ty2), col, 1)
        ax, ay = map(int, target.aim_point)
        cv2.circle(frame, (ax, ay), 5, col, -1)
    lx, ly = map(int, laser_point(w, h))                                    # crosshair = where the laser hits
    cv2.line(frame, (lx - 15, ly), (lx + 15, ly), (255, 255, 255), 1)
    cv2.line(frame, (lx, ly - 15), (lx, ly + 15), (255, 255, 255), 1)

    lines = [f"STATE: {state}   COLOR: {color}   FPS: {fps:.1f}",
             f"ARMED: {'YES' if armed else 'no'}   TRIGGER: {'ON' if trigger else 'off'}   "
             f"err=({err[0]:+.2f},{err[1]:+.2f})"]
    for i, t in enumerate(lines):
        cv2.putText(frame, t, (10, 22 + 22 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                    (0, 0, 255) if trigger else (0, 255, 255), 2)


def main():
    args = parse_args()
    if args.mvp:
        args.color, args.no_tilt, args.keyboard_trigger = "any", True, True

    print("[init] loading YOLO ...")
    detector = TargetDetector()
    selector = TargetSelector()
    ctrl = TurretController(use_tilt=not args.no_tilt)
    link = TurretLink(port=args.port, dry_run=args.dry_run)
    target_cam = CameraStream(args.target_cam, config.TARGET_CAM_SIZE, "target", config.TARGET_CAM_ROTATE_180)

    gesture_worker = None
    if not args.keyboard_trigger:
        from vanguard.gesture_auth import GestureWorker
        operator_cam = CameraStream(args.operator_cam, config.OPERATOR_CAM_SIZE, "operator",
                                    msmf=config.OPERATOR_CAM_MSMF)
        gesture_worker = GestureWorker(operator_cam)

    color = args.color
    armed = config.START_ARMED
    fire_until = 0.0
    gun = GunSound(enabled=not args.mute)
    bang_until = 0.0
    lost = 0
    last_id = -1
    fps, t_prev = 0.0, time.time()
    pan, tilt = float(config.PAN_HOME), float(config.TILT_HOME)

    try:
        while True:
            frame, fid = target_cam.read()
            if frame is None or fid == last_id:
                time.sleep(0.002)
                continue
            last_id = fid
            h, w = frame.shape[:2]

            # ---- Module 1: who is the target? ----
            people = detector.detect(frame)
            target = selector.select(people, None if color == "any" else color)

            # ---- Module 2: move the turret ----
            on_target = False
            if target is not None:
                lost = 0
                ax, ay = target.aim_point
                pan, tilt, on_target = ctrl.track(ax, ay, w, h)
                state = "LOCKED" if on_target else "TRACKING"
            else:
                lost += 1
                ctrl.reset_smoothing()
                if lost > config.LOST_FRAMES_BEFORE_SCAN:
                    selector.reset()
                    pan, tilt = ctrl.scan()
                    state = "SCANNING"
                else:
                    state = "LOST"          # hold position briefly, target may reappear

            # ---- Module 3: is the operator authorizing? ----
            if gesture_worker is not None:
                gesture, authorized, op_view = gesture_worker.state()
                if op_view is not None:
                    cv2.imshow("VANGUARD - operator", op_view)
            else:
                authorized = time.time() < fire_until

            # ---- Safety interlock: ALL conditions must hold ----
            trigger = armed and target is not None and on_target and authorized
            link.send(pan, tilt, trigger)
            if gun.update(trigger):                    # laptop plays the gunshot
                bang_until = time.time() + 0.15

            now = time.time()
            fps = 0.9 * fps + 0.1 * (1.0 / max(now - t_prev, 1e-3))
            t_prev = now
            draw_hud(frame, people, target, state, color, armed, trigger, fps, ctrl.err)
            if time.time() < bang_until:                 # muzzle-flash text on screen
                h0, w0 = frame.shape[:2]
                cv2.putText(frame, "BANG!", (w0 // 2 - 70, h0 // 2 - 40),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.6, (0, 0, 255), 4)
            cv2.imshow("VANGUARD - target", frame)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
            elif key == ord("a"):
                armed = not armed
                print(f"[key] {'ARMED' if armed else 'DISARMED'}")
            elif key == ord("c"):
                color = COLORS[(COLORS.index(color) + 1) % len(COLORS)]
                selector.reset()
                print(f"[key] target colour -> {color}")
            elif key == ord("r"):
                selector.reset()
            elif key == ord("f") and args.keyboard_trigger:
                fire_until = time.time() + 1.0
    finally:
        link.close()                      # trigger off + home, always
        target_cam.stop()
        if gesture_worker is not None:
            gesture_worker.stop()
            gesture_worker.camera.stop()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
