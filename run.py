"""
FloodSense dev server.
    python run.py              -> http://127.0.0.1:5000
    FLOODSENSE_PORT=8080 python run.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))  # so CACHE_DIR resolves

from backend.app import app  # noqa: E402

if __name__ == "__main__":
    port = int(os.environ.get("FLOODSENSE_PORT", "5000"))
    debug = os.environ.get("FLOODSENSE_DEBUG", "1") == "1"
    print(f"FloodSense -> http://127.0.0.1:{port}   (Relative Flood Risk Index explorer)")
    app.run(host="127.0.0.1", port=port, debug=debug, use_reloader=False)
