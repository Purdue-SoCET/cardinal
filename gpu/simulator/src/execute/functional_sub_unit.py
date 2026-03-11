from builtins import range
from abc import ABC, abstractmethod
import math
from bitstring import Bits
from gpu.common.custom_enums_multi import Op, R_Op, I_Op, F_Op, B_Op, P_Op, J_Op, C_Op, H_Op, U_Op
from simulator.utils.performance_counter.execute import ExecutePerfCount as PerfCount
from simulator.compact_queue import CompactQueue
from simulator.latch_forward_stage import LatchIF, Instruction, ForwardingIF

class FunctionalUnitPipeline(CompactQueue):
    def __init__(self, latency: int):
        super().__init__(length=latency, type_=Instruction)

class FunctionalSubUnit(ABC):
    def __init__(self, num: int):
        self.name = f"{self.__class__.__name__}_{num}"
        self.ready_out = True
        self.perf_count = PerfCount(name=self.name)

        # the way stages are connected in the SM class, we need (latency - 1) latches
        self.ex_wb_interface = LatchIF(name=f"{self.name}_EX_WB_Interface")
    
    @abstractmethod
    def tick(self):
        pass
    
    @abstractmethod
    def compute(self):
        pass

class Branch(FunctionalSubUnit):
    SUPPORTED_OPS = [
        B_Op.BEQ, B_Op.BNE, H_Op.HALT
    ]
    def __init__(self, num: int):
        super().__init__(num=num)
        self.data = None
    
    def compute(self):
        instr = self.data

        if instr is None or not isinstance(instr, Instruction):
            return
        
        if instr.opcode not in self.SUPPORTED_OPS:
            raise ValueError(f"Branch does not support operation {instr.opcode}, instruction i at pc: {instr.pc}")
        
        # FIX: initializng w-dat predicabtee becaue it yelling
        instr.wdat_pred = [Bits(uint=0, length=1) for _ in range(32)]
        for i in range(32):
            #if instr.predicate[i].bin == "0":
                #continue
            match instr.opcode:
                case B_Op.BEQ:
                    instr.wdat_pred[i] = Bits(uint=((instr.rdat1[i].uint == instr.rdat2[i].uint) & instr.predicate[i].uint), length=1)
                case B_Op.BNE:
                    instr.wdat_pred[i] = Bits(uint=((instr.rdat1[i].uint != instr.rdat2[i].uint) & instr.predicate[i].uint), length=1)
                case H_Op.HALT:
                    continue
                case _:
                    raise ValueError(f"Unsupported operation {instr.opcode} in Branch.")
        self.data = instr
        
    def tick(self, behind_latch: LatchIF) -> Instruction:
        # Branch unit is assumed to have single-cycle latency for simplicity
        if isinstance(behind_latch, LatchIF):
            in_data = behind_latch.snoop()
        else:
            in_data = None

        if self.ex_wb_interface.ready_for_push():
            if isinstance(in_data, Instruction):
                in_data.mark_fu_enter(self.name, self.perf_count.total_cycles)

            out_data = self.data
            self.data = in_data

            if isinstance(out_data, Instruction):
                out_data.mark_fu_exit(self.name, self.perf_count.total_cycles)

            if isinstance(behind_latch, LatchIF):
                behind_latch.pop()

            self.ready_out = True
        else:
            out_data = False
            self.ready_out = False            

        self.perf_count.increment(
            instr=in_data, 
            ready_out=self.ready_out, 
            ex_wb_interface_ready=self.ex_wb_interface.ready_for_push()
        )

        return out_data

class Jump(FunctionalSubUnit):
    SUPPORTED_OPS = [
        P_Op.JPNZ, J_Op.JAL, I_Op.JALR
    ]
    def __init__(self, num: int, schedule_if: ForwardingIF = None):
        super().__init__(num=num)

        self.schedule_if = schedule_if
        self.data = None
    
    def compute(self):
        if self.schedule_if is None:
            raise ValueError("Jump unit requires a forwarding interface to the Schedule stage for correct operation.")
        instr = self.data
        schedule_if_value = None # defaults to PC + 4, this is signified by pusing None to Schedule Stage Forwarding Interface

        if instr is None or not isinstance(instr, Instruction):
            return
        
        if instr.opcode not in self.SUPPORTED_OPS:
            raise ValueError(f"Jump does not support operation {instr.opcode}")
        

        match instr.opcode:
            case J_Op.JAL:
                schedule_if_value = {"warp_group": instr.warp_group_id, "dest": instr.pc.uint + instr.imm.int}
                instr.wdat = [Bits(uint=(instr.pc.uint + 4) & 0xFFFFFFFF, length=32) for x in range(32)]
            case I_Op.JALR:
                if not all(data == instr.rdat1[0] for data in instr.rdat1):
                      raise ValueError("JALR requires all rdat1 values to be the same for correct scheduling.")
                schedule_if_value = {"warp_group": instr.warp_group_id, "dest": instr.rdat1[0].uint + instr.imm}
                instr.wdat = None
            case P_Op.JPNZ:
                if not all(pred_val == instr.predicate[0] for pred_val in instr.predicate):
                    raise ValueError("JPNZ requires all predicate values to be the same for correct scheduling.")
                if instr.predicate[0] == Bits(length=1, uint=1):
                    schedule_if_value = {"warp_group": instr.warp_group_id, "dest": instr.pc + instr.imm}
                instr.wdat = None
            case _:
                raise ValueError(f"Unsupported operation {instr.opcode} in Jump.")
            
        self.schedule_if.push(schedule_if_value)
        self.data = instr
        
    def tick(self, behind_latch: LatchIF) -> Instruction:
        if self.schedule_if is None:
            raise ValueError("Jump unit requires a forwarding interface to the Schedule stage for correct operation.")
        # Jump unit is assumed to have single-cycle latency for simplicity
        if isinstance(behind_latch, LatchIF):
            in_data = behind_latch.snoop()
        else:
            in_data = None

        if self.ex_wb_interface.ready_for_push():
            if isinstance(in_data, Instruction):
                in_data.mark_fu_enter(self.name, self.perf_count.total_cycles)

            out_data = self.data
            self.data = in_data
            if isinstance(out_data, Instruction):
                out_data.mark_fu_exit(self.name, self.perf_count.total_cycles)

            if isinstance(behind_latch, LatchIF):
                behind_latch.pop()

            self.ready_out = True
        else:
            out_data = False
            self.ready_out = False            

        self.perf_count.increment(
            instr=in_data, 
            ready_out=self.ready_out, 
            ex_wb_interface_ready=self.ex_wb_interface.ready_for_push()
        )

        return out_data
        
