"""laya-needle: local server. The Chrome extension talks to this and nothing else.

    python server.py            # http://127.0.0.1:8787

Loads Laya once, then answers POST /api/search. Binds to loopback only, so it is
not reachable from your network. No API key, no account, no outbound requests
once the weights are cached.
"""
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from search import THRESHOLD as search_threshold_value, SearchError, search  # noqa: E402

HOST = "127.0.0.1"
PORT = int(os.environ.get("PORT", "8787"))
# multilingual is both the fastest checkpoint and the best at separating a hit
# from a near miss on this task. See "Why multilingual" in the README.
MODEL = os.environ.get("LAYA_NEEDLE_MODEL", "multilingual")
SUBFOLDER = {"english": None, "multilingual": "multilingual", "typed-decisions": "typed-decisions"}
MAX_BODY = 512_000
# Raise toward 0.8 for fewer, surer matches; lower for more, noisier ones.
THRESHOLD = float(os.environ.get("LAYA_NEEDLE_THRESHOLD", search_threshold_value))

AGENT = None
LOCK = threading.Lock()  # one model on one accelerator: serialise inference


def describe(device):
    """torch names the accelerator; the terminal should name it for a person."""
    name = str(device)
    if name.startswith("mps"):
        return "your Mac's GPU (mps)"
    if name.startswith("cuda"):
        return f"your graphics card ({name})"
    if name.startswith("cpu"):
        return "the CPU, which is slower than a GPU"
    return name


def load():
    global AGENT
    if MODEL not in SUBFOLDER:
        sys.exit(f"LAYA_NEEDLE_MODEL must be one of {', '.join(SUBFOLDER)}, not {MODEL!r}")
    import laya
    print(f"loading laya ({MODEL}); the first run downloads weights and takes a few minutes", flush=True)
    started = time.perf_counter()
    AGENT = laya.load("convaiinnovations/laya", subfolder=SUBFOLDER[MODEL])
    print(f"ready in {time.perf_counter() - started:.1f}s, running on {describe(AGENT.device)}", flush=True)


def predict(state, questions):
    with LOCK:
        return AGENT.predict(state, questions)["answers"]


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass  # the page text is the user's; keep it out of the terminal

    def _send(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.end_headers()

    def do_GET(self):
        if self.path.split("?")[0] != "/api/health":
            return self._send(404, {"error": "Not found."})
        self._send(200, {"ok": AGENT is not None, "model": MODEL,
                         "device": str(AGENT.device) if AGENT else None,
                         "threshold": THRESHOLD})

    def do_POST(self):
        if self.path.split("?")[0] != "/api/search":
            return self._send(404, {"error": "Not found."})
        if AGENT is None:
            return self._send(503, {"error": "Laya is still loading. Try again in a moment."})

        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > MAX_BODY:
            return self._send(413, {"error": "That page is too large to search."})
        try:
            body = json.loads(self.rfile.read(length))
        except (ValueError, UnicodeDecodeError):
            return self._send(400, {"error": "Could not read that request."})

        started = time.perf_counter()
        try:
            result = search(body, predict, THRESHOLD)
        except SearchError as e:
            return self._send(e.status, {"error": e.message})
        except Exception:
            import traceback; traceback.print_exc()
            return self._send(500, {"error": "Laya could not complete this search."})
        result["elapsedMs"] = round((time.perf_counter() - started) * 1000)
        result["model"] = MODEL
        self._send(200, result)


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == "__main__":
    try:
        server = Server((HOST, PORT), Handler)
    except OSError as e:
        sys.exit(f"Port {PORT} is already in use ({e.strerror}). Stop the other "
                 f"laya-needle, or start this one with PORT=8788 python server.py")
    threading.Thread(target=load, daemon=True).start()
    print(f"laya-needle listening on http://{HOST}:{PORT} (threshold {THRESHOLD})", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
