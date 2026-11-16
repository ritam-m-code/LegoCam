"""A camera that always hands you the newest frame.

A background thread does nothing but read frames as fast as the camera
produces them, keeping only the most recent one. The main loop then never
waits on the camera and never receives a frame that has been sitting in a
driver buffer since several seconds ago.

Exposure and gain are pinned to fixed values. This matters more than it
looks: if the camera is free to adjust its own exposure, the brightness of
the image changes when you swap parts, the threshold that separates part
from background moves with it, and the measured size drifts.
"""

import threading
import time

import cv2


class CameraError(Exception):
    """The camera could not be opened, or stopped delivering frames."""


class Camera:
    def __init__(self, settings):
        self._settings = settings
        self._frame = None
        self._taken_at = 0.0
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self.error = None

        self._thread = threading.Thread(target=self._read_forever, daemon=True)
        self._thread.start()

    def latest(self):
        """Return (frame, age_in_seconds), or None before the first frame."""
        with self._lock:
            if self._frame is None:
                return None
            return self._frame, time.monotonic() - self._taken_at

    def wait_for_first_frame(self, timeout=60):
        deadline = time.monotonic() + timeout
        while self.latest() is None:
            if self.error:
                raise CameraError(self.error)
            if time.monotonic() > deadline:
                raise CameraError("Timed out waiting for the first camera frame.")
            time.sleep(0.05)
        return self.latest()[0]

    def close(self):
        self._stop.set()
        self._thread.join(timeout=3)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def _read_forever(self):
        capture = cv2.VideoCapture(self._settings["camera"], cv2.CAP_MSMF)
        try:
            if not capture.isOpened():
                raise CameraError("Cannot open the camera. Close any other app using it.")

            capture.set(cv2.CAP_PROP_FRAME_WIDTH, self._settings["width"])
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self._settings["height"])

            # The stream has to be running before exposure settings take effect.
            capture.read()
            capture.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0)
            capture.set(cv2.CAP_PROP_EXPOSURE, self._settings["exposure"])
            capture.set(cv2.CAP_PROP_GAIN, self._settings["gain"])

            # Throw away the frames captured while those settings were taking hold.
            for _ in range(5):
                capture.read()

            while not self._stop.is_set():
                ok, frame = capture.read()
                if not ok or frame is None:
                    raise CameraError("The camera stopped returning frames.")
                with self._lock:
                    self._frame = frame
                    self._taken_at = time.monotonic()
        except Exception as error:
            self.error = str(error)
        finally:
            capture.release()
