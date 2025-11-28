from abc import ABC, abstractmethod
import math
from bitstring import Bits
from custom_enums_multi import Op, R_Op, I_Op, F_Op
from performance_counter import PerfCount
from compact_queue import CompactQueue
from latch_forward_stage import LatchIF, Instruction

class FunctionalUnitPipeline(CompactQueue):
    def __init__(self, latency: int):
        super().__init__(length=latency, type_=Instruction)

class FunctionalSubUnit(ABC):
    def __init__(self, latency: int, num: int, type_: type):
        self.name = f"{self.__class__.__name__}_{type_.__name__}_{num}"
        self.latency = latency
        self.ready_out = True
        self.perf_count = PerfCount(name=self.name)

        if type_ not in [int, float]:
            raise ValueError(f"Unsupported type '{type_}' for FunctionalSubUnit. Must be {int} or {float}.")

        self.type_ = type_

        # the way stages are connected in the SM class, we need (latency - 1) latches
        self.pipeline = FunctionalUnitPipeline(latency=max(1, latency-1))
        self.ex_wb_interface = LatchIF(name=f"{self.name}_EX_WB_Interface")
    
    @abstractmethod
    def compute(self):
        pass

    def single_cycle_latency_compute_tick(self):
        if self.latency != 1 or self.ready_out is False:
            return
        
        self.ex_wb_interface.force_push(self.pipeline.advance(None))

        
    def tick(self, in_data: Instruction) -> Instruction:
        # ready signal back to Issue Stage
        self.ready_out = True

        if isinstance(in_data, Instruction):
            in_data.mark_fu_enter(self.name, self.perf_count.total_cycles)

        if self.ex_wb_interface.ready_for_push():
            out_data = self.pipeline.advance(in_data)
        else:
            out_data = False
            self.pipeline.compact(in_data)
            if self.latency > 1 and self.pipeline.is_full:
                self.ready_out = False
            elif self.latency == 1 and in_data is not None:
                self.ready_out = False
            #if self.pipeline.is_full:
            #    self.ready_out = False

        if isinstance(out_data, Instruction):
            out_data.mark_fu_exit(self.name, self.perf_count.total_cycles)

        self.perf_count.increment(
            instr=in_data, 
            ready_out=self.ready_out, 
            ex_wb_interface_ready=self.ex_wb_interface.ready_for_push()
        )
        
        return out_data # return data to the Exectute stage so that all results can be collected and sent to WB stage together


class Alu(FunctionalSubUnit):
    SUPPORTED_OPS = {
        int: [
            R_Op.ADD, R_Op.SUB, R_Op.AND, R_Op.OR, 
            R_Op.XOR, R_Op.SLT, R_Op.SLTU, R_Op.SLL, 
            R_Op.SRL, R_Op.SRA, I_Op.SUBI, I_Op.ADDI,
            I_Op.ORI, I_Op.XORI, I_Op.SLTI, I_Op.SLTIU,
            I_Op.SLLI, I_Op.SRLI, I_Op.SRAI,
        ],
        float: [
            # No floating-point operations supported in ALU
        ]
    }

    def __init__(self, latency: int, num: int, type_: type = int):
        if type_ != int:
            raise ValueError("ALU only supports integer operations.")

        super().__init__(latency=latency, num=num, type_=type_)

    def compute(self):
        # Use current_instr if pipeline is empty (latency=1), else use last queue entry
        instr = self.pipeline.queue[-1]
        if instr is None:
            return

        if not isinstance(instr, Instruction):
            raise TypeError(f"Expected Instruction type in pipeline, got {type(instr)}")
        
        if instr.opcode not in self.SUPPORTED_OPS[self.type_]:
            raise ValueError(f"ALU does not support operation {instr.opcode}")

        overflow_detected = False
        for i in range(32):
            if instr.predicate[i].bin == 0b0:
                continue

            if self.type_ == int: 
                a = instr.rdat1[i].int
                b = instr.rdat2[i].int
            else:
                raise ValueError("ALU only supports integer operations.")

            match instr.opcode:
                case R_Op.ADD | I_Op.ADDI:
                    result = a + b
                    # Check for signed overflow
                    if result > 2147483647 or result < -2147483648:
                        overflow_detected = True
                case R_Op.SUB | I_Op.SUBI:
                    result = a - b
                    # Check for signed overflow
                    if result > 2147483647 or result < -2147483648:
                        overflow_detected = True
                case R_Op.AND:
                    result = a & b
                case R_Op.OR | I_Op.ORI:
                    result = a | b
                case R_Op.XOR | I_Op.XORI:
                    result = a ^ b
                case R_Op.SLT | I_Op.SLTI:
                    result = int(a < b)
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
                case _:
                    raise ValueError(f"Unsupported operation {instr.opcode} in ALU.")
            
            if self.type_ == int:
                # Mask to 32 bits and store as unsigned, bitstring will handle conversion
                instr.wdat[i] = Bits(length=32, uint=result & 0xFFFFFFFF)
            else:
                raise ValueError("ALU only supports integer operations.")
        
        if overflow_detected:
            self.perf_count.increment_overflow(instr.opcode)

        if self.latency == 1:
            self.single_cycle_latency_compute_tick()

