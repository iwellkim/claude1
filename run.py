"""로컬 개발 서버 진입점.

    python run.py   → http://localhost:5000
"""
from __future__ import annotations

import os

from app.server import app


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=bool(os.environ.get("DEBUG")))
