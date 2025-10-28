import sys, os

# Dynamically locate the project root (SoCET_GPU_FuncSim)
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../.."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from gpu.gpu_sim.cyclesim.src.base_class import StageInterface, PipelineStage, SM, LoggerBase, PerfCounterBase, FunctionalUnitBase

from collections import deque
from dataclasses import dataclass, field
from typing import List, Any, Optional

# =========================================================
#  DEFINE YOUR CLASSES HERE; LOOK AT BELOW FOR REFERENCE. TEMPLATE PROVIDED.
# =========================================================

class FetchStage(PipelineStage):
    def __init__(self, parent_core):
        super().__init__("Fetch", parent_core)
        self.waiting_for_hit = False
        self.pending_req = None

    def process(self, inst):
        fb = self.feedback_links.get("icache")
        ihit = None
        if fb:
            fb_msg = fb.receive()
            if fb_msg is not None:
                ihit = fb_msg.get("ihit", None)
                print(f"[Fetch] Got iCache feedback: ihit={ihit}")
            else:
                print("Ihit not received.")

        # Case 1: stalled waiting for hit
        if self.waiting_for_hit:
            if ihit is True:
                print(f"[Fetch] iCache hit resolved for pc=0x{self.pending_req['pc']:x}.")
                self.waiting_for_hit = False
                resolved = self.pending_req
                self.pending_req = None

                # ✅ Do NOT re-output the same resolved PC downstream.
                # Simply mark that you’re ready to accept the next request.
                return None

        # Case 2: no stall, new fetch request incoming
        if inst is None:
            return None

        print(f"[Fetch] Sending fetch req → ICache: pc=0x{inst['pc']:x}")
        self.waiting_for_hit = True
        self.pending_req = inst
        return inst

def make_raw(op7: int, rd: int = 1, rs1: int = 2, mid6: int = 3, pred: int = 0, packet_start: bool = False, packet_end: bool = False) -> int:
        """Construct a 32-bit instruction word according to the DecodeStage layout:
        bits [6:0]   = opcode7
        bits [12:7]  = rd (6)
        bits [18:13] = rs1 (6)
        bits [24:19] = mid6 (6)
        bits [29:25] = pred (5)
        bit  [30]    = packet_start
        bit  [31]    = packet_end
        """
        raw = (
            (int(packet_end) << 31)
            | (int(packet_start) << 30)
            | ((pred & 0x1F) << 25)
            | ((mid6 & 0x3F) << 19)
            | ((rs1 & 0x3F) << 13)
            | ((rd & 0x3F) << 7)
            | (op7 & 0x7F)
        )
        return raw
    
class ICacheFU(FunctionalUnitBase):
    def __init__(self, name="ICacheFU", latency=3):
        super().__init__(name=name, latency=latency)
        self.icache_lut = {
            0x100: make_raw(0x00, rd=1, rs1=2, mid6=3),
            0x104: make_raw(0x10, rd=5, rs1=6, mid6=0),
            0x108: make_raw(0x20, rd=2, rs1=3, mid6=4),
            0x10C: make_raw(0x30, rd=2, rs1=3, mid6=4),
            0x110: make_raw(0x40, rd=0, rs1=1, mid6=2, pred=1, packet_start=True),
            0x114: make_raw(0x7F, rd=0, rs1=0, mid6=0),
        }

        # Internal state
        self.pending = []         # list of dicts: {"pc":..., "warp":..., "remaining":...}
        self.completed = []       # ready results to forward next tick

    def accept(self, op: dict) -> bool:
        pc = op["pc"]
        warp = op["warp_id"]

        # Fast path: cache hit
        if pc in self.icache_lut:
            raw = self.icache_lut[pc]
            result = {"pc": pc, "warp_id": warp, "raw": raw, "ihit": True}
            self.completed.append(result)
            print(f"[{self.name}] IMMEDIATE HIT  pc=0x{pc:x}")
            return True

        # Miss path: enqueue miss request
        self.pending.append({"pc": pc, "warp": warp, "remaining": self.latency})
        print(f"[{self.name}] MISS start for pc=0x{pc:x} ({self.latency} cycles)")

        # 🔧 NEW: immediately tell fetch/decode there's a miss (ihit=False)
        for fb_name, fb_if in self.parent_stage.feedback_links.items():
            if fb_if.is_feedback:
                fb_if.send({"pc": pc, "warp_id": warp, "ihit": False})
                print(f"[{self.name}] Sent early miss feedback → {fb_name}")

        return True

    def tick(self):
        # Advance outstanding misses
        for req in self.pending:
            req["remaining"] -= 1
            if req["remaining"] == 0:
                pc = req["pc"]
                warp = req["warp"]
                self.icache_lut[pc] = make_raw(0x20, rd=9, rs1=9, mid6=9)  # Fill line
                raw = self.icache_lut[pc]
                self.completed.append({"pc": pc, "warp_id": warp, "raw": raw, "ihit": True})
                print(f"[{self.name}] MISS resolved pc=0x{pc:x}")
        # Remove finished requests
        self.pending = [r for r in self.pending if r["remaining"] > 0]

        # Send completed results downstream (if outputs available)
        while self.completed:
            result = self.completed.pop(0)
            for out in self.outputs:
                if out.can_accept():
                    out.send(result)
                    print(f"[{self.name}] → sent result {result}")
                    break


class ICacheStage(PipelineStage):
    def __init__(self, parent_core, miss_latency=3):
        super().__init__("ICache", parent_core)
        self.fu = ICacheFU(latency=miss_latency)
        self.fu.parent_stage = self      # 🔧 <---- add this line
        self.add_subunit(self.fu)

    def process(self, inst):
        if not inst:
            return None

        # Accept the instruction into the FU (handles hit/miss)
        self.fu.accept(inst)

        # Check if FU completed something this cycle
        if self.fu.completed:
            result = self.fu.completed.pop(0)
            print("CACHE FINISHED SOMETHING ! \n")
            # Send feedbacks
            for dst in ("fetch", "decode"):
                if dst in self.feedback_links:
                    self.feedback_links[dst].send({
                        "ihit": result["ihit"],
                        "pc": result["pc"],
                        "warp_id": result["warp_id"],
                    })
                    print(f"[ICache] Sent feedback {dst}: pc=0x{result['pc']:x}, ihit={result['ihit']}")

            # ✅ Return the instruction to move forward down the pipeline
            return result

        return None


class DecodeStage(PipelineStage):
    def __init__(self, parent_core):
        super().__init__("Decode", parent_core)

    def process(self, inst):
        if not inst:
            return None

        ihit = inst.get("ihit", False)
        pc = inst["pc"]

        if not ihit:
            print(f"[Decode] (NOP) Missed instruction at pc=0x{pc:x}")
            return None

        if not inst:
            return None

        # Interpret instruction as a 32-bit integer and extract the low 7-bit opcode.
        raw = int(inst.get("raw", 0)) & 0xFFFFFFFF
        opcode_upper = raw & 0x7  # bits 6-3
        opcode_lower = (raw >> 3) & 0xF  # bits 2-0
        opcode_r0_dict = {
            "000": "add",
            "001": "sub",
            "010": "mul",
            "011": "div",
            "100": "and",
            "101": "or",
            "110": "xor",
            "111": "slt",
        }
        opcode_r1_dict = {
            "000": "sltu",
            "001": "addf",
            "010": "subf",
            "011": "mulf",
            "100": "divf",
            "101": "sll",
            "110": "srl",
            "111": "sra",
        }
        opcode_i0_dict = {
            "000": "addi",
            "001": "subi",
            "101": "ori",
            "111": "slti",
        }
        opcode_i1_dict = {
            "000": "sltiu",
            "001": "srli",
            "101": "srai",
        }
        opcode_i2_dict = {
            "000": "lw",
            "001": "st",
            "010": "lb",
            "011": "jalr"
        }

        def sign_extend(value: int, bits: int) -> int:
            sign_bit = 1 << (bits - 1)
            return (value & (sign_bit - 1)) - (value & sign_bit)

        # Field extraction according to the provided ISA layout
        opcode7 = raw & 0x7F
        rd = (raw >> 7) & 0x3F
        rs1 = (raw >> 13) & 0x3F
        # bits [24:19] used either as rs2 (6 bits) or imm field depending on type
        mid6 = (raw >> 19) & 0x3F
        pred = (raw >> 25) & 0x1F
        packet_start = bool((raw >> 30) & 0x1)
        packet_end = bool((raw >> 31) & 0x1)

        high4 = (opcode7 >> 3) & 0xF
        low3 = opcode7 & 0x7

        # Build opcode -> mnemonic map from the provided table (subset implemented)
        opcode_map = {
            # R-type (high4 = 0b0000)
            0b0000000: "add",
            0b0000001: "sub",
            0b0000010: "mul",
            0b0000011: "div",
            0b0000100: "and",
            0b0000101: "or",
            0b0000110: "xor",
            0b0000111: "slt",
            # R-type / FP and shifts (high4 = 0b0001)
            0b0001000: "sltu",  # 0001 000 -> 8
            0b0001001: "addf",
            0b0001010: "subf",
            0b0001011: "mulf",
            0b0001100: "divf",
            0b0001101: "sll",
            0b0001110: "srl",
            0b0001111: "sra",
            # I-type (0010, 0011)
            0b0010000: "addi",
            0b0010001: "subi",
            0b0010101: "ori",
            0b0010111: "slti",
            0b0011000: "sltiu",  # 0011 000 -> 24
            0b0011110: "srli",
            0b0011111: "srai",
            0b0100000: "lw",    # 0100 000 -> 32
            0b0100001: "lh",
            0b0100010: "lb",
            0b0100011: "jalr",
            # F-type (0101)
            0b0101000: "isqrt",
            0b0101001: "sin",
            0b0101010: "cos",
            0b0101011: "itof",
            0b0101100: "ftoi",
            # S-type (0110)
            0b0110000: "sw",
            0b0110001: "sh",
            0b0110010: "sb",
            # B-type (1000)
            0b1000000: "beq",
            0b1000001: "bne",
            0b1000010: "bge",
            0b1000011: "bgeu",
            0b1000100: "blt",
            0b1000101: "bltu",
            # U-type (1010)
            0b1010000: "auipc",
            0b1010001: "lli",
            0b1010010: "lmi",
            0b1010100: "lui",
            # C-type (1011)
            0b1011000: "csrr",
            0b1011001: "csrw",
            # J-type (1100)
            0b1100000: "jal",
            # P-type (1101)
            0b1101000: "jpnz",
            # H-type: halt is all ones (0b1111111 -> 127)
            0b1111111: "halt",
        }

        mnemonic = opcode_map.get(opcode7, "nop")

        # Interpret fields according to determined instruction class (best-effort)
        decoded: dict = {
            "raw": raw,
            "opcode7": opcode7,
            "mnemonic": mnemonic,
            "predication": pred,
            "packet_start": packet_start,
            "packet_end": packet_end,
        }

        # Classify by high4 nibble
        if high4 in (0x0, 0x1):
            # R-type family (register-register)
            decoded.update({"type": "R", "rd": rd, "rs1": rs1, "rs2": mid6})
        elif high4 in (0x2, 0x3, 0x4):
            # I-type family (immediates and loads/jalr)
            imm6 = sign_extend(mid6, 6)
            decoded.update({"type": "I", "rd": rd, "rs1": rs1, "imm": imm6})
        elif high4 == 0x5:
            # F-type / unary ops: rd, rs1
            decoded.update({"type": "F", "rd": rd, "rs1": rs1})
        elif high4 in (0x6, 0x7):
            # S-type family (store / memory write)
            decoded.update({"type": "S", "imm": mid6, "rs1": rs1, "rs2": rd})
        elif high4 == 0x8:
            # B-type (branch): preddest in rd field
            decoded.update({"type": "B", "pred_dest": rd, "rs1": rs1, "rs2": mid6})
        elif high4 == 0xA:
            # U-type: 12-bit immediate occupies bits [24:13]
            imm12 = (raw >> 13) & 0xFFF
            decoded.update({"type": "U", "rd": rd, "imm12": sign_extend(imm12, 12)})
        elif high4 == 0xB:
            # C-type: CSR op
            decoded.update({"type": "C", "rd": rd, "csr": (raw >> 13) & 0x3FF})
        elif high4 == 0xC:
            # J-type: jal
            imm12 = (raw >> 13) & 0xFFF
            decoded.update({"type": "J", "rd": rd, "imm12": sign_extend(imm12, 12)})
        elif high4 == 0xD:
            # P-type: predicated jump
            decoded.update({"type": "P", "rs1": rs1, "rs2": mid6})
        elif opcode7 == 0x7F:
            decoded.update({"type": "H", "mnemonic": "halt"})
        else:
            decoded.update({"type": "UNKNOWN"})

        # Attach the original instruction for reference
        decoded["orig_inst"] = inst
        print('\n')
        print(f"[Decode] Decoding pc=0x{pc:x}, raw=0x{inst['raw']:08x}")
        return {"decoded": True, "decoded_fields": decoded}

class IBufferStage(PipelineStage):
    def __init__(self, parent_core, depth: int = 8):
        super().__init__("IBuffer", parent_core)
        self.q = deque(maxlen=depth)

    def process(self, item):
        # Enqueue whatever arrived this cycle.
        if item is not None:
            self.q.append(item)

        print(self.q)

        # Dequeue at most one item if downstream can accept.
        if self.output_if and self.output_if.can_accept() and self.q:
            return self.q.popleft()

        return None

    # ---------------------------
    # Visibility helpers
    # ---------------------------
    def _compact(self, item: any) -> any:
        """
        Make entries easy to read. Pull common fields if present (mnemonic/opcode/warp/pc).
        Falls back to a tiny dict or repr to avoid huge prints.
        """
        try:
            if isinstance(item, dict):
                out = {}
                df = item.get("decoded_fields")
                oc = item.get("oc")
                if df and "mnemonic" in df: out["mn"] = df["mnemonic"]
                if oc and "opcode" in oc:   out["op"] = oc["opcode"]
                if oc and "warp_id" in oc:  out["warp"] = oc["warp_id"]
                if "pc" in item:            out["pc"] = hex(item["pc"])
                if out:
                    return out
                # fallback: keep only a few keys if present
                keys = [k for k in ("pc", "raw", "opcode", "warp_id") if k in item]
                return {k: item[k] for k in keys} or "dict"
            return item
        except Exception:
            return repr(item)

    def snapshot(self) -> List[Any]:
        """Return a compact list of the queue contents (left=oldest)."""
        return [self._compact(x) for x in list(self.q)]

    def dump(self, *, cycle: Optional[int] = None, label: str = "IBUF") -> None:
        """
        Print a single-line summary of the buffer state.
        Example: ibuf.dump(cycle=sm.global_cycle)
        """
        tag = f"[C{cycle}]" if cycle is not None else ""
        snap = self.snapshot()
        print(f"{tag} {label}:{self.name} depth={len(self.q)}/{self.q.maxlen} -> {snap}")

    # (optional niceties)
    def __len__(self) -> int:
        return len(self.q)

    def clear(self) -> None:
        self.q.clear()

class EndStage(PipelineStage):
    def __init__(self, parent_core, accept_after_cycle=10):
        super().__init__("EndStage", parent_core)
        self.inst_queue = []
        self.accept_after_cycle = accept_after_cycle
        # Mark input as NOT ready initially
        if self.inputs:
            self.inputs[0].ready = False

        alu_to_fpu = StageInterface("if_ALU_FPU", latency=1)
        fpu_to_alu = StageInterface("if_FPU_ALU", latency=1)
                

    def load_instructions(self, instructions):
        self.inst_queue.extend(instructions)

    def process(self, inst):
        # Control when stage becomes ready to accept instructions
        if self.cycle_count >= self.accept_after_cycle:
            if self.inputs:
                self.inputs[0].ready = True
        
        if inst:
            print(f"PASSTHROUGH: Executing instruction: {inst}\n")

            return inst
        return None
    
# class YourStage(PipelineStage):
#     def __init__(self, parent_core):
#          super().__init__("YourStage", parent_core) 
#          # this line initializes your class with the variables from the Pipeline stage class

#     def process(self, inst):
#         "Populate this with whatever process you want for your stage."
#         "Inst is the dictionary of inputs you expect into the stage at any time"
    
#         pass

#     def extraFunctions(self, args):
#         "Feel free to define extra functions as needed to use internally."
#         "refer with self.<functin_name>"

