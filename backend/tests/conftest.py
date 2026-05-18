import sys
import os
import sqlite3
import warnings

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Suppress FastAPI/Starlette asyncio.iscoroutinefunction deprecation warning.
# Fires at import time before main.py filter applies, so must be set here.
warnings.filterwarnings(
    "ignore",
    message=".*asyncio\\.iscoroutinefunction.*",
    category=DeprecationWarning,
)

# Clear rate-limit state before each test session so repeated runs don't 429.
_DB = os.path.join(os.path.dirname(__file__), "..", "..", "data", "awaaz_relay.db")
try:
    if os.path.exists(_DB):
        with sqlite3.connect(_DB) as _conn:
            _conn.execute("DELETE FROM rate_limits")
            _conn.commit()
except Exception:
    pass