class AddSub(FunctionalSubUnit):
    SUPPORTED_OPS = {
        float: [R_Op.ADDF, R_Op.SUBF],
    }

    def __init__(self, latency: int, num: int,  type_: type = float):
        if type_ != float:
            raise ValueError("AddSub only supports floating-point operations.")

        super().__init__(latency=latency, type_=type_, num=num)

    def compute(self):
        # Use current_instr if pipeline is empty (latency=1), else use last queue entry
        instr = self.pipeline.queue[-1]
        if instr is None:
            return

        if not isinstance(instr, Instruction):
            raise TypeError(f"Expected Instruction type in pipeline, got {type(instr)}")
        
        if instr.opcode not in self.SUPPORTED_OPS[self.type_]:
            raise ValueError(f"AddSub does not support operation {instr.opcode}")

        overflow_detected = False
        for i in range(32):
            if instr.predicate[i].bin == 0b0:
                continue

            a = instr.rdat1[i].float
            b = instr.rdat2[i].float

            match instr.opcode:
                case R_Op.ADDF:
                    result = a + b
                case R_Op.SUBF:
                    result = a - b
                case _:
                    raise ValueError(f"Unsupported operation {instr.opcode} in AddSub.")
            
            # Check for floating-point overflow/underflow (inf or -inf)
            if math.isinf(result) or math.isnan(result):
                overflow_detected = True
            
            instr.wdat[i] = Bits(length=32, float=result)
        
        if overflow_detected:
            self.perf_count.increment_overflow(instr.opcode)
        
        if self.latency == 1:
            self.single_cycle_latency_compute_tick()

class Mul(FunctionalSubUnit):
    SUPPORTED_OPS = {
        int: [R_Op.MUL],
        float: [R_Op.MULF],
    }

    def __init__(self, latency: int, num: int, type_: type):
        if type_ not in [int, float]:
            raise ValueError("MUL only supports integer and floating-point operations.")

        super().__init__(latency=latency, type_=type_, num=num)
    def compute(self):
        # Use current_instr if pipeline is empty (latency=1), else use last queue entry
        instr = self.pipeline.queue[-1]
        if instr is None:
            return

        if not isinstance(instr, Instruction):
            raise TypeError(f"Expected Instruction type in pipeline, got {type(instr)}")
        
        if instr.opcode not in self.SUPPORTED_OPS[self.type_]:
            raise ValueError(f"MUL does not support operation {instr.opcode}")

        overflow_detected = False
        for i in range(32):
            if instr.predicate[i].bin == 0b0:
                continue

            match instr.opcode:
                case R_Op.MUL:
                    a = instr.rdat1[i].int
                    b = instr.rdat2[i].int
                    result = a * b
                    # Check for signed overflow
                    if result > 2147483647 or result < -2147483648:
                        overflow_detected = True
                    instr.wdat[i] = Bits(length=32, uint=result & 0xFFFFFFFF)
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
            self.perf_count.increment_overflow(instr.opcode)
        
        if self.latency == 1:
            self.single_cycle_latency_compute_tick()

