
import sys
from pathlib import Path
gpu_root = Path(__file__).resolve().parents[4]
# under gpu_root is a src folder
sim_root = gpu_root / "simulator" 
sys.path.append(str(src_root))
print(src_root)