"""pytest conftest: add repo root to sys.path so harness/oracle imports work."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
