#!/usr/bin/env python3
"""Tiny stdlib web server that serves ONLY the viewer/ folder.

Run: python3 server.py
Then open http://127.0.0.1:4700 in Chrome.
"""
import http.server
import os
import socketserver

PORT = 4700
VIEWER_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "viewer")


class ViewerHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=VIEWER_DIR, **kwargs)


def main():
    if not os.path.isdir(VIEWER_DIR):
        raise SystemExit(f"viewer/ folder not found at {VIEWER_DIR} — run build.py first.")

    with socketserver.TCPServer(("127.0.0.1", PORT), ViewerHandler) as httpd:
        print(f"Serving {VIEWER_DIR} at http://127.0.0.1:{PORT}")
        print("Press Ctrl+C to stop.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")


if __name__ == "__main__":
    main()
