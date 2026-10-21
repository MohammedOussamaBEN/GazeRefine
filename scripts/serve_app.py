"""Loopback-only CPU backend + browser UI. python scripts/serve_app.py"""
from __future__ import annotations
import argparse
import base64
import csv
import io
import json
import secrets
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gazerefine.interactive import AppConfig, CPUInference, load_image, samples_to_fixations


def data_url(image):
    buf = io.BytesIO(); image.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


class AppServer(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, address):
        self.token = secrets.token_urlsafe(32)
        self.engine = CPUInference()
        self.inference_lock = threading.Lock()
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass  # Do not log uploaded images or gaze data.

    def local_request(self):
        expected = f"127.0.0.1:{self.server.server_port}"
        if self.headers.get("Host") != expected:
            return False
        origin = self.headers.get("Origin")
        return origin is None or origin == f"http://{expected}"

    def reply(self, code, body, content_type="application/json"):
        if not isinstance(body, bytes):
            body = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers(); self.wfile.write(body)

    def do_GET(self):
        if not self.local_request():
            return self.reply(403, {"error":"Use the localhost URL printed by the launcher."})
        path = urlsplit(self.path).path
        if path == "/api/config":
            return self.reply(200, {"token":self.server.token, "device":"cpu"})
        allowed = {"/":"index.html", "/app.js":"app.js", "/style.css":"style.css", "/gaze.js":"gaze.js"}
        if path not in allowed:
            return self.reply(404, {"error":"Not found"})
        file = ROOT/"webapp"/allowed[path]
        types = {".html":"text/html; charset=utf-8", ".js":"text/javascript; charset=utf-8", ".css":"text/css; charset=utf-8"}
        self.reply(200, file.read_bytes(), types[file.suffix])

    def do_POST(self):
        if not self.local_request() or self.headers.get("X-GazeRefine-Token") != self.server.token:
            return self.reply(403, {"error":"Invalid local app session."})
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            return self.reply(415, {"error":"JSON required."})
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 32*1024*1024:
                return self.reply(413, {"error":"Request limit is 32 MB."})
            data = json.loads(self.rfile.read(size))
            path = urlsplit(self.path).path
            if path == "/api/fixations":
                if len(data["samples"]) > 100_000:
                    raise ValueError("Record a shorter gaze session.")
                return self.reply(200, {"fixations":samples_to_fixations(data["samples"])})
            if path != "/api/predict":
                return self.reply(404, {"error":"Not found"})
            if not self.server.inference_lock.acquire(blocking=False):
                return self.reply(409, {"error":"An inference is already running."})
            try:
                if not isinstance(data["image"], str) or not data["image"].startswith("data:image/"):
                    raise ValueError("Upload an image first.")
                payload = base64.b64decode(data["image"].split(",",1)[1], validate=True)
                image = load_image(io.BytesIO(payload))
                config = AppConfig(modality=data.get("modality","colonoscopy"),
                                   resolution=int(data.get("resolution",384)),
                                   threshold=float(data.get("threshold",.5)),
                                   duration_weighted=bool(data.get("duration_weighted",True)))
                result = self.server.engine.predict(image, data["fixations"], config)
                self.reply(200, {**{k:data_url(result[k]) for k in ("mask","overlay","prior")},
                                 "metadata":result["metadata"]})
            finally:
                self.server.inference_lock.release()
        except (KeyError, ValueError, TypeError, OSError) as exc:
            self.reply(400, {"error":str(exc)})
        except Exception as exc:
            self.reply(500, {"error":f"Inference failed: {type(exc).__name__}: {exc}"})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    server = AppServer(("127.0.0.1", args.port))
    url = f"http://127.0.0.1:{server.server_port}"
    print(f"GazeRefine CPU app: {url}\nCtrl+C to stop. Model loads on first prediction.", flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
