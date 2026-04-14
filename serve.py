#!/usr/bin/env python3
"""
Serve the static site from public/ so city and area routes work.
Run from project root: python serve.py
Then open http://127.0.0.1:8080/ — /manhattan/, /brooklyn/, etc. will load correctly.
(Uses port 8080 to avoid conflict with Live Server on 5500.)
"""
import http.server
import socketserver
import os
import sys

PUBLIC_DIR = os.path.join(os.path.dirname(__file__), "public")
os.chdir(PUBLIC_DIR)

PORT = int(os.environ.get("PORT", 8080))

class MyHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # Add CORS headers for development
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

if __name__ == "__main__":
    if not os.path.isfile(os.path.join(PUBLIC_DIR, "index.html")):
        print("No public/index.html found. Run: python generate.py")
        sys.exit(1)
    try:
        with socketserver.TCPServer(("", PORT), MyHTTPRequestHandler) as httpd:
            print(f"Serving at http://127.0.0.1:{PORT}/ (root = public/)")
            print(f"City pages: http://127.0.0.1:{PORT}/manhattan/ etc.")
            print("Press Ctrl+C to stop.")
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        sys.exit(0)
    except OSError as e:
        if e.errno == 98:  # Address already in use
            print(f"Port {PORT} is already in use. Please stop the other server or change the PORT in this script.")
        else:
            print(f"Error: {e}")
        sys.exit(1)

