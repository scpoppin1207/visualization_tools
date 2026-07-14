import sys
from pathlib import Path


def get_repo_root() -> Path:
    """Return repository root directory."""
    return Path(__file__).resolve().parent.parent


def ensure_repo_on_path() -> Path:
    """Add repository root to sys.path if not already present."""
    root = get_repo_root()
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    return root


def config_path(*parts: str) -> Path:
    """Build path under config/ directory."""
    return get_repo_root() / "config" / Path(*parts)


def parse_bool(value: str) -> bool:
    """Parse common truthy/falsey CLI string values."""
    return value.lower() in ("true", "1", "yes", "y")
