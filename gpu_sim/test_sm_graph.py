from base_class import StageInterface, PipelineStage, SM, LoggerBase, PerfCounterBase, make_raw


# =========================================================
#  FETCH → ICACHE → DECODE pipeline with iCache miss latency
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
                out = self.pending_req
                self.pending_req = None
                return out
            elif ihit is False:
                print(f"[Fetch] Still waiting on iCache miss at pc=0x{self.pending_req['pc']:x}.")
                return None
            else:
                return None

        # Case 2: no stall, new fetch request incoming
        if inst is None:
            return None

        print(f"[Fetch] Sending fetch req → ICache: pc=0x{inst['pc']:x}")
        self.waiting_for_hit = True
        self.pending_req = inst
        return inst


class ICacheStage(PipelineStage):
    def __init__(self, parent_core, miss_latency=3):
        super().__init__("ICache", parent_core)
        self.icache_lut = {
            0x100: make_raw(0x00, rd=1, rs1=2, mid6=3),  # add
            0x104: make_raw(0x10, rd=5, rs1=6, mid6=0),  # addi
            0x108: make_raw(0x20, rd=2, rs1=3, mid6=4),  # lw
            0x10C: make_raw(0x30, rd=2, rs1=3, mid6=4),  # sw
            0x110: make_raw(0x40, rd=0, rs1=1, mid6=2, pred=1, packet_start=True),  # beq
            0x114: make_raw(0x7F, rd=0, rs1=0, mid6=0),  # halt
        }
        self.miss_latency = miss_latency
        self.active_misses = {}  # pc -> remaining cycles

    def process(self, inst):
        if not inst:
            return None

        pc = inst["pc"]
        warp = inst["warp_id"]

        # Simulate cache lookup
        ihit = pc in self.icache_lut
        raw = self.icache_lut.get(pc, 0)

        # Handle misses (simulate fetch delay)
        if not ihit:
            if pc not in self.active_misses:
                self.active_misses[pc] = self.miss_latency
                print(f"[ICache] MISS on pc=0x{pc:x} → starting memory fetch ({self.miss_latency} cycles)")
            else:
                self.active_misses[pc] -= 1
                if self.active_misses[pc] <= 0:
                    # Pretend it was fetched from memory
                    self.icache_lut[pc] = make_raw(0x20, rd=9, rs1=9, mid6=9)  # dummy data
                    del self.active_misses[pc]
                    ihit = True
                    raw = self.icache_lut[pc]
                    print(f"[ICache] MISS resolved for pc=0x{pc:x}")

        # Feedback to Fetch + Decode
        for dst in ("fetch", "decode"):
            if dst in self.feedback_links:
                self.feedback_links[dst].send({"ihit": ihit, "pc": pc, "warp_id": warp})

        print(f"[ICache] pc=0x{pc:x}, ihit={ihit}")
        return {"pc": pc, "warp_id": warp, "raw": raw, "ihit": ihit}


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
        print(decoded)
        print(f"[Decode] Decoding pc=0x{pc:x}, raw=0x{inst['raw']:08x}")
        return {"decoded": True, "decoded_fields": {"orig_inst": inst}}


# =========================================================
#  SM Wrapper
# =========================================================

class SM_Test(SM):
    def __init__(self):
        fetch = FetchStage(self)
        icache = ICacheStage(self, miss_latency=3)
        decode = DecodeStage(self)

        stage_defs = {
            "fetch": fetch,
            "icache": icache,
            "decode": decode,
        }

        connections = [
            ("fetch", "icache"),
            ("icache", "decode"),
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

        for nm in ["fetch", "icache", "decode"]:
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
        print("\n")    



# =========================================================
#  Test Harness
# =========================================================

if __name__ == "__main__":
    sm = SM_Test()

    fetch_reqs = [
        # {"pc": 0x100, "warp_id": 0},  # hit
        # {"pc": 0x104, "warp_id": 0},  # hit
        # {"pc": 0x120, "warp_id": 0},  # miss
        # {"pc": 0x108, "warp_id": 0},  # hit
        
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
