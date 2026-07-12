import socket


def get_local_ip() -> str:
    """Best-effort guess at this machine's LAN IP (the one phones on the
    same WiFi can actually reach). Falls back to localhost if offline."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Doesn't actually send anything -- just forces the OS to pick
        # the network interface that would be used to reach the internet.
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except OSError:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip
