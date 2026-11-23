"""
Loud beep played on the LAPTOP (the toy gun is silent).

Fires once when the trigger turns ON (armed + locked + on target + gesture), then keeps
firing every SHOT_REPEAT_S seconds while it stays ON. Set SHOT_REPEAT_S = 0 (config.py) for a single shot.

Uses sounds/beep.wav. If that file doesn't exist, a loud 2 kHz beep is generated once.
Drop in your own .wav (same name) to change the sound.
"""
import os
import subprocess
import sys
import time
import wave

import numpy as np

from . import config


def make_beep(path, sr=44100, freq=2000, dur=0.22):
    """Loud alarm-style beep: 2 kHz near-square tone (odd harmonics), short fades to avoid clicks."""
    t = np.arange(int(sr * dur)) / sr
    sig = sum(np.sin(2 * np.pi * freq * k * t) / k for k in (1, 3, 5))  # square-ish = louder, harsher
    fade = int(sr * 0.005)
    env = np.ones_like(t)
    env[:fade] = np.linspace(0, 1, fade)
    env[-fade:] = np.linspace(1, 0, fade)
    sig = sig * env
    sig = sig / (np.max(np.abs(sig)) + 1e-9)
    pcm = (sig * 0.98 * 32767).astype(np.int16)                         # near full volume
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


class GunSound:
    def __init__(self, path=config.SHOT_WAV, repeat_s=config.SHOT_REPEAT_S, enabled=True):
        self.path = os.path.abspath(path)
        self.repeat_s = repeat_s
        self.enabled = enabled
        self._was_on = False
        self._last_shot = 0.0
        if enabled and not os.path.exists(self.path):
            make_beep(self.path)
            print(f"[sound] generated {self.path}")

    def _play(self):
        try:
            if sys.platform.startswith("win"):
                import winsound
                winsound.PlaySound(self.path, winsound.SND_FILENAME | winsound.SND_ASYNC)
            elif sys.platform == "darwin":
                subprocess.Popen(["afplay", self.path],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                subprocess.Popen(["aplay", "-q", self.path],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:                       # never let sound crash the turret loop
            print(f"[sound] could not play: {e}")

    def update(self, trigger):
        """Call once per frame with the trigger state. Returns True on frames where a shot fired."""
        now = time.time()
        fire = False
        if trigger and self.enabled:
            if not self._was_on:                                        # trigger just turned ON
                fire = True
            elif self.repeat_s > 0 and now - self._last_shot >= self.repeat_s:
                fire = True                                             # held: keep firing
        if fire:
            self._play()
            self._last_shot = now
        self._was_on = trigger
        return fire
