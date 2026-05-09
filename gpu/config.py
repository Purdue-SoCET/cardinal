"""Configuration management for GPU tests and simulator using pydantic-settings."""

from pathlib import Path
from typing import Optional, Any, Tuple, Type, Dict, ClassVar
from enum import Enum
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict, PydanticBaseSettingsSource
import toml


# ============================================================================
# Enum Definitions for Type-Safe Configuration
# ============================================================================

class WritebackBufferCountScheme(str, Enum):
    """Buffer counting scheme options."""
    BUFFER_PER_FSU = "buffer_per_fsu"
    BUFFER_PER_BANK = "buffer_per_bank"

class WritebackBufferSizeScheme(str, Enum):
    """Buffer size scheme options."""
    FIXED = "fixed"
    VARIABLE = "variable"

class WritebackBufferStructure(str, Enum):
    """Buffer structure options."""
    QUEUE = "queue"
    STACK = "stack"
    CIRCULAR = "circular"

class WritebackBufferPolicy(str, Enum):
    """Buffer eviction policy options."""
    CAPACITY_PRIORITY = "capacity_priority"
    AGE_PRIORITY = "age_priority"
    FSU_PRIORITY = "fsu_priority"


# ============================================================================
# Memory-Mapped I/O (MMIO) Configuration for Thread Block Scheduler
# ============================================================================

class MMIOConfig(BaseModel):
    """Memory-mapped I/O configuration for kernel launch parameters.
    
    Used when Thread Block Scheduler (TBS) is enabled. These values are read
    from the meminit file at specific memory addresses instead of config.toml.
    
    MMIO Memory Map:
        0x00: Control Register (Start/Reset GPU)
        0x04: Status Register (Done/Idle/Error)
        0x08: Device ID Register
        0x0C: Kernel Entry Point (start PC)
        0x10: Block Register (threads per block)
        0x14: Grid Register (number of blocks)
        0x18: Total Threads Register (total threads)
        0x1C: Kernel Arguments Address Register
        0x20: Kernel Argument Size Register
    """
    # Default values when TBS is disabled or meminit doesn't provide them
    kernel_entry_point: int = Field(
        default=0x0,
        description="Virtual address of kernel entry point (from MMIO 0x0C)"
    )
    threads_per_block: int = Field(
        default=32,
        description="Threads per block dimension (from MMIO 0x10)"
    )
    num_blocks: int = Field(
        default=1,
        description="Number of blocks/grid dimension (from MMIO 0x14)"
    )
    total_threads: int = Field(
        default=32,
        description="Total threads across all blocks (from MMIO 0x18)"
    )
    kernel_args_address: int = Field(
        default=0x20000000,
        description="Virtual address of kernel arguments (from MMIO 0x1C)"
    )
    kernel_args_size: int = Field(
        default=0,
        description="Size in bytes of kernel arguments (from MMIO 0x20)"
    )


class ProgramConfig(BaseModel):
    """Program-specific configuration for test output filtering.
    
    Defines the address range that contains the actual program results.
    Only values within this range are compared during test validation.
    """
    diff_start_addr: int = Field(
        description="Start address of the output address space (hex format)"
    )
    diff_end_addr: int = Field(
        description="End address of the output address space (hex format)"
    )


class PathsConfig(BaseModel):
    """Path configuration for various scripts and tools."""
    assembler_script: str
    opcodes: str
    emulator: str
    hex_bin_converter: str


class DirectoriesConfig(BaseModel):
    """Directory configuration for test inputs and outputs."""
    diff_dir: str
    test_root_asm: str
    test_root_bin: str
    expected_dir: str


class FilesConfig(BaseModel):
    """Configuration for intermediate and output files."""
    raw_asm_output: str
    formatted_instr: str
    meminit: str
    meminit_bin: str
    emu_output: str
    emu_temp_output: str
    sim_output: str
    final_expected: str
    temp_cmd_log: str


class TestParametersConfig(BaseModel):
    """Test execution parameters."""
    default_start_pc: int
    default_threads: int
    default_blocks: int
    format: str
    default_pattern: str


# ============================================================================
# Simulator Configuration Classes
# ============================================================================

class SMConfig(BaseModel):
    """Streaming Multiprocessor configuration.

    When enable_tbs=False (default):
        - Uses kernel parameters from this config (tb_size, memory.start_pc)
        - Simple single-block kernel execution model

    When enable_tbs=True:
        - Kernel parameters are read from MMIO in the meminit file
        - Parameters configured in [mmio] section are used as fallbacks
        - Enables Thread Block Scheduler for dynamic block scheduling
        - See MMIOConfig for MMIO register mapping
    """
    sm_no: int = 0
    num_warps: int = 1
    num_preds: int = 16
    threads_per_warp: int = 32
    enable_tbs: bool = False
    kernel_pointer_addr: int = 0x0
    tb_size: int = 32
    scheduler_policy: str = Field(
        default="RR",
        description="Warp scheduling policy: RR (round-robin) or GTO (greedy-then-oldest)"
    )


class MemoryConfig(BaseModel):
    """Memory and memory controller configuration."""
    start_pc: int = 0x0
    latency: int = 2
    policy: str = "rr"


class KernelConfig(BaseModel):
    """Kernel configuration."""
    max_kernels_per_sm: int = 1
    kernel_id: int = 0x20000000


class ICacheConfig(BaseModel):
    """Instruction cache configuration."""
    cache_size: int = 32768
    block_size: int = 4
    associativity: int = 1
    hit_latency: int = Field(default=1, description="Cache hit pipeline depth in cycles")


class DCacheConfig(BaseModel):
    """Data cache configuration."""
    cache_size: int = 32768
    block_size: int = 4
    associativity: int = 1
    hit_latency: int = Field(default=2, description="Cache hit pipeline depth in cycles")
    mshr_buffer_len: int = Field(default=16, description="Number of entries in each MSHR buffer")
    num_banks: int = Field(default=2, description="Number of cache banks")
    num_sets_per_bank: int = Field(default=16, description="Number of sets per bank")
    num_ways: int = Field(default=8, description="Number of ways (associativity) per set")
    block_size_words: int = Field(default=32, description="Cache line size in words (32-bit words)")
    word_size_bytes: int = Field(default=4, description="Size of each word in bytes")
    uuid_size: int = Field(default=8, description="UUID bit width (from lockup_free_cache.sv)")


class IntUnitConfigSettings(BaseModel):
    """Integer unit configuration."""
    alu_count: int = Field(default=1, description="Number of integer ALUs")
    mul_count: int = Field(default=1, description="Number of integer multipliers")
    div_count: int = Field(default=1, description="Number of integer dividers")
    alu_latency: int = Field(default=1, description="Integer ALU latency in cycles")
    mul_latency: int = Field(default=2, description="Integer multiply latency in cycles")
    div_latency: int = Field(default=17, description="Integer divide latency in cycles")


class FpUnitConfigSettings(BaseModel):
    """Floating-point unit configuration."""
    alu_count: int = Field(default=1, description="Number of floating-point ALUs")
    mul_count: int = Field(default=1, description="Number of floating-point multipliers")
    div_count: int = Field(default=1, description="Number of floating-point dividers")
    sqrt_count: int = Field(default=0, description="Number of square root units")
    alu_latency: int = Field(default=1, description="FP ALU latency in cycles")
    mul_latency: int = Field(default=4, description="FP multiply latency in cycles")
    div_latency: int = Field(default=24, description="FP divide latency in cycles")
    sqrt_latency: int = Field(default=20, description="FP square root latency in cycles")


class SpecialUnitConfigSettings(BaseModel):
    """Special unit configuration."""
    trig_count: int = Field(default=1, description="Number of trigonometric units")
    inv_sqrt_count: int = Field(default=1, description="Number of inverse square root units")
    conv_count: int = Field(default=1, description="Number of conversion units")
    trig_latency: int = Field(default=16, description="Trigonometric operations latency in cycles")
    inv_sqrt_latency: int = Field(default=12, description="Inverse sqrt latency in cycles")
    conv_latency: int = Field(default=1, description="Conversion operations latency in cycles")


class MemBranchJumpUnitConfigSettings(BaseModel):
    """Memory/Branch/Jump unit configuration."""
    ldst_count: int = Field(default=1, description="Number of load/store units")
    branch_count: int = Field(default=1, description="Number of branch units")
    jump_count: int = Field(default=1, description="Number of jump units")
    ldst_buffer_size: int = Field(default=1, description="Writeback buffer size for LDST units")
    ldst_queue_size: int = Field(default=1, description="Queue size for LDST units")
    block_size_words: int = Field(default=32, description="Cache line size in words (must match [dcache] block_size_words)")
    word_size_bytes: int = Field(default=4, description="Size of each word in bytes (must match [dcache] word_size_bytes)")


class FunctionalUnitsConfig(BaseModel):
    """Functional units configuration."""
    int_unit_count: int = Field(default=1, description="Number of integer execution units")
    fp_unit_count: int = Field(default=1, description="Number of FP execution units")
    special_unit_count: int = Field(default=1, description="Number of special execution units")
    membranchjump_unit_count: int = Field(default=1, description="Number of memory/branch/jump units")
    
    # Nested unit configurations
    int_unit: IntUnitConfigSettings = Field(default_factory=IntUnitConfigSettings)
    fp_unit: FpUnitConfigSettings = Field(default_factory=FpUnitConfigSettings)
    special_unit: SpecialUnitConfigSettings = Field(default_factory=SpecialUnitConfigSettings)
    membranchjump_unit: MemBranchJumpUnitConfigSettings = Field(default_factory=MemBranchJumpUnitConfigSettings)


class WritebackBufferConfig(BaseModel):
    """Writeback buffer configuration."""
    count_scheme: WritebackBufferCountScheme = Field(
        default=WritebackBufferCountScheme.BUFFER_PER_FSU,
        description="Buffer counting scheme: buffer_per_fsu or buffer_per_bank"
    )
    size_scheme: WritebackBufferSizeScheme = Field(
        default=WritebackBufferSizeScheme.FIXED,
        description="Size scheme: fixed (single size for all) or variable (per-FSU sizes)"
    )
    structure: WritebackBufferStructure = Field(
        default=WritebackBufferStructure.QUEUE,
        description="Buffer structure: queue, stack, or circular"
    )
    primary_policy: WritebackBufferPolicy = Field(
        default=WritebackBufferPolicy.CAPACITY_PRIORITY,
        description="Primary eviction policy: capacity_priority, age_priority, or fsu_priority"
    )
    secondary_policy: WritebackBufferPolicy = Field(
        default=WritebackBufferPolicy.AGE_PRIORITY,
        description="Secondary eviction policy: capacity_priority, age_priority, or fsu_priority"
    )
    size: int = Field(
        default=8,
        description="Buffer size (fixed) or default size (variable)"
    )
    variable_sizes: Optional[Dict[str, int]] = Field(
        default=None,
        description="Per-FSU buffer sizes when using variable size scheme"
    )
    fsu_priorities: Optional[Dict[str, int]] = Field(
        default=None,
        description="FSU priority mapping when using fsu_priority policy"
    )


class WritebackConfig(BaseModel):
    """Writeback stage configuration."""
    buffer_config: WritebackBufferConfig = Field(
        default_factory=WritebackBufferConfig,
        description="Writeback buffer configuration"
    )


class RegisterFileConfig(BaseModel):
    """Register file configuration."""
    num_banks: int = Field(
        default=2,
        description="Number of register file banks"
    )


class PredicateRegisterFileConfig(BaseModel):
    """Predicate register file configuration."""
    num_banks: int = Field(
        default=1,
        description="Number of predicate register file banks"
    )


class TestConfig(BaseModel):
    """Test configuration."""
    test_file: str = "test.bin"
    test_file_type: str = "bin"
    tb_size: int = 32


class PerformanceCounterConfig(BaseModel):
    """Performance counter and telemetry configuration."""
    enabled: bool = True
    trace_enabled: bool = False
    trace_start_cycle: int = 0
    trace_end_cycle: int = 0
    output_dir: str = "results/perf_data"
    output_prefix: str = ""  # Prefix for output filenames (e.g., test name)
    summary_only: bool = True
    enabled_units: list[str] = Field(default_factory=list)  # empty = all units
    buffer_limit: int = 100_000
    flight_recorder_enabled: bool = False


# ============================================================================
# TOML Loading
# ============================================================================

class TomlConfigSettingsSource(PydanticBaseSettingsSource):
    """Custom settings source to load configuration from TOML file."""
    
    def __init__(self, settings_cls: Type[BaseSettings], toml_file: Path):
        super().__init__(settings_cls)
        self.toml_file = toml_file
        self.toml_data = self._load_toml()
    
    def _load_toml(self) -> dict:
        """Load TOML file."""
        if not self.toml_file.exists():
            raise FileNotFoundError(f"Config file not found: {self.toml_file}")
        with open(self.toml_file, 'r') as f:
            return toml.load(f)
    
    def get_field_value(self, field_name: str, field_info: Any) -> Tuple[Any, str, bool]:
        """Get field value from TOML data."""
        if field_name in self.toml_data:
            return self.toml_data[field_name], field_name, False
        return None, field_name, False
    
    def __call__(self) -> dict:
        """Return all TOML data."""
        return self.toml_data


# ============================================================================
# Main Settings Classes
# ============================================================================

class Settings(BaseSettings):
    """Combined settings class for test suite and simulator."""
    
    model_config = SettingsConfigDict(
        env_file_encoding='utf-8',
        extra='ignore'
    )
    custom_toml_file: ClassVar[Optional[Path]] = None
    
    # Test suite configuration
    paths: PathsConfig
    directories: DirectoriesConfig
    files: FilesConfig
    test_parameters: TestParametersConfig
    
    # Simulator configuration
    sm: SMConfig
    memory: MemoryConfig
    kernel: KernelConfig
    icache: ICacheConfig
    dcache: DCacheConfig = Field(default_factory=DCacheConfig)
    functional_units: FunctionalUnitsConfig = Field(default_factory=FunctionalUnitsConfig)
    writeback: WritebackConfig = Field(default_factory=WritebackConfig)
    register_file: RegisterFileConfig = Field(default_factory=RegisterFileConfig)
    predicate_register_file: PredicateRegisterFileConfig = Field(default_factory=PredicateRegisterFileConfig)
    mmio: MMIOConfig = Field(default_factory=MMIOConfig)
    test: TestConfig
    perf_counter: PerformanceCounterConfig = Field(default_factory=PerformanceCounterConfig)
    
    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        """Customize settings sources to include TOML."""
        toml_file = Path(__file__).parent / 'config.toml'
        if getattr(settings_cls, 'custom_toml_file', None) is not None:
            toml_file = settings_cls.custom_toml_file
        return (
            init_settings,
            TomlConfigSettingsSource(settings_cls, toml_file),
            env_settings,
        )
    
    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "Settings":
        """Load settings from a TOML file.
        
        Args:
            config_path: Optional path to config file. If None, uses default 'config.toml'
        
        Returns:
            Settings instance
        """
        if config_path is not None:
            class CustomSettings(cls):
                custom_toml_file: ClassVar[Optional[Path]] = Path(config_path)
            return CustomSettings()
        return cls()
    
    def resolve_paths(self) -> None:
        """Resolve relative paths relative to the config file location."""
        config_dir = Path(__file__).parent
        
        # Resolve directory paths
        self.directories.diff_dir = str((config_dir / self.directories.diff_dir).resolve())
        self.directories.test_root_asm = str((config_dir / self.directories.test_root_asm).resolve())
        self.directories.test_root_bin = str((config_dir / self.directories.test_root_bin).resolve())
        self.directories.expected_dir = str((config_dir / self.directories.expected_dir).resolve())
        
        # Resolve file paths
        self.files.raw_asm_output = str((config_dir / self.files.raw_asm_output).resolve())
        self.files.formatted_instr = str((config_dir / self.files.formatted_instr).resolve())
        self.files.meminit = str((config_dir / self.files.meminit).resolve())
        self.files.meminit_bin = str((config_dir / self.files.meminit_bin).resolve())
        self.files.emu_output = str((config_dir / self.files.emu_output).resolve())
        self.files.emu_temp_output = str((config_dir / self.files.emu_temp_output).resolve())
        self.files.sim_output = str((config_dir / self.files.sim_output).resolve())
        self.files.final_expected = str((config_dir / self.files.final_expected).resolve())
        self.files.temp_cmd_log = str((config_dir / self.files.temp_cmd_log).resolve())
        
        # Resolve path scripts
        self.paths.assembler_script = str((config_dir / self.paths.assembler_script).resolve())
        self.paths.opcodes = str((config_dir / self.paths.opcodes).resolve())
        self.paths.emulator = str((config_dir / self.paths.emulator).resolve())
        self.paths.hex_bin_converter = str((config_dir / self.paths.hex_bin_converter).resolve())
    
    def to_icache_dict(self) -> Dict[str, Any]:
        """Convert icache config to dictionary format expected by ICacheStage."""
        return {
            "cache_size": self.icache.cache_size,
            "block_size": self.icache.block_size,
            "associativity": self.icache.associativity,
            "hit_latency": self.icache.hit_latency,
        }

    def to_dcache_dict(self) -> Dict[str, Any]:
        """Convert dcache config to dictionary format expected by LockupFreeCacheStage."""
        return {
            "cache_size": self.dcache.cache_size,
            "block_size": self.dcache.block_size,
            "associativity": self.dcache.associativity,
            "hit_latency": self.dcache.hit_latency,
            "mshr_buffer_len": self.dcache.mshr_buffer_len,
            "num_banks": self.dcache.num_banks,
            "num_sets_per_bank": self.dcache.num_sets_per_bank,
            "num_ways": self.dcache.num_ways,
            "block_size_words": self.dcache.block_size_words,
            "word_size_bytes": self.dcache.word_size_bytes,
            "uuid_size": self.dcache.uuid_size,
        }
    
    def read_mmio_from_meminit(self, meminit_path: Path) -> MMIOConfig:
        """Read MMIO configuration from meminit file.
        
        When TBS is enabled, kernel parameters are stored in memory-mapped I/O
        locations instead of config.toml. This method reads those values from
        the meminit hex file.
        
        MMIO addresses:
            0x0C: Kernel Entry Point
            0x10: Threads Per Block
            0x14: Number of Blocks
            0x18: Total Threads
            0x1C: Kernel Arguments Address
            0x20: Kernel Arguments Size
        
        Args:
            meminit_path: Path to meminit hex file
            
        Returns:
            MMIOConfig populated with values from memory
            
        Raises:
            FileNotFoundError: If meminit file doesn't exist
            ValueError: If hex file is malformed
        """
        if not meminit_path.exists():
            raise FileNotFoundError(f"Meminit file not found: {meminit_path}")
        
        # MMIO address to field mapping
        mmio_map = {
            0x0C: 'kernel_entry_point',
            0x10: 'threads_per_block',
            0x14: 'num_blocks',
            0x18: 'total_threads',
            0x1C: 'kernel_args_address',
            0x20: 'kernel_args_size',
        }
        
        mmio_values = {}
        
        try:
            with open(meminit_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    
                    parts = line.split()
                    if len(parts) < 2:
                        continue
                    
                    try:
                        addr = int(parts[0], 16)
                        value = int(parts[1], 16)
                        
                        # Check if this address is in MMIO range
                        if addr in mmio_map:
                            mmio_values[mmio_map[addr]] = value
                    except (ValueError, IndexError):
                        # Skip malformed lines
                        continue
        except Exception as e:
            raise ValueError(f"Error reading meminit file {meminit_path}: {e}")
        
        # Create MMIOConfig with values from meminit, falling back to defaults
        return MMIOConfig(
            kernel_entry_point=mmio_values.get('kernel_entry_point', self.mmio.kernel_entry_point),
            threads_per_block=mmio_values.get('threads_per_block', self.mmio.threads_per_block),
            num_blocks=mmio_values.get('num_blocks', self.mmio.num_blocks),
            total_threads=mmio_values.get('total_threads', self.mmio.total_threads),
            kernel_args_address=mmio_values.get('kernel_args_address', self.mmio.kernel_args_address),
            kernel_args_size=mmio_values.get('kernel_args_size', self.mmio.kernel_args_size),
        )
    
    def read_program_config(self, program_config_path: Path) -> Optional[ProgramConfig]:
        """Read program-specific configuration from program_config.toml.
        
        This file defines the address space to compare during test validation.
        
        Args:
            program_config_path: Path to program_config.toml file
            
        Returns:
            ProgramConfig instance if file exists, None otherwise
        """
        if not program_config_path.exists():
            return None
        
        try:
            config_data = toml.load(program_config_path)
            
            # The file should have a section with diff_start_addr and diff_end_addr
            # Look for any section that contains these keys
            for section_name, section_data in config_data.items():
                if isinstance(section_data, dict):
                    diff_start_addr = section_data.get('diff_start_addr')
                    diff_end_addr = section_data.get('diff_end_addr')
                    
                    if diff_start_addr is not None and diff_end_addr is not None:
                        # Handle both string (hex) and int formats
                        if isinstance(diff_start_addr, str):
                            diff_start_addr = int(diff_start_addr, 16)
                        if isinstance(diff_end_addr, str):
                            diff_end_addr = int(diff_end_addr, 16)
                        
                        return ProgramConfig(
                            diff_start_addr=diff_start_addr,
                            diff_end_addr=diff_end_addr
                        )
            
            return None
        except Exception as e:
            print(f"Error reading program config {program_config_path}: {e}")
            return None


# ============================================================================
# Singleton Management
# ============================================================================

_settings: Optional[Settings] = None


def get_settings(config_path: Optional[Path] = None) -> Settings:
    """Get or create the settings singleton.
    
    Args:
        config_path: Optional path to config file
        
    Returns:
        Settings instance
    """
    global _settings
    if _settings is None or config_path is not None:
        _settings = Settings.load(config_path)
        _settings.resolve_paths()
    return _settings


def reset_settings():
    """Reset the settings singleton. Useful for testing."""
    global _settings
    _settings = None
