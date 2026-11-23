"""Laptop -> Arduino link. Protocol: "<pan>,<tilt>,<trigger>\\n" at 115200 baud."""
import time

from . import config


def find_arduino_port():
    from serial.tools import list_ports
    keywords = ("arduino", "ch340", "ch341", "usb serial", "usb-serial", "wch", "cp210")
    ports = list(list_ports.comports())
    for p in ports:
        text = f"{p.description} {p.manufacturer or ''}".lower()
        if any(k in text for k in keywords):
            return p.device
    if len(ports) == 1:
        return ports[0].device
    names = ", ".join(f"{p.device} ({p.description})" for p in ports) or "none"
    raise RuntimeError(f"Arduino not found automatically. Ports seen: {names}. "
                       f"Pass --port COMx or set SERIAL_PORT in config.py")


class TurretLink:
    def __init__(self, port=None, baud=config.SERIAL_BAUD, dry_run=False):
        self.dry_run = dry_run
        self._last = None
        self._last_sent_t = 0.0
        if dry_run:
            print("[serial] DRY RUN - no Arduino, commands are only printed on change")
            return
        import serial
        port = port or config.SERIAL_PORT or find_arduino_port()
        self.ser = serial.Serial(port, baud, timeout=0.05, write_timeout=0.1)
        time.sleep(2.0)                       # opening the port resets the Uno; wait for boot
        self.ser.reset_input_buffer()
        print(f"[serial] connected on {port} @ {baud}")

    def send(self, pan, tilt, trigger):
        cmd = (int(round(pan)), int(round(tilt)), 1 if trigger else 0)
        now = time.time()
        changed = cmd != self._last
        if not changed and now - self._last_sent_t < config.SERIAL_HEARTBEAT_S:
            return
        if self.dry_run:
            if changed:
                print(f"[serial] -> {cmd[0]},{cmd[1]},{cmd[2]}")
        else:
            try:
                self.ser.write(f"{cmd[0]},{cmd[1]},{cmd[2]}\n".encode())
            except Exception as e:            # write timeout / unplugged: Arduino watchdog goes safe
                print(f"[serial] write failed: {e}")
        self._last = cmd
        self._last_sent_t = now

    def ping(self):
        if self.dry_run:
            return "DRY RUN"
        self.ser.write(b"?\n")
        return self.ser.readline().decode(errors="ignore").strip()

    def close(self):
        """Always leave the turret safe: trigger off, back home."""
        self._last = None
        self.send(config.PAN_HOME, config.TILT_HOME, False)
        if not self.dry_run:
            time.sleep(0.1)
            self.ser.close()
