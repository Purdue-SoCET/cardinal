import json
from dataclasses import dataclass, field, fields
from typing import List, Optional, Dict, Any

class SchemaValidationError(Exception):
    """Custom exception for clear, traceable JSON validation errors."""
    pass

def _check_strict_keys(data: Dict[str, Any], cls: Any, context: str):
    """Throws an error if the JSON dictionary contains keys not defined in the Dataclass."""
    allowed_keys = {f.name for f in fields(cls)}
    actual_keys = set(data.keys())
    
    extra_keys = actual_keys - allowed_keys
    if extra_keys:
        raise SchemaValidationError(f"[{context}] Unrecognized parameters found: {', '.join(extra_keys)}.")

# ==========================================
# Execution & Verification Models
# ==========================================
@dataclass
class ExecutionConfig:
    threads: int = 32
    blocks: int = 1
    consumes: List[str] = field(default_factory=list)
    produces_mem: Optional[str] = None
    
    # Active Emulator Features
    start_pc: Optional[str] = None
    arg_pointer: Optional[str] = None
    track_regfile: bool = False
    print_zero: bool = False

    @classmethod
    def from_dict(cls, data: Dict[str, Any], context: str) -> 'ExecutionConfig':
        if not data:
            return cls()
        
        _check_strict_keys(data, cls, context)
        
        # Validation
        if not isinstance(data.get("threads", 32), int) or data.get("threads", 32) <= 0:
            raise SchemaValidationError(f"[{context}] 'threads' must be a positive integer.")
        if not isinstance(data.get("blocks", 1), int) or data.get("blocks", 1) <= 0:
            raise SchemaValidationError(f"[{context}] 'blocks' must be a positive integer.")
        if not isinstance(data.get("consumes", []), list):
            raise SchemaValidationError(f"[{context}] 'consumes' must be a list of strings.")

        return cls(
            threads=data.get("threads", 32),
            blocks=data.get("blocks", 1),
            consumes=data.get("consumes", []),
            produces_mem=data.get("produces_mem"),
            start_pc=data.get("start_pc"),
            arg_pointer=data.get("arg_pointer"),
            track_regfile=bool(data.get("track_regfile", False)),
            print_zero=bool(data.get("print_zero", False))
        )

@dataclass
class VerificationConfig:
    expected_file: str
    check_start: Optional[str] = None
    check_end: Optional[str] = None
    float_tolerance: Optional[float] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any], context: str) -> Optional['VerificationConfig']:
        if not data:
            return None
            
        _check_strict_keys(data, cls, context)
        
        if "expected_file" not in data:
            raise SchemaValidationError(f"[{context}] Missing required field: 'expected_file'.")

        float_tol = data.get("float_tolerance")
        if float_tol is not None and not isinstance(float_tol, (int, float)):
            raise SchemaValidationError(f"[{context}] 'float_tolerance' must be a number.")

        return cls(
            expected_file=data["expected_file"],
            check_start=data.get("check_start"),
            check_end=data.get("check_end"),
            float_tolerance=float(float_tol) if float_tol is not None else None
        )

# ==========================================
# Pipeline Models
# ==========================================
@dataclass
class PipelineStage:
    type: str  # "script", "c_source", "asm_source"
    name: Optional[str] = None
    source: Optional[str] = None
    command: Optional[str] = None
    compiler_flags: Optional[str] = None
    execution: Optional[ExecutionConfig] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any], context: str) -> 'PipelineStage':
        if "type" not in data:
            raise SchemaValidationError(f"[{context}] Missing required field: 'type'.")
            
        _check_strict_keys(data, cls, context)
            
        stage_type = data["type"]
        valid_types = ["script", "c_source", "asm_source"]
        if stage_type not in valid_types:
            raise SchemaValidationError(f"[{context}] Invalid 'type' '{stage_type}'. Must be one of {valid_types}.")

        # Script-specific validation
        if stage_type == "script" and "command" not in data:
            raise SchemaValidationError(f"[{context}] Stage type 'script' requires a 'command' field.")

        exec_data = data.get("execution")
        
        return cls(
            type=stage_type,
            name=data.get("name", f"Unnamed {stage_type} stage"),
            source=data.get("source"),
            command=data.get("command"),
            compiler_flags=data.get("compiler_flags"),
            execution=ExecutionConfig.from_dict(exec_data, f"{context} -> Execution") if exec_data else None
        )

# ==========================================
# High-Level Suite Models
# ==========================================
@dataclass
class StageDefaults:
    source: Optional[str] = None
    compiler_flags: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any], context: str) -> Optional['StageDefaults']:
        if not data:
            return None
            
        _check_strict_keys(data, cls, context)
        
        return cls(
            source=data.get("source"),
            compiler_flags=data.get("compiler_flags")
        )

@dataclass
class SharedConfig:
    c_source: Optional[StageDefaults] = None
    asm_source: Optional[StageDefaults] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any], context: str) -> Optional['SharedConfig']:
        if not data:
            return None
            
        _check_strict_keys(data, cls, context)
        
        return cls(
            c_source=StageDefaults.from_dict(data.get("c_source", {}), f"{context} -> c_source"),
            asm_source=StageDefaults.from_dict(data.get("asm_source", {}), f"{context} -> asm_source")
        )

@dataclass
class TestCase:
    name: str
    pipeline: List[PipelineStage]
    verification: Optional[VerificationConfig] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any], context: str) -> 'TestCase':
        test_name = data.get("name", "Unnamed Test")
        test_context = f"{context} -> Test '{test_name}'"
        
        _check_strict_keys(data, cls, test_context)
        
        if "pipeline" not in data or not isinstance(data["pipeline"], list) or len(data["pipeline"]) == 0:
            raise SchemaValidationError(f"[{test_context}] Missing or empty 'pipeline' array. A test must have at least one stage.")

        stages = []
        for i, stage_data in enumerate(data["pipeline"]):
            stages.append(PipelineStage.from_dict(stage_data, f"{test_context} -> Stage {i}"))

        return cls(
            name=test_name,
            pipeline=stages,
            verification=VerificationConfig.from_dict(data.get("verification", {}), f"{test_context} -> Verification")
        )

@dataclass
class TestSuite:
    suite_name: str
    tests: List[TestCase]
    shared_config: Optional[SharedConfig] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TestSuite':
        if not isinstance(data, dict):
            raise SchemaValidationError("Root of JSON must be a dictionary.")
            
        suite_name = data.get("suite_name", "Unnamed Suite")
        suite_context = f"Suite '{suite_name}'"

        _check_strict_keys(data, cls, suite_context)

        if "tests" not in data or not isinstance(data["tests"], list):
            raise SchemaValidationError(f"[{suite_context}] Missing 'tests' array.")

        return cls(
            suite_name=suite_name,
            shared_config=SharedConfig.from_dict(data.get("shared_config", {}), f"{suite_context} -> SharedConfig"),
            tests=[TestCase.from_dict(test, suite_context) for test in data["tests"]]
        )

    def apply_shared_config(self):
        if not self.shared_config:
            return

        for test in self.tests:
            for stage in test.pipeline:
                defaults = None
                if stage.type == "c_source":
                    defaults = self.shared_config.c_source
                elif stage.type == "asm_source":
                    defaults = self.shared_config.asm_source

                if defaults:
                    if not stage.source and defaults.source:
                        stage.source = defaults.source
                    if not stage.compiler_flags and defaults.compiler_flags:
                        stage.compiler_flags = defaults.compiler_flags

# ==========================================
# Local Testing
# ==========================================
if __name__ == "__main__":
    # Deliberately broken JSON with an extra key to test strict validation
    mock_json_bad = """
    {
      "suite_nam": "Typo in Suite Name Key",
      "tests": [
        {
          "name": "Valid Test",
          "pipeline": [ 
              { 
                  "type": "c_source"
              }
          ]
        }
      ]
    }
    """

    print("Testing Validation Engine...\n")
    try:
        raw_dict = json.loads(mock_json_bad)
        suite = TestSuite.from_dict(raw_dict)
    except SchemaValidationError as e:
        print(f"Successfully caught error:\n{e}")