"""
MODULE 2 - Proportional Servo-Tracking

The camera is mounted ON the turret, so the goal is simply: keep the aim point at the image centre.

  error  = (aim_x - centre_x) / centre_x            -> -1 (far left) .. +1 (far right)
  angle_error_deg = error * (FOV / 2)               -> how many degrees off we are
  step  = Kp * angle_error_deg                       (proportional control)
  step  = clamp(step, -MAX_STEP, +MAX_STEP)          (no violent jumps)
  |error| < DEADBAND  -> step = 0                    (no jitter when already aimed)

Far from centre -> big step, near centre -> small step: that is the "proportional smoothing".
"""
from . import config


def laser_point(frame_w, frame_h):
    """Pixel where the laser dot lands in the turret image (image centre + calibrated offset)."""
    return frame_w / 2 + config.AIM_OFFSET_PX[0], frame_h / 2 + config.AIM_OFFSET_PX[1]


class AxisController:
    def __init__(self, kp, half_fov_deg, limits, home, invert=False,
                 deadband=config.DEADBAND, max_step=config.MAX_STEP_DEG):
        self.kp = kp
        self.half_fov = half_fov_deg
        self.lo, self.hi = limits
        self.home = home
        self.sign = -1.0 if invert else 1.0
        self.deadband = deadband
        self.max_step = max_step
        self.angle = float(home)

    def update(self, error):
        """error in -1..1. Returns the new servo angle."""
        if abs(error) < self.deadband:
            return self.angle
        step = self.kp * error * self.half_fov
        step = max(-self.max_step, min(self.max_step, step))
        self.angle = max(self.lo, min(self.hi, self.angle + self.sign * step))
        return self.angle

    def nudge(self, delta):
        self.angle = max(self.lo, min(self.hi, self.angle + delta))
        return self.angle


class TurretController:
    def __init__(self, use_tilt=True):
        self.pan = AxisController(config.KP_PAN, config.CAM_HFOV_DEG / 2, config.PAN_LIMITS,
                                  config.PAN_HOME, config.INVERT_PAN)
        # Image y grows DOWNWARD, so a target below centre gives +error; INVERT_TILT fixes servo direction.
        self.tilt = AxisController(config.KP_TILT, config.CAM_VFOV_DEG / 2, config.TILT_LIMITS,
                                   config.TILT_HOME, config.INVERT_TILT)
        self.use_tilt = use_tilt
        self._sx = self._sy = None
        self._scan_dir = 1.0
        self.err = (0.0, 0.0)

    def reset_smoothing(self):
        self._sx = self._sy = None

    def track(self, aim_x, aim_y, frame_w, frame_h):
        """Returns (pan_angle, tilt_angle, on_target)."""
        a = config.EMA_ALPHA                                   # exponential moving average
        self._sx = aim_x if self._sx is None else a * aim_x + (1 - a) * self._sx
        self._sy = aim_y if self._sy is None else a * aim_y + (1 - a) * self._sy

        # steer the target onto where the LASER hits (camera is glued ~10 deg off the barrel), not the image centre
        lx, ly = laser_point(frame_w, frame_h)
        ex = (self._sx - lx) / (frame_w / 2)
        ey = (self._sy - ly) / (frame_h / 2)
        self.err = (ex, ey)

        self.pan.update(ex)
        if self.use_tilt:
            self.tilt.update(ey)
            on_target = abs(ex) < config.ON_TARGET_TOL and abs(ey) < config.ON_TARGET_TOL
        else:
            on_target = abs(ex) < config.ON_TARGET_TOL
        return self.pan.angle, self.tilt.angle, on_target

    def scan(self):
        """Nobody found: sweep pan back and forth, ease tilt back to home."""
        self.reset_smoothing()
        a = self.pan.nudge(self._scan_dir * config.SCAN_STEP_DEG)
        if a >= self.pan.hi or a <= self.pan.lo:
            self._scan_dir *= -1
        t = self.tilt.angle
        if abs(t - self.tilt.home) > 1:
            self.tilt.nudge(1.0 if t < self.tilt.home else -1.0)
        return self.pan.angle, self.tilt.angle
