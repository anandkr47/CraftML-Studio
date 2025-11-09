import uvicorn
import sys
from pathlib import Path

# Ensure project root is on sys.path so 'apps.backend.main' can be imported
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from apps.backend.main import app  # noqa: E402


if __name__ == "__main__":
    # Keep localhost/5000 for the desktop app integration
    uvicorn.run(app, host="127.0.0.1", port=5000, log_level="info")


