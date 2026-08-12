#!/usr/bin/env python3
"""Serve a built Vite/React app with client-side route fallback."""

from __future__ import annotations

import argparse
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


class SpaRequestHandler(SimpleHTTPRequestHandler):
    def send_head(self):  # noqa: N802 - stdlib override name
        url_path = urlsplit(self.path).path
        translated = Path(self.translate_path(url_path))

        if not translated.exists() and "." not in Path(url_path).name:
            self.path = "/index.html"

        return super().send_head()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bind", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--directory", default=".")
    args = parser.parse_args()

    os.chdir(args.directory)
    server = ThreadingHTTPServer((args.bind, args.port), SpaRequestHandler)
    print(f"Serving {Path.cwd()} at http://{args.bind}:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
