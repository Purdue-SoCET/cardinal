from simulator.execute.functional_sub_unit import FunctionalSubUnit
from simulator.interfaces import LatchIF
from common.custom_enums_multi import Op, R_Op, I_Op, F_Op, C_Op, H_Op, U_Op, B_Op, P_Op, J_Op
from typing import Optional
from simulator.instruction import Instruction
from bitstring import Bits
import math
from simulator.utils.data_structures.compact_queue import CompactQueue
from simulator.utils.performance_counter.execute import ExecutePerfCount as PerfCount
from simulator.utils.performance_counter.telemeter import Telemeter

class ArithmeticSubUnitPipeline(CompactQueue):
    def __init__(self, latency: int):
        super().__init__(length=latency, type_=Instruction)
        
class ArithmeticSubUnit(FunctionalSubUnit):
    SUPPORTED_OPS = {
        int: [],
        float: [],
    }

    def __init__(self, latency: int, num: int, type_: type, telemeter=None):
        if type_ not in [int, float]:
            raise ValueError(f"Unsupported type '{type_}' for FunctionalSubUnit. Must be {int} or {float}.")

        # Set type first since parent __init__ uses self.name which may be overridden by subclasses
        self.type_ = type_
        self.latency = latency
        
        # Call parent init - this sets self.name and creates perf_count
        # For base ArithmeticSubUnit, the name will be "ArithmeticSubUnit_<num>"
        # Subclasses will override self.name in their own __init__ after calling super()
        super().__init__(num=num, telemeter=telemeter)
        
        # Update the name to include the type information
        # This also needs to update the perf_count unit_name if it was already registered
        self.name = f"{self.__class__.__name__}_{type_.__name__}_{num}"
        
        # Update perf_count unit_name to match the new unit name
        # CRITICAL: Must update unit_name, not name (unit_name is what telemeter uses as the dict key)
        self.perf_count.unit_name = self.name
        
        # Re-register with telemeter under the correct name if telemeter exists
        if telemeter and self.name != f"{self.__class__.__name__}_{num}":
            # Remove old registration and add new one
            old_name = f"{self.__class__.__name__}_{num}"
            if old_name in telemeter._units:
                del telemeter._units[old_name]
            telemeter.register_unit(self.perf_count)

        self._overflow_pending = False

        self.ex_wb_interface = LatchIF(name=f"{self.name}_EX_WB_Interface")

        # the way stages are connected in the SM class, we need (latency - 1) latches
        self.pipeline = ArithmeticSubUnitPipeline(latency=max(1, latency-1))

    def single_cycle_latency_compute_tick(self):
        if self.latency != 1 or self.ready_out is False:
            return
        
        self.ex_wb_interface.force_push(self.pipeline.advance(None))

    def tick(self, behind_latch: LatchIF) -> Instruction:
        if isinstance(behind_latch, LatchIF):
            in_data = behind_latch.snoop()
        else:
            in_data = None

        instr = None

        if self.ex_wb_interface.ready_for_push():
            instr = in_data
            if isinstance(instr, Instruction):
                instr.mark_fu_enter(self.name, self.perf_count.total_cycles)

            out_data = self.pipeline.advance(in_data)

            if isinstance(out_data, Instruction):
                out_data.mark_fu_exit(self.name, self.perf_count.total_cycles)

            if isinstance(behind_latch, LatchIF):
                behind_latch.pop()

            self.ready_out = True

        elif self.latency > 1 and not self.pipeline.is_full:
            out_data = False
            instr = in_data
            if isinstance(instr, Instruction):
                instr.mark_fu_enter(self.name, self.perf_count.total_cycles)

            self.pipeline.compact(instr)

            if isinstance(behind_latch, LatchIF):
                behind_latch.pop()
        else:
            out_data = False
            self.ready_out = False            

        self._record_cycle(
            instr=instr,
            ready_out=self.ready_out,
            ex_wb_interface_ready=self.ex_wb_interface.ready_for_push(),
            overflow=self._overflow_pending,
        )
        self._overflow_pending = False
        
        return out_data # return data to the Exectute stage so that all results can be collected and sent to WB stage together
    
    def _record_cycle(
        self,
        *,
        instr: Instruction,
        ex_wb_interface_ready: bool,
        ready_out: bool,
        overflow: bool = False,
        trace_kwargs: dict | None = None,
        trigger_kwargs: dict | None = None,
        record_kwargs: dict | None = None,
    ):
        trace_payload = {"overflow": overflow}
        trigger_payload = {"overflow": overflow}
        record_payload = {"overflow": overflow}

        if trace_kwargs:
            trace_payload.update(trace_kwargs)
        if trigger_kwargs:
            trigger_payload.update(trigger_kwargs)
        if record_kwargs:
            record_payload.update(record_kwargs)

        super()._record_cycle(
            instr=instr,
            ex_wb_interface_ready=ex_wb_interface_ready,
            ready_out=ready_out,
            trace_kwargs=trace_payload,
            trigger_kwargs=trigger_payload,
            record_kwargs=record_payload,
        )

class Alu(ArithmeticSubUnit):
    SUPPORTED_OPS = {
        int: [
            R_Op.ADD, R_Op.SUB, R_Op.AND, R_Op.OR, 
            R_Op.XOR, R_Op.SLT, R_Op.SLTU, R_Op.SLL, 
            R_Op.SRL, R_Op.SRA, R_Op.SGE, R_Op.SGEU, 
            I_Op.SUBI, I_Op.ADDI, I_Op.ORI, I_Op.XORI, 
            I_Op.SLTI, I_Op.SLTIU, I_Op.SLLI, I_Op.SRLI, 
            I_Op.SRAI, C_Op.CSRR, U_Op.LUI, U_Op.AUIPC, U_Op.LLI, U_Op.LMI
        ],
        float: [
            R_Op.ADDF, R_Op.SUBF, R_Op.SLTF, R_Op.SGEF,
        ]
    }
    OUTPUT_TYPE = {
        int: [
             R_Op.ADD, R_Op.SUB, R_Op.AND, R_Op.OR, 
            R_Op.XOR, R_Op.SLT, R_Op.SLTU, R_Op.SLL, 
            R_Op.SRL, R_Op.SRA, R_Op.SGE, R_Op.SGEU, 
            I_Op.SUBI, I_Op.ADDI, I_Op.ORI, I_Op.XORI, 
            I_Op.SLTI, I_Op.SLTIU, I_Op.SLLI, I_Op.SRLI, 
            I_Op.SRAI, C_Op.CSRR, U_Op.LUI, U_Op.AUIPC, 
            U_Op.LLI, U_Op.LMI,

            # the results of these ops are integers, even though their input is float
            R_Op.SLTF, R_Op.SGEF,
        ],
        float: [
            R_Op.ADDF, R_Op.SUBF, 
        ]
    }

    def __init__(self, latency: int, num: int, type_: type, telemeter=None):
        if type_ != int and type_ != float:
            raise ValueError("ALU only supports integer and float operations.")

        super().__init__(latency=latency, num=num, type_=type_, telemeter=telemeter)

    def compute(self):
        # Use current_instr if pipeline is empty (latency=1), else use last queue entry
        instr = self.pipeline.queue[-1]
        if instr is None:
            return

        if not isinstance(instr, Instruction):
            raise TypeError(f"Expected Instruction type in pipeline, got {type(instr)}")
                                                                 
        if instr.opcode not in self.SUPPORTED_OPS[self.type_]:
            raise ValueError(f"ALU does not support operation {instr.opcode} for type {self.type_}")

        overflow_detected = False
        for i in range(32):
            if instr.predicate[i].bin == "0":
                continue

            if isinstance(instr.opcode, C_Op):
                a = instr.csr_value if instr.csr_param != 3 else instr.csr_value.uint
            elif instr.opcode in self.SUPPORTED_OPS[float]:
                a = instr.rdat1[i].float
            elif isinstance(instr.opcode, U_Op):
                a = instr.imm.int
            else:
                a = instr.rdat1[i].int
            
            if isinstance(instr.opcode, I_Op):
                b = instr.imm.int
            elif isinstance(instr.opcode, C_Op):
                b = 0 if instr.csr_param != 0 else i
            elif instr.opcode in self.SUPPORTED_OPS[float]:
                b = instr.rdat2[i].float
            elif isinstance(instr.opcode, U_Op):
                if instr.opcode == U_Op.AUIPC:
                    b = instr.pc.uint
                else:
                    b = instr.rdat1[i].int
            else:
                b = instr.rdat2[i].int

            match instr.opcode:
                # case R_Op.ADD | I_Op.ADDI:
                case R_Op.ADD | I_Op.ADDI | C_Op.CSRR | R_Op.ADDF | U_Op.AUIPC:
                    result = a + b
                    # Check for signed overflow
                    # Overflow occurs when operands have same sign but result has opposite sign
                    if instr.opcode == R_Op.ADD or instr.opcode == I_Op.ADDI:
                        if (a > 0 and b > 0 and result < 0) or (a < 0 and b < 0 and result > 0):
                            overflow_detected = True
                case R_Op.SUB | I_Op.SUBI | R_Op.SUBF:
                    result = a - b
                    # Check for signed overflow
                    # Overflow occurs when: positive - negative = negative, or negative - positive = positive
                    if instr.opcode == R_Op.SUB:
                        if (a > 0 and b < 0 and result < 0) or (a < 0 and b > 0 and result > 0):
                            overflow_detected = True
                case R_Op.AND:
                    result = a & b
                case R_Op.OR | I_Op.ORI:
                    result = a | b
                case R_Op.XOR | I_Op.XORI:
                    result = a ^ b
                case R_Op.SLT | I_Op.SLTI:
                    result = int(a < b)
                case R_Op.SGE:
                    result = not int(a < b)
                case R_Op.SGEU:
                    result = not int((a & 0xFFFFFFFF) < (b & 0xFFFFFFFF))
                case R_Op.SLTU | I_Op.SLTIU:
                    result = int((a & 0xFFFFFFFF) < (b & 0xFFFFFFFF))
                case R_Op.SLL | I_Op.SLLI:
                    result = a << b
                    # Check for shift overflow (shift amount >= 32)
                    if b >= 32 or b < 0:
                        overflow_detected = True
                case R_Op.SRL | I_Op.SRLI:
                    result = (a % 0x100000000) >> b
                    # Check for shift overflow
                    if b >= 32 or b < 0:
                        overflow_detected = True
                case R_Op.SRA | I_Op.SRAI:
                    result = a >> b
                    # Check for shift overflow
                    if b >= 32 or b < 0:
                        overflow_detected = True
                case R_Op.SLTF:
                    if math.isinf(a) or math.isnan(a) or math.isinf(b) or math.isnan(b):
                        overflow_detected = True
                    result = int(a < b)
                case R_Op.SGEF:
                    if math.isinf(a) or math.isnan(a) or math.isinf(b) or math.isnan(b):
                        overflow_detected = True
                    result = int(a >= b)
                # case U_Op.AUIPC:
                #     # result = (b + ((a & 0xFFFFF) << 12)) & 0xFFFFFFFF
                #     result = (a + b) & 0xFFFFFFFF
                case U_Op.LLI:
                    # {old[31:12], imm[11:0]}
                    result = ((b & 0xFFFFF000) | (a & 0xFFF)) & 0xFFFFFFFF
                case U_Op.LMI:
                    # {old[31:24], imm[11:0], old[11:0]}
                    result= ((b & 0xFF000FFF) | ((a & 0xFFF) << 12)) & 0xFFFFFFFF

                case U_Op.LUI:
                    # {imm[7:0], old[23:0]}
                    result= (((a & 0xFF) << 24) | (b & 0x00FFFFFF)) & 0xFFFFFFFF
                case _:
                    raise ValueError(f"Unsupported operation {instr.opcode} in ALU_{self.type_}.")
                
            if instr.opcode in self.OUTPUT_TYPE[int]:
                instr.wdat[i] = Bits(length=32, uint=result & 0xFFFFFFFF)
            elif instr.opcode in self.OUTPUT_TYPE[float]:
                instr.wdat[i] = Bits(length=32, float=result)
            else:
                raise ValueError(f"Opcode {instr.opcode} doesnt have an output type listed in {self.__class__.__name__}.OUTPUT_TYPE.")
        
        if overflow_detected:
            self._overflow_pending = True

        if self.latency == 1:
            self.single_cycle_latency_compute_tick()

class Mul(ArithmeticSubUnit):
    SUPPORTED_OPS = {
        int: [R_Op.MUL],
        float: [R_Op.MULF],
    }

    def __init__(self, latency: int, num: int, type_: type, telemeter=None):
        if type_ not in [int, float]:
            raise ValueError("MUL only supports integer and floating-point operations.")

        super().__init__(latency=latency, type_=type_, num=num, telemeter=telemeter)
    def compute(self):
        # Use current_instr if pipeline is empty (latency=1), else use last queue entry
        instr = self.pipeline.queue[-1]
        if instr is None:
            return

        if not isinstance(instr, Instruction):
            raise TypeError(f"Expected Instruction type in pipeline, got {type(instr)}")
        
        if instr.opcode not in self.SUPPORTED_OPS[self.type_]:
            raise ValueError(f"MUL does not support operation {instr.opcode} for type {self.type_}")

        overflow_detected = False
        for i in range(32):
            if instr.predicate[i].bin == "0":
                continue

            match instr.opcode:
                case R_Op.MUL:
                    a = instr.rdat1[i].int
                    b = instr.rdat2[i].int
                    result = a * b
                    # Check for signed overflow
                    if result > 2147483647 or result < -2147483648:
                        overflow_detected = True
                    instr.wdat[i] = Bits(length=32, int=result & 0xFFFFFFFF)
                case R_Op.MULF:
                    a = instr.rdat1[i].float
                    b = instr.rdat2[i].float
                    result = a * b
                    # Check for floating-point overflow
                    if math.isinf(result) or math.isnan(result):
                        overflow_detected = True
                    instr.wdat[i] = Bits(length=32, float=result)
                case _:
                    raise ValueError(f"Unsupported operation {instr.opcode} in MUL.")
        
        if overflow_detected:
            self._overflow_pending = True
        
        if self.latency == 1:
            self.single_cycle_latency_compute_tick()

class Div(ArithmeticSubUnit):
    SUPPORTED_OPS = {
        int: [R_Op.DIV],
        float: [R_Op.DIVF],
    }

    def __init__(self, latency: int, num: int, type_: type, telemeter=None):
        if type_ not in [int, float]:
            raise ValueError("DIV only supports integer and floating-point operations.")

        super().__init__(latency=latency, type_=type_, num=num, telemeter=telemeter)
    def compute(self):
        # Use current_instr if pipeline is empty (latency=1), else use last queue entry
        instr = self.pipeline.queue[-1]
        if instr is None:
            return

        if not isinstance(instr, Instruction):
            raise TypeError(f"Expected Instruction type in pipeline, got {type(instr)}")
        
        if instr.opcode not in self.SUPPORTED_OPS[self.type_]:
            raise ValueError(f"DIV does not support operation {instr.opcode} for type {self.type_}")

        overflow_detected = False
        for i in range(32):
            if instr.predicate[i].bin == "0":
                continue
                
            match instr.opcode:
                case R_Op.DIV:
                    a = instr.rdat1[i].int
                    b = instr.rdat2[i].int
                    if b == 0:
                        result = 0
                        overflow_detected = True  # Division by zero
                    else:
                        result = a // b
                        # Check for division overflow (MIN_INT / -1)
                        if a == -2147483648 and b == -1:
                            overflow_detected = True
                    # print(f"[EX: DIV] {a} / {b} = ", result)
                    instr.wdat[i] = Bits(length=32, uint=result & 0xFFFFFFFF)
                case R_Op.DIVF:
                    a = instr.rdat1[i].float
                    b = instr.rdat2[i].float
                    if b == 0.0:
                        result = 0.0
                        overflow_detected = True  # Division by zero
                    else:
                        result = a / b
                        # Check for floating-point overflow
                        if math.isinf(result) or math.isnan(result):
                            overflow_detected = True
                    # print(f"[EX: DIV] {a} / {b} = ", result)
                    instr.wdat[i] = Bits(length=32, float=result)
                case _:
                    raise ValueError(f"Unsupported operation {instr.opcode} in DIV.")
        
        if overflow_detected:
            self.perf_count.increment_overflow(instr.opcode)
        
        if self.latency == 1:
            self.single_cycle_latency_compute_tick()

class Conv(ArithmeticSubUnit):
    SUPPORTED_OPS = {
        float: [F_Op.ITOF, F_Op.FTOI]
    }

    def __init__(self, latency: int, num: int, type_: type = float, telemeter=None):
        
        # converstion unit will be considered float since it requires float hardware for all operations, even if int is involved
        if type_ != float:
            raise ValueError("Conversion unit only supports floating-point operations.")

        super().__init__(latency=latency, num=num, type_=type_, telemeter=telemeter)

    def compute(self):
        # Use current_instr if pipeline is empty (latency=1), else use last queue entry
        instr = self.pipeline.queue[-1]
        if instr is None:
            return

        if not isinstance(instr, Instruction):
            raise TypeError(f"Expected Instruction type in pipeline, got {type(instr)}")
        
        if instr.opcode not in self.SUPPORTED_OPS[self.type_]:
            raise ValueError(f"Conversion does not support operation {instr.opcode}")

        overflow_detected = False
        for i in range(32):
            if instr.predicate[i].bin == "0":
                continue

            match instr.opcode:
                case F_Op.ITOF:
                    a = instr.rdat1[i].int
                    result = float(a)
                    # Check for overflow (exceeding max float or min float)
                    if result > 3.4028235e+38 or result < -3.4028235e+38:
                        overflow_detected = True
                    instr.wdat[i] = Bits(length=32, float=result)
                case F_Op.FTOI:
                    a = instr.rdat1[i].float
                    result = int(a)
                    # Check for overflow (exceeding max int or min int)
                    if result > 2147483647 or result < -2147483648:
                        overflow_detected = True
                    instr.wdat[i] = Bits(length=32, int=result)
                case _:
                    raise ValueError(f"Unsupported operation {instr.opcode} in Conversion.")
        
        if overflow_detected:
            self.perf_count.increment_overflow(instr.opcode)
        
        if self.latency == 1:
            self.single_cycle_latency_compute_tick()

class Sqrt(ArithmeticSubUnit):
    SUPPORTED_OPS = {
        float: [],
    }
    # No opcode yet for SQRT, could be added later so keeping this here in the meantime

    def __init__(self, latency: int, num: int, type_: type = float, telemeter=None):
        if type_ != float:
            raise ValueError("SQRT only supports floating-point operations.")

        super().__init__(latency=latency, type_=type_, num=num, telemeter=telemeter)
    def compute(self):
        # Use current_instr if pipeline is empty (latency=1), else use last queue entry
        instr = self.pipeline.queue[-1]
        if instr is None:
            return

        if not isinstance(instr, Instruction):
            raise TypeError(f"Expected Instruction type in pipeline, got {type(instr)}")
        
        if instr.opcode not in self.SUPPORTED_OPS[self.type_]:
            raise ValueError(f"SQRT does not support operation {instr.opcode} for type {self.type_}")

        for i in range(32):
            if instr.predicate[i].bin == "0":
                continue

            a = instr.rdat1[i].float
            if a < 0.0:
                result = 0.0
            else:
                result = a ** 0.5
            instr.wdat[i] = Bits(length=32, float=result)
        
        if self.latency == 1:
            self.single_cycle_latency_compute_tick()

class Trig(ArithmeticSubUnit):
    SUPPORTED_OPS = {
        float: [F_Op.SIN, F_Op.COS],
    }

    def __init__(self, latency: int, num: int, type_: type = float, telemeter=None):
        if type_ != float:
            raise ValueError("TRIG only supports floating-point operations.")

        super().__init__(latency=latency, type_=type_, num=num, telemeter=telemeter)
        
        # Pre-compute CORDIC constants based on latency
        self._theta_table = [math.atan2(1, 2**i) for i in range(latency)]
        self._K_n = self._compute_K(latency)
    
    def _compute_K(self, n: int) -> float:
        """
        Compute K(n) for n iterations.
        K(n) is the product of cos(arctan(2^-i)) for i = 0 to n-1,
        which equals product of 1/sqrt(1 + 2^(-2i)) for i = 0 to n-1.
        """
        k = 1.0
        for i in range(n):
            k *= 1.0 / math.sqrt(1 + 2 ** (-2 * i))
        return k

    def _cordic(self, alpha: float) -> tuple[float, float]:
        """
        CORDIC algorithm for computing sine and cosine.
        Uses pre-computed constants based on latency attribute.
        
        Args:
            alpha: Input angle in radians
        
        Returns:
            Tuple of (cos(alpha), sin(alpha))
        """
        theta = 0.0
        x = 1.0
        y = 0.0
        P2i = 1.0  # This will be 2**(-i) in the loop
        
        for arc_tangent in self._theta_table:
            sigma = +1 if theta < alpha else -1
            theta += sigma * arc_tangent
            x, y = x - sigma * y * P2i, sigma * P2i * x + y
            P2i /= 2.0
        
        return x * self._K_n, y * self._K_n

    def compute(self):
        # Use current_instr if pipeline is empty (latency=1), else use last queue entry
        instr = self.pipeline.queue[-1]
        if instr is None:
            return

        if not isinstance(instr, Instruction):
            raise TypeError(f"Expected Instruction type in pipeline, got {type(instr)}")
        
        if instr.opcode not in self.SUPPORTED_OPS[self.type_]:
            raise ValueError(f"TRIG does not support operation {instr.opcode} for type {self.type_}")

        overflow_detected = False
        for i in range(32):
            if instr.predicate[i].bin == "0":
                continue

            a = instr.rdat1[i].float
            cos_result, sin_result = self._cordic(a)
            
            match instr.opcode:
                case F_Op.SIN:
                    result = sin_result
                case F_Op.COS:
                    result = cos_result
                case _:
                    raise ValueError(f"Unsupported operation {instr.opcode} in TRIG.")
            
            # Check for invalid results (inf or nan)
            if math.isinf(result) or math.isnan(result):
                overflow_detected = True
            
            instr.wdat[i] = Bits(length=32, float=result)
        
        if overflow_detected:
            self._overflow_pending = True
        
        if self.latency == 1:
            self.single_cycle_latency_compute_tick()

class InvSqrt(ArithmeticSubUnit):
    SUPPORTED_OPS = {
        float: [F_Op.ISQRT],
    }

    def __init__(self, latency: int, num: int, type_: type = float, telemeter=None):
        if type_ != float:
            raise ValueError("InvSqrt only supports floating-point operations.")

        super().__init__(latency=latency, type_=type_, num=num, telemeter=telemeter)
    
    def compute(self):
        # Use current_instr if pipeline is empty (latency=1), else use last queue entry
        instr = self.pipeline.queue[-1]
        if instr is None:
            return

        if not isinstance(instr, Instruction):
            raise TypeError(f"Expected Instruction type in pipeline, got {type(instr)}")
        
        if instr.opcode not in self.SUPPORTED_OPS[self.type_]:
            raise ValueError(f"InvSqrt does not support operation {instr.opcode} for type {self.type_}")

        overflow_detected = False
        for i in range(32):
            if instr.predicate[i].bin == "0":
                continue
                
            match instr.opcode:
                case F_Op.ISQRT:
                    a = instr.rdat1[i].float
                    if a <= 0.0:
                        result = 0.0
                        overflow_detected = True  # Invalid input
                    else:
                        # Fast inverse square root algorithm (Quake III)
                        # Convert float to int representation for bit manipulation
                        
                        # Get the bit representation using Bits
                        bits_obj = Bits(length=32, float=a)
                        i_bits = bits_obj.int
                        
                        # Magic constant for fast inverse square root
                        i_bits = 0x5f3759df - (i_bits >> 1)
                        
                        # Convert back to float using Bits
                        y = Bits(length=32, int=i_bits).float
                        
                        # Newton-Raphson iterations based on latency
                        # More iterations = more accuracy, simulating more cycles
                        num_iterations = max(1, self.latency - 1)
                        for _ in range(num_iterations):
                            y = y * (1.5 - 0.5 * a * y * y)
                        
                        result = y
                        
                        # Check for invalid results
                        if math.isinf(result) or math.isnan(result):
                            overflow_detected = True
                    
                    instr.wdat[i] = Bits(length=32, float=result)
                case _:
                    raise ValueError(f"Unsupported operation {instr.opcode} in InvSqrt for type {self.type_}.")
        
        if overflow_detected:
            self._overflow_pending = True
        
        if self.latency == 1:
            self.single_cycle_latency_compute_tick()