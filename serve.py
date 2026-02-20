#!/usr/bin/env python3
"""
HTTPS local server for portfolio.
Uses mkcert if available (no browser warning), falls back to self-signed openssl cert.

Usage:  python3 serve.py
Then open: https://localhost:8443
"""
import http.server
import ssl
import os
import subprocess
import sys
from pathlib import Path

PORT = 8443
CERT = "cert.pem"
KEY  = "key.pem"


def check_mkcert():
    try:
        subprocess.run(["mkcert", "--version"], capture_output=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def generate_certs_mkcert():
    print("[serve] Using mkcert — browser will trust this cert automatically.")
    subprocess.run(["mkcert", "-install"], check=True, capture_output=True)
    subprocess.run(["mkcert", "-key-file", KEY, "-cert-file", CERT, "localhost", "127.0.0.1"], check=True)
    print("[serve] Trusted cert generated via mkcert.")


def generate_certs_openssl():
    print("[serve] mkcert not found — generating self-signed cert with openssl.")
    print("[serve] You will need to click 'Advanced → Proceed to localhost' in your browser.")
    subprocess.run([
        "openssl", "req", "-x509", "-newkey", "rsa:2048",
        "-keyout", KEY, "-out", CERT,
        "-days", "365", "-nodes",
        "-subj", "/CN=localhost"
    ], check=True, capture_output=True)
    print("[serve] Self-signed cert generated.")


def main():
    os.chdir(Path(__file__).parent)

    if not (Path(CERT).exists() and Path(KEY).exists()):
        if check_mkcert():
            generate_certs_mkcert()
        else:
            try:
                generate_certs_openssl()
            except (FileNotFoundError, subprocess.CalledProcessError) as e:
                print(f"[serve] ERROR: Could not generate cert: {e}")
                print("[serve] Install mkcert: brew install mkcert")
                sys.exit(1)
    else:
        print("[serve] Using existing cert files.")

    handler = http.server.SimpleHTTPRequestHandler
    handler.extensions_map.update({
        ".js":  "application/javascript",
        ".css": "text/css",
    })

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(CERT, KEY)

    httpd = http.server.HTTPServer(("0.0.0.0", PORT), handler)
    httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)

    print(f"\n  Portfolio running at → https://localhost:{PORT}\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[serve] Stopped.")


if __name__ == "__main__":
    main()
