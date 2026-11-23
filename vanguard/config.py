"""
VANGUARD - all tunable settings in one place.
Change values here, not inside the modules.
"""

# ---------------- Cameras ----------------
# Turret webcam is picked by its Windows NAME, because camera numbers change when it's replugged.
# Run tools/test_cameras.py to see the names. The operator cam uses Media Foundation (1 = HP laptop cam).
TARGET_CAM_INDEX = "USB Camera"   # external USB webcam on the turret (name or DirectShow number)
OPERATOR_CAM_INDEX = 1      # built-in laptop webcam
TARGET_CAM_SIZE = (1280, 720)   # GY-891 only offers 1280x720 over DirectShow
OPERATOR_CAM_SIZE = (640, 480)
OPERATOR_CAM_MSMF = True        # HP laptop cam gives black frames via DirectShow next to the webcam; Media Foundation works
TARGET_CAM_ROTATE_180 = True    # webcam is mounted upside down on the gun

# Field of view of the TURRET camera (degrees). GY-891 3.6 mm lens: ~60 assumed, measure during alignment.
CAM_HFOV_DEG = 60.0
CAM_VFOV_DEG = 36.0         # 16:9 frame -> 2*atan(tan(30 deg) * 9/16)

# Where the laser dot lands, in turret-camera pixels from the image centre (+x right, +y down).
# The webcam is glued ~10 deg above the barrel, so targets are steered onto this point instead of the centre.
# Calibrate: python tools/manual_jog.py --port COM5, laser on, click the dot -> paste the printed line here.
# shortcut: one fixed offset is exact only at the distance it was calibrated at (calibrate at demo distance).
START_ARMED = True          # turret is armed at start; 'a' still toggles it as a keyboard kill switch
AIM_OFFSET_PX = (61, 171)   # clicked on the laser dot in manual_jog, 20 Nov

# ---------------- Serial / Arduino ----------------
SERIAL_PORT = None          # None = auto-detect. Or e.g. "COM5" (Windows) / "/dev/ttyUSB0" (Linux)
SERIAL_BAUD = 115200
SERIAL_HEARTBEAT_S = 0.10   # resend even if nothing changed (Arduino watchdog is 500 ms)

# ---------------- Module 1: detection ----------------
YOLO_WEIGHTS = "yolov8n-pose.pt"  # nano pose model (~7 MB, auto-download): person box + shoulders/hips.
                                  # Plain "yolov8n.pt" also works (torso then guessed from box ratios).
YOLO_IMGSZ = 320             # 320 is fast on CPU; try 416/480 if detections are weak
YOLO_CONF = 0.45
COLOR_MATCH_MIN = 0.30       # fraction of torso pixels that must match the colour

# Torso region inside a person box (fractions of box width / height).
TORSO_X = (0.25, 0.75)
TORSO_Y = (0.22, 0.55)

# HSV ranges (OpenCV: H 0-179, S 0-255, V 0-255). Tune with tools/hsv_tuner.py under YOUR lighting.
COLOR_RANGES = {
    "black":  [((0, 0, 0), (179, 255, 60))],
    "white":  [((0, 0, 170), (179, 45, 255))],
    "red":    [((0, 90, 70), (10, 255, 255)), ((170, 90, 70), (179, 255, 255))],
    "orange": [((11, 110, 100), (22, 255, 255))],
    "yellow": [((23, 90, 100), (34, 255, 255))],
    "green":  [((35, 60, 50), (85, 255, 255))],
    "blue":   [((90, 80, 40), (130, 255, 255))],
}

# ---------------- Module 2: tracking ----------------
PAN_LIMITS = (0, 180)
TILT_LIMITS = (45, 135)      # must match TILT_MIN/TILT_MAX in the Arduino sketch
PAN_HOME = 90
TILT_HOME = 90

# Kp = fraction of the angular error corrected per frame (0..1). Start low, raise until it
# tracks briskly; lower it if the turret overshoots / oscillates.
KP_PAN = 0.15
KP_TILT = 0.15
MAX_STEP_DEG = 5.0           # never move more than this per frame
DEADBAND = 0.04              # ignore errors smaller than 4% of half-frame (kills jitter)
EMA_ALPHA = 0.7              # smoothing of the target point (1 = no smoothing)
ON_TARGET_TOL = 0.10         # |error| below this on both axes counts as "aimed"

# Flip these if the turret moves AWAY from the target instead of toward it.
INVERT_PAN = True            # on this turret a higher pan angle turns LEFT (checked with manual_jog)
INVERT_TILT = True           # on this turret a higher tilt angle points UP (checked with manual_jog)

# Scanning when nobody is found
SCAN_STEP_DEG = 1.5
LOST_FRAMES_BEFORE_SCAN = 15  # ~0.75 s at 20 FPS

# ---------------- Module 3: gesture ----------------
HAND_MODEL_PATH = "models/hand_landmarker.task"
HAND_MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
                  "hand_landmarker/float16/latest/hand_landmarker.task")
AUTH_GESTURE = "OPEN_PALM"     # OPEN_PALM | V_SIGN | POINT
AUTH_HOLD_S = 0.40             # gesture must be held this long before engaging
RELEASE_GRACE_S = 0.15         # hand briefly lost -> wait this long before going safe (FIST = instant)

# ---------------- Engagement sound (laptop speaker) ----------------
SHOT_WAV = "sounds/beep.wav"      # loud 2 kHz beep, auto-generated on first run; replace with your own .wav to change it
SHOT_REPEAT_S = 0.35              # fire again every 0.35 s while the trigger is held (0 = one shot only)