class Div(FunctionalSubUnit):
    SUPPORTED_OPS = {
        int: [R_Op.DIV],
        float: [R_Op.DIVF],
    }

    def __init__(self, latency: int, num: int, type_: type):
        if type_ not in [int, float]:
            raise ValueError("DIV only supports integer and floating-point operations.")

        super().__init__(latency=latency, type_=type_, num=num)
    def compute(self):
        # Use current_instr if pipeline is empty (latency=1), else use last queue entry
        instr = self.pipeline.queue[-1]
        if instr is None:
            return

        if not isinstance(instr, Instruction):
            raise TypeError(f"Expected Instruction type in pipeline, got {type(instr)}")
        
        if instr.opcode not in self.SUPPORTED_OPS[self.type_]:
            raise ValueError(f"DIV does not support operation {instr.opcode}")

        overflow_detected = False
        for i in range(32):
            if instr.predicate[i].bin == 0b0:
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
                    instr.wdat[i] = Bits(length=32, float=result)
                case _:
                    raise ValueError(f"Unsupported operation {instr.opcode} in DIV.")
        
        if overflow_detected:
            self.perf_count.increment_overflow(instr.opcode)
        
        if self.latency == 1:
            self.single_cycle_latency_compute_tick()

class Sqrt(FunctionalSubUnit):
    SUPPORTED_OPS = {
        float: [],
    }
    # No opcode yet for SQRT, could be added later so keeping this here in the meantime

    def __init__(self, latency: int, num: int, type_: type = float):
        if type_ != float:
            raise ValueError("SQRT only supports floating-point operations.")

        super().__init__(latency=latency, type_=type_, num=num)
    def compute(self):
        # Use current_instr if pipeline is empty (latency=1), else use last queue entry
        instr = self.pipeline.queue[-1]
        if instr is None:
            return

        if not isinstance(instr, Instruction):
            raise TypeError(f"Expected Instruction type in pipeline, got {type(instr)}")
        
        if instr.opcode not in self.SUPPORTED_OPS[self.type_]:
            raise ValueError(f"SQRT does not support operation {instr.opcode}")

        for i in range(32):
            if instr.predicate[i].bin == 0b0:
                continue

            a = instr.rdat1[i].float
            if a < 0.0:
                result = 0.0
            else:
                result = a ** 0.5
            instr.wdat[i] = Bits(length=32, float=result)
        
        if self.latency == 1:
            self.single_cycle_latency_compute_tick()

class Trig(FunctionalSubUnit):
    SUPPORTED_OPS = {
        float: [F_Op.SIN, F_Op.COS],
    }

    def __init__(self, latency: int, num: int, type_: type = float):
        if type_ != float:
            raise ValueError("TRIG only supports floating-point operations.")

        super().__init__(latency=latency, type_=type_, num=num)
        
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
            raise ValueError(f"TRIG does not support operation {instr.opcode}")

        overflow_detected = False
        for i in range(32):
            if instr.predicate[i].bin == 0b0:
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
            self.perf_count.increment_overflow(instr.opcode)
        
        if self.latency == 1:
            self.single_cycle_latency_compute_tick()

class InvSqrt(FunctionalSubUnit):
    SUPPORTED_OPS = {
        float: [F_Op.ISQRT],
    }

    def __init__(self, latency: int, num: int, type_: type = float):
        if type_ != float:
            raise ValueError("InvSqrt only supports floating-point operations.")

        super().__init__(latency=latency, type_=type_, num=num)
    
    def compute(self):
        # Use current_instr if pipeline is empty (latency=1), else use last queue entry
        instr = self.pipeline.queue[-1]
        if instr is None:
            return

        if not isinstance(instr, Instruction):
            raise TypeError(f"Expected Instruction type in pipeline, got {type(instr)}")
        
        if instr.opcode not in self.SUPPORTED_OPS[self.type_]:
            raise ValueError(f"InvSqrt does not support operation {instr.opcode}")

        overflow_detected = False
        for i in range(32):
            if instr.predicate[i].bin == 0b0:
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
                    raise ValueError(f"Unsupported operation {instr.opcode} in InvSqrt.")
        
        if overflow_detected:
            self.perf_count.increment_overflow(instr.opcode)
        
        if self.latency == 1:
            self.single_cycle_latency_compute_tick()

