"""Project path constants."""
import sys
from pathlib import Path

# frozen exe: treat the exe's directory as the project root, so libraries /
# config / models sit next to the exe and the whole folder stays portable
PROJECT_ROOT = (Path(sys.executable).resolve().parent
                if getattr(sys, "frozen", False)
                else Path(__file__).resolve().parents[2])
LIBRARIES_DIR = PROJECT_ROOT / "libraries"
CONFIG_DIR = PROJECT_ROOT / "config"
WORKSPACE_DIR = PROJECT_ROOT / "workspace"
EXPORTS_DIR = PROJECT_ROOT / "exports"

DEFAULT_LIBRARY = "默认知识库"


def list_libraries() -> list[Path]:
    """All knowledge bases (dirs under libraries/ containing kb.yaml)."""
    if not LIBRARIES_DIR.exists():
        return []
    return sorted([d for d in LIBRARIES_DIR.iterdir()
                   if d.is_dir() and (d / "kb.yaml").exists()], key=lambda p: p.name)
