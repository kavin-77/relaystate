"""
Keep-alive ping script for Render free tier.
Pings the /healthz endpoint every 10 minutes to prevent instance spindown.
Usage: python scripts/keepalive.py https://relaystate.onrender.com
"""

import sys
import time
import urllib.request
from datetime import datetime

def ping_loop(target_url: str, interval_seconds: int = 600):
    if not target_url.endswith("/healthz"):
        target_url = target_url.rstrip("/") + "/healthz"
        
    print(f"[{datetime.now().isoformat()}] Starting keep-alive ping targeting: {target_url}")
    print(f"Interval: every {interval_seconds} seconds ({interval_seconds // 60} minutes)")
    
    while True:
        try:
            req = urllib.request.Request(
                target_url,
                headers={"User-Agent": "RelayState-KeepAlive/1.0"}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Ping OK (HTTP {resp.status})")
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Ping failed or cold starting: {e}")
            
        time.sleep(interval_seconds)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/keepalive.py <RENDER_URL>")
        sys.exit(1)
    ping_loop(sys.argv[1])
