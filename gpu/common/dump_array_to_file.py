from __future__ import annotations

from pathlib import Path
from datetime import datetime
from typing import Iterable, Any


def dump_array_to_timestamped_file(
    out_dir: str | Path,
    arr: Iterable[Any],
    prefix: str = "dump",
    ext: str = "txt",
    sep: str = "\n",
    include_index: bool = True,
) -> Path:
    """
    Creates out_dir if needed, writes arr to a timestamped file, returns the Path.
    Filename format: {prefix}_YYYY-MM-DD_HH-MM-SS.{ext}
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"{prefix}_{ts}.{ext.lstrip('.')}"
    out_path = out_dir / filename

    with out_path.open("w", encoding="utf-8") as f:
        for i, x in enumerate(arr):
            line = f"{i}: {x}" if include_index else str(x)
            f.write(line + sep)

    return out_path


# # ---- example ----
# if __name__ == "__main__":
#     data = [10, 20, 30, 40]
#     p = dump_array_to_timestamped_file("./dumps", data, prefix="memdump")
#     print("Wrote:", p)
