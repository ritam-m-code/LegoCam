"""Read frames in a worker thread so the live controls stay responsive."""

import threading
import time

import cv2


class Camera:
    def __init__(self, config):
        self.config = config
        self.latest = None
        self.error = None
        self.stop = threading.Event()
        self.lock = threading.Lock()
        self.applied = {}
        self.readback = {}
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def run(self):
        cap = cv2.VideoCapture(self.config["camera"], cv2.CAP_MSMF)
        try:
            if not cap.isOpened():
                raise ValueError("Camera unavailable. Close other camera apps and retry.")
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config["width"])
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config["height"])
            cap.read()
            self.applied = {
                "auto_exposure": bool(cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0)),
                "exposure": bool(cap.set(cv2.CAP_PROP_EXPOSURE, self.config["exposure"])),
                "gain": bool(cap.set(cv2.CAP_PROP_GAIN, self.config["gain"])),
            }
            for _ in range(5):
                cap.read()
            sequence = 0
            while not self.stop.is_set():
                ok, frame = cap.read()
                if not ok or frame is None:
                    raise ValueError("Camera frame read failed")
                if [frame.shape[1], frame.shape[0]] != [
                    self.config["width"],
                    self.config["height"],
                ]:
                    raise ValueError("Camera resolution differs from session setup")
                self.readback = {
                    "exposure": cap.get(cv2.CAP_PROP_EXPOSURE),
                    "gain": cap.get(cv2.CAP_PROP_GAIN),
                    "auto_exposure": cap.get(cv2.CAP_PROP_AUTO_EXPOSURE),
                }
                sequence += 1
                with self.lock:
                    self.latest = sequence, time.monotonic(), frame
        except Exception as error:
            self.error = str(error)
        finally:
            cap.release()

    def snapshot(self):
        with self.lock:
            return self.latest
