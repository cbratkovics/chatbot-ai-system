"""Serve the real export with its Vercel headers; no application server or proxy."""
import argparse
import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEADERS = json.loads((ROOT / "vercel.json").read_text())["headers"][0]["headers"]


class StaticHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        for header in HEADERS:
            self.send_header(header["key"], header["value"])
        super().end_headers()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=3000)
    args = parser.parse_args()
    if not (ROOT / "out/index.html").is_file():
        raise SystemExit("Missing export. Run npm run build first.")
    ThreadingHTTPServer(
        ("127.0.0.1", args.port), partial(StaticHandler, directory=str(ROOT / "out"))
    ).serve_forever()
