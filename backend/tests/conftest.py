"""Global test fixtures."""

import sys
from pathlib import Path

# Add backend root to Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
