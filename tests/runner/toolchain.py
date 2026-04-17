import subprocess
import shlex
from pathlib import Path
from typing import List

# ==========================================
# Path Resolution (Anchored to Repo Root)
# ==========================================
# If this file is at: tests/runner/toolchain.py
# REPO_ROOT is two directories up.
TOOLCHAIN_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLCHAIN_DIR.parent.parent

# Tool Paths
TWIG_BIN      = "twig"  # Universal compiler for both C and ASM
ASM_BIN       = "tool"
EMULATOR_BIN  = REPO_ROOT / "gpu" / "emulator" / "src" / "emulator.py"

## Error
class ToolchainError(Exception):
    """Raised when an external toolchain command returns a non-zero exit code."""
    def __init__(self, message: str, cmd: str, stdout: str, stderr: str):
        super().__init__(message)
        self.cmd = cmd
        self.stdout = stdout
        self.stderr = stderr

def _execute(cmd_list: List[str], cwd: Path) -> str:
    """Internal helper to execute a command and capture output."""
    cmd_str = " ".join(str(arg) for arg in cmd_list)
    
    try:
        # capture_output=True grabs both stdout and stderr
        result = subprocess.run(
            cmd_list, 
            cwd=cwd, 
            capture_output=True, 
            text=True, 
            check=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        raise ToolchainError(
            message=f"Command failed with exit code {e.returncode}",
            cmd=cmd_str,
            stdout=e.stdout,
            stderr=e.stderr
        )
    except FileNotFoundError as e:
        raise ToolchainError(
            message=f"Executable not found: {e}",
            cmd=cmd_str,
            stdout="",
            stderr=str(e)
        )

# ==========================================
# Public Interfaces
# ==========================================
def run_script(command: str, cwd: Path) -> str:
    """Runs an arbitrary shell script or python generator."""
    cmd_list = shlex.split(command)
    return _execute(cmd_list, cwd)

def run_assembler(source_file: Path, output_hex: Path, cwd: Path) -> str:
    """Assembles a .s file into a raw hex file using twig."""
    cmd_list = [
        ASM_BIN,
        "--asm", str(source_file),
        "-o", str(output_hex),
        "--hex"
    ]
    return _execute(cmd_list, cwd)

def compile_c(source_file: Path, output_hex: Path, flags: str, cwd: Path) -> str:
    """Compiles a C file to raw hex using twig."""
    # Note: We omit --asm and --hex here, letting twig default to C compilation
    cmd_list = [TWIG_BIN, str(source_file), "--hex-output", str(output_hex)]
    cmd_list_s = [TWIG_BIN, str(source_file), "--output", "assembly.s", "-S"]
    
    if flags:
        cmd_list.extend(shlex.split(flags))
        cmd_list_s.extend(shlex.split(flags))
        
    _execute(cmd_list_s, cwd)
    
    return _execute(cmd_list, cwd)

def run_emulator(
    meminit_file: Path, 
    threads: int, 
    blocks: int, 
    cwd: Path, 
    output_file: Optional[Path] = None, 
    mem_format: str = "hex",
    start_pc: Optional[str] = None,
    arg_pointer: Optional[str] = None,
    track_regfile: bool = False,
    print_zero: bool = False
) -> str:
    """Runs the python emulator using the provided memory initialization file."""
    cmd_list = [
        "python3",
        str(EMULATOR_BIN),
        str(meminit_file),
        "-t", str(threads),
        "-b", str(blocks),
        "--mem-format", mem_format
    ]
    
    if output_file:
        cmd_list.extend(["--output_file", str(output_file)])
    if start_pc:
        cmd_list.extend(["--start-pc", str(start_pc)])
    if arg_pointer:
        cmd_list.extend(["--arg-pointer", str(arg_pointer)])
    if track_regfile:
        cmd_list.append("--track-regfile")
    if print_zero:
        cmd_list.append("--print-zero")
        
    return _execute(cmd_list, cwd)

if __name__ == "__main__":
    # Example usage (for testing purposes)
    print("Repo Root:", REPO_ROOT)
    output = run_script("echo Hello, World!", cwd=REPO_ROOT)
    print("Script Output:", output)

    try:
        output = run_assembler(REPO_ROOT / "tests" / "unit_tests" / "r_type" / "add.s", REPO_ROOT / "example.hex", cwd=REPO_ROOT)
        print("Assembler Output:", output)
    except ToolchainError as e:
        print(f"Error: {e}")
        print(f"Command: {e.cmd}")
        print(f"Stdout: {e.stdout}")
        print(f"Stderr: {e.stderr}")

    try:
        output = compile_c(REPO_ROOT / "benchmark" / "kernels" / "add.c", REPO_ROOT / "add.hex", "-O2 -DGPU_SIM -I " + str(REPO_ROOT / "benchmark/kernels/include"), cwd=REPO_ROOT)
        print("Compiler Output:", output)
    except ToolchainError as e:
        print(f"Error: {e}")
        print(f"Command: {e.cmd}")
        print(f"Stdout: {e.stdout}")
        print(f"Stderr: {e.stderr}")

    try:
        output = run_emulator(REPO_ROOT / "example.hex", 32, 1, cwd=REPO_ROOT)
        print("Emulator Output:", output)
    except ToolchainError as e:
        print(f"Error: {e}")
        print(f"Command: {e.cmd}")
        print(f"Stdout: {e.stdout}")
        print(f"Stderr: {e.stderr}")