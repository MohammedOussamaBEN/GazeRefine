"""Optional SDKs are imported only when their tracker is explicitly started."""
import threading
import time
import math


class EyeTraxTracker:
    """Calibrated webcam gaze -> screen pixel x,y,timestamp_ms callbacks."""
    def __init__(self, callback, error, camera=0):
        self.callback, self.error, self.camera = callback, error, camera
        self.stop_event = threading.Event()

    def start(self):
        def run():
            cap = None
            try:
                import cv2
                from eyetrax import GazeEstimator, run_9_point_calibration
                estimator = GazeEstimator()
                run_9_point_calibration(estimator, camera_index=self.camera)
                if self.stop_event.is_set():
                    return
                cap = cv2.VideoCapture(self.camera)
                if not cap.isOpened():
                    raise RuntimeError("Could not open webcam.")
                while not self.stop_event.is_set():
                    ok, frame = cap.read()
                    if not ok:
                        raise RuntimeError("Webcam stopped delivering frames.")
                    features, blink = estimator.extract_features(frame)
                    now = time.monotonic()*1000
                    if features is not None and not blink:
                        x,y = estimator.predict([features])[0]
                        if math.isfinite(x) and math.isfinite(y):
                            self.callback(float(x),float(y),now)
                    self.stop_event.wait(.015)
            except Exception as exc:
                self.error(str(exc))
            finally:
                if cap is not None:
                    cap.release()
        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()


class TobiiTracker:
    """Tobii Pro normalized display gaze. Calibrate in Eye Tracker Manager first."""
    def __init__(self, callback, error, screen_width, screen_height):
        self.callback, self.error = callback, error
        self.width, self.height = screen_width, screen_height
        self.device = None

    def start(self):
        import tobii_research as tr
        self.tr = tr
        devices = tr.find_all_eyetrackers()
        if not devices:
            raise RuntimeError("No Tobii Pro eye tracker found.")
        self.device = devices[0]
        self.device.subscribe_to(tr.EYETRACKER_GAZE_DATA, self._sample, as_dictionary=True)

    def _sample(self, data):
        eyes = []
        for side in ("left", "right"):
            if data.get(f"{side}_gaze_point_validity"):
                xy = data[f"{side}_gaze_point_on_display_area"]
                if all(math.isfinite(v) for v in xy):
                    eyes.append(xy)
        if eyes:
            x = sum(p[0] for p in eyes)/len(eyes)
            y = sum(p[1] for p in eyes)/len(eyes)
            self.callback(x*self.width, y*self.height, time.monotonic()*1000)

    def stop(self):
        if self.device:
            self.device.unsubscribe_from(self.tr.EYETRACKER_GAZE_DATA, self._sample)
