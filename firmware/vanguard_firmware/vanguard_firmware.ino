/*
 * VANGUARD - turret firmware (Arduino Uno)
 *
 * The laptop does all the thinking; the Arduino only:
 *   - receives "<pan>,<tilt>,<trigger>\n" over USB serial at 115200 baud
 *       pan, tilt : integer angles in degrees (clamped to the limits below)
 *       trigger   : 0 = safe, 1 = engage (laser/buzzer ON)
 *   - drives the two servos and the trigger output
 *   - WATCHDOG: if no valid command arrives for WATCHDOG_MS, the trigger is forced OFF
 *     (laptop crash, cable pulled, Python frozen -> always fails safe).
 *
 * Extra commands:
 *   "?\n"  -> replies "VANGUARD OK <pan> <tilt> <trigger>"
 *
 * Pins: PAN servo D9, TILT servo D10, TRIGGER D7 (to transistor base / relay IN), status LED D13.
 */
#include <Servo.h>

// ---------- pins ----------
const uint8_t PAN_PIN     = 9;
const uint8_t TILT_PIN    = 10;
const uint8_t TRIGGER_PIN = 7;
const uint8_t LED_PIN     = 13;

// ---------- limits (tune to your mechanics so nothing hits the frame) ----------
const int PAN_MIN  = 0,  PAN_MAX  = 180;
const int TILT_MIN = 45, TILT_MAX = 135;
const int PAN_HOME = 90, TILT_HOME = 90;

// If your relay module is "active LOW" (most blue 5V relay boards are), set this to true.
const bool TRIGGER_ACTIVE_LOW = false;

const unsigned long WATCHDOG_MS = 500;

Servo panServo, tiltServo;
int  panAngle  = PAN_HOME;
int  tiltAngle = TILT_HOME;
bool triggerOn = false;
unsigned long lastCmdMs = 0;

char buf[32];
uint8_t bufLen = 0;

void setTrigger(bool on) {
  triggerOn = on;
  bool level = TRIGGER_ACTIVE_LOW ? !on : on;
  digitalWrite(TRIGGER_PIN, level ? HIGH : LOW);
  digitalWrite(LED_PIN, on ? HIGH : LOW);
}

void applyCommand(int p, int t, int trig) {
  panAngle  = constrain(p, PAN_MIN, PAN_MAX);
  tiltAngle = constrain(t, TILT_MIN, TILT_MAX);
  panServo.write(panAngle);
  tiltServo.write(tiltAngle);
  setTrigger(trig == 1);
  lastCmdMs = millis();
}

// Parses "123,45,1" without String/sscanf (keeps the Uno fast and RAM-safe).
bool parseLine(const char *s, int &p, int &t, int &trig) {
  int vals[3];
  int idx = 0;
  long cur = 0;
  bool haveDigit = false, neg = false;
  for (const char *c = s; ; ++c) {
    if (*c >= '0' && *c <= '9') {
      cur = cur * 10 + (*c - '0');
      haveDigit = true;
      if (cur > 999) return false;
    } else if (*c == '-' && !haveDigit) {
      neg = true;
    } else if (*c == ',' || *c == '\0') {
      if (!haveDigit || idx >= 3) return false;
      vals[idx++] = neg ? -cur : cur;
      cur = 0; haveDigit = false; neg = false;
      if (*c == '\0') break;
    } else if (*c == ' ' || *c == '\r') {
      // ignore
    } else {
      return false;
    }
  }
  if (idx != 3) return false;
  p = vals[0]; t = vals[1]; trig = vals[2];
  return true;
}

void handleLine(const char *line) {
  if (line[0] == '?') {
    Serial.print(F("VANGUARD OK "));
    Serial.print(panAngle);  Serial.print(' ');
    Serial.print(tiltAngle); Serial.print(' ');
    Serial.println(triggerOn ? 1 : 0);
    lastCmdMs = millis();
    return;
  }
  int p, t, trig;
  if (parseLine(line, p, t, trig)) {
    applyCommand(p, t, trig);
  }
}

void setup() {
  pinMode(TRIGGER_PIN, OUTPUT);
  pinMode(LED_PIN, OUTPUT);
  setTrigger(false);                    // safe before anything else

  panServo.attach(PAN_PIN, 500, 2500);
  tiltServo.attach(TILT_PIN, 500, 2500);
  panServo.write(PAN_HOME);
  tiltServo.write(TILT_HOME);

  Serial.begin(115200);
  Serial.println(F("VANGUARD READY"));
  lastCmdMs = millis();
}

void loop() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\n') {
      buf[bufLen] = '\0';
      if (bufLen > 0) handleLine(buf);
      bufLen = 0;
    } else if (bufLen < sizeof(buf) - 1) {
      buf[bufLen++] = c;
    } else {
      bufLen = 0;                       // overflow -> drop the garbage line
    }
  }

  // Fail-safe: lost contact with the laptop -> trigger OFF (servos hold position).
  if (triggerOn && (millis() - lastCmdMs > WATCHDOG_MS)) {
    setTrigger(false);
  }
}