class ArithmeticSubUnit(FunctionalSubUnit):
    def __init__(self, latency: int, num: int, type_: type):
        super().__init__(num=num)
        self.name = f"{self.__class__.__name__}_{type_.__name__}_{num}"
        self.latency = latency

        if type_ not in [int, float]:
            raise ValueError(f"Unsupported type '{type_}' for FunctionalSubUnit. Must be {int} or {float}.")

        self.type_ = type_

        self.ex_wb_interface = LatchIF(name=f"{self.name}_EX_WB_Interface")

        # the way stages are connected in the SM class, we need (latency - 1) latches
        self.pipeline = FunctionalUnitPipeline(latency=max(1, latency-1))

    def single_cycle_latency_compute_tick(self):
        if self.latency != 1 or self.ready_out is False:
            return
        
        self.ex_wb_interface.force_push(self.pipeline.advance(None))

    def tick(self, behind_latch: LatchIF) -> Instruction:
        if isinstance(behind_latch, LatchIF):
            in_data = behind_latch.snoop()
        else:
            in_data = None

        if self.ex_wb_interface.ready_for_push():
            if isinstance(in_data, Instruction):
                in_data.mark_fu_enter(self.name, self.perf_count.total_cycles)

            out_data = self.pipeline.advance(in_data)

            if isinstance(out_data, Instruction):
                out_data.mark_fu_exit(self.name, self.perf_count.total_cycles)

            if isinstance(behind_latch, LatchIF):
                behind_latch.pop()

            self.ready_out = True

        elif self.latency > 1 and not self.pipeline.is_full:
            out_data = False

            if isinstance(in_data, Instruction):
                in_data.mark_fu_enter(self.name, self.perf_count.total_cycles)

            self.pipeline.compact(in_data)

            if isinstance(behind_latch, LatchIF):
                behind_latch.pop()
        else:
            out_data = False
            self.ready_out = False            

        self.perf_count.increment(
            instr=in_data, 
            ready_out=self.ready_out, 
            ex_wb_interface_ready=self.ex_wb_interface.ready_for_push()
        )
        
        return out_data # return data to the Exectute stage so that all results can be collected and sent to WB stage together

class Conv(ArithmeticSubUnit):
    SUPPORTED_OPS = {
        float: [F_Op.ITOF, F_Op.FTOI]
    }

    def __init__(self, latency: int, num: int, type_: type = float):
        
        # converstion unit will be considered float since it requires float hardware for all operations, even if int is involved
        if type_ != float:
            raise ValueError("Conversion unit only supports floating-point operations.")

        super().__init__(latency=latency, num=num, type_=type_)

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
                    instr.wdat[i] = Bits(length=32, int=result & 0xFFFFFFFF)
                case _:
                    raise ValueError(f"Unsupported operation {instr.opcode} in Conversion.")
        
        if overflow_detected:
            self.perf_count.increment_overflow(instr.opcode)

        if self.latency == 1:
            self.single_cycle_latency_compute_tick()

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

    def __init__(self, latency: int, num: int, type_: type):
        if type_ != int and type_ != float:
            raise ValueError("ALU only supports integer and float operations.")

        super().__init__(latency=latency, num=num, type_=type_)

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
                    b = instr.pc
                else:
                    b = instr.rdat1[i].int
            else:
                b = instr.rdat2[i].int

            match instr.opcode:
                # case R_Op.ADD | I_Op.ADDI:
                case R_Op.ADD | I_Op.ADDI | C_Op.CSRR | R_Op.ADDF:
                    result = a + b            
                    # Check for signed overflow
                    if instr.opcode == R_Op.ADD or instr.opcode == I_Op.ADDI and (result > 2147483647 or result < -2147483648):
                        overflow_detected = True
                case R_Op.SUB | I_Op.SUBI | R_Op.SUBF:
                    result = a - b
                    # Check for signed overflow
                    if instr.opcode == R_Op.SUB and (result > 2147483647 or result < -2147483648):
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
                case U_Op.AUIPC:
                    result = (b + ((a & 0xFFFFF) << 12)) & 0xFFFFFFFF
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
            self.perf_count.increment_overflow(instr.opcode)

        if self.latency == 1:
            self.single_cycle_latency_compute_tick()

class Mul(ArithmeticSubUnit):
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
            self.perf_count.increment_overflow(instr.opcode)
        
        if self.latency == 1:
            self.single_cycle_latency_compute_tick()

class Div(ArithmeticSubUnit):
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

class Sqrt(ArithmeticSubUnit):
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
            self.perf_count.increment_overflow(instr.opcode)
        
        if self.latency == 1:
            self.single_cycle_latency_compute_tick()

class InvSqrt(ArithmeticSubUnit):
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
            self.perf_count.increment_overflow(instr.opcode)
        
        if self.latency == 1:
            self.single_cycle_latency_compute_tick()

