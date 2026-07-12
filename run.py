"""
Entry point for Rumor.

Run this on the host computer:

    python run.py

Everyone else connects by opening a browser on the SAME WiFi network
and going to the address this prints, or by scanning the QR code shown
at http://<this-machine's-address>:8000/display
"""
import uvicorn
from app.server import app
from app.net import get_local_ip

PORT = 8000

if __name__ == "__main__":
    ip = get_local_ip()
    print("=" * 52)
    print("  RUMOR is starting up")
    print("=" * 52)
    print(f"  On THIS computer, open:   http://localhost:{PORT}/display")
    print(f"  Everyone ELSE, open:      http://{ip}:{PORT}")
    print("  (Put the /display page on a big screen so people can")
    print("   scan the QR code or read the address off it.)")
    print("=" * 52)
    uvicorn.run("app.server:app", host="0.0.0.0", port=PORT, reload=False)