#     def cycleMods(self):
#         ""

# =========================================================
#  SM Wrapper
# =========================================================

class SM_Test(SM):
    def __init__(self):
        fetch = FetchStage(self)
        icache = ICacheStage(self, miss_latency=3)
        decode = DecodeStage(self)
        ibuffer = IBufferStage(self)
        end = PipelineStage("EndStage", "SM_Test")

        stage_defs = {
            "fetch": fetch,
            "icache": icache,
            "decode": decode,
            "ibuffer": ibuffer,
            "end": end
        }

        connections = [
            ("fetch", "icache"),
            ("icache", "decode"),
            ("decode", "ibuffer"),
            ("ibuffer", "end")
        ]

        feedbacks = [
            ("icache", "fetch"),
            ("icache", "decode"),
        ]

        logger = LoggerBase(name="SM_Test")
        perf = PerfCounterBase()
        super().__init__(stage_defs=stage_defs, connections=connections, feedbacks=feedbacks,
                         logger=logger, perf=perf)

        self.user_if = StageInterface("if_user_fetch", latency=0)
        self.stages["fetch"].add_input(self.user_if)
        self.interfaces.append(self.user_if)

    def push_instruction(self, req: dict, at_iface="if_user_fetch"):
        iface = self.get_interface(at_iface)
        if iface and iface.can_accept():
            iface.send(req)
            print(f"[SM] Injected → {at_iface}: {req}")
            return True
        return False

    def print_pipeline_state(self):
        print(f"\n=== Cycle {self.global_cycle} ===")

        for nm in ["fetch", "icache", "decode", "ibuffer"]:
            st = self.stages[nm]
            state = st.debug_state()
            inst = state.get("current_inst", None)
            pc_display = "-"
            if inst is None:
                pc_display = "-"
            elif isinstance(inst, int):
                # already a numeric PC
                pc_display = f"0x{inst:x}"
            elif isinstance(inst, str):
                # could be 'pc=0x100' or just 'active'
                if "0x" in inst:
                    pc_display = inst
                else:
                    pc_display = inst
            elif isinstance(inst, dict):
                # structured dict form
                if "pc" in inst:
                    pc_display = f"0x{inst['pc']:x}"
                elif "decoded_fields" in inst:
                    # try to get nested orig_inst.pc
                    orig = inst["decoded_fields"].get("orig_inst", {})
                    if isinstance(orig, dict) and "pc" in orig:
                        pc_display = f"0x{orig['pc']:x}"
                    else:
                        pc_display = str(inst["decoded_fields"])
                else:
                    pc_display = str(inst)
            else:
                pc_display = str(inst)
            print(f"{nm:>8}: {pc_display}")
        self.stages['ibuffer'].dump()
        print("\n")    



# =========================================================
#  Test Harness
# =========================================================

if __name__ == "__main__":
    sm = SM_Test()

    fetch_reqs = [
        {"pc": 0x100, "warp_id": 0},  # hit
        {"pc": 0x104, "warp_id": 0},  # hit
        {"pc": 0x120, "warp_id": 0},  # miss
        {"pc": 0x10C, "warp_id": 0}  # hit
    ]

    req_idx = 0
    total_cycles = len(fetch_reqs) + 15

    for _ in range(total_cycles):
        if req_idx < len(fetch_reqs):
            ok = sm.push_instruction(fetch_reqs[req_idx])
            if ok:
                req_idx += 1

        sm.cycle()
        sm.print_pipeline_state()
