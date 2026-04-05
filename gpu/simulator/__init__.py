from pathlib import Path
import sys

_pkg_dir = Path(__file__).resolve().parent
_src_dir = _pkg_dir / "src"
_src = str(_src_dir)

if _src_dir.is_dir():
    if _src not in sys.path:
        sys.path.insert(0, _src)
    if _src not in __path__:
        __path__.append(_src)