"""Shared test setup: make the modules in web/ importable like on Toolforge."""
import sys
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parents[1]
WEB_DIR = REPO_DIR / 'web'

if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))
