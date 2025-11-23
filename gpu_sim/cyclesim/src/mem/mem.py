#!/usr/bin/env python3
import sys
import os
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple
from collections import deque
from base import ForwardingIF, LatchIF, Stage, Addr, Instruction, MemRequest, dCacheFrame, MSHREntry
from pathlib import Path
import atexit
from bitstring import Bits

class MemStage(Stage):
    """Memory controller functional unit using Mem() backend."""

    def __init__(
        self,
        name: str,
        behind_latch: Optional[LatchIF],
        ahead_latch: Optional[LatchIF],
        mem_backend,                 # <-- existing Mem class instance
        latency: int = 5,
    ):
        super().__init__(name=name, behind_latch=behind_latch, ahead_latch=ahead_latch)
        self.mem_backend = mem_backend
        self.latency = latency
        self.inflight: list[MemRequest] = []

    def compute(self, input_data: Optional[Any] = None):
        # Progress all inflight requests
        completed = []
        for req in self.inflight:
            req.remaining -= 1
            if req.remaining <= 0:
                if (getattr(req, 'rw_mode', 'read') == 'write'):    # Write logic
                    if req.data is None:
                        print(f"[{self.name}] Error: Write request with no data @0x{req.addr:X}")
                        completed.append(req)
                    else:
                        data_bytes = bytearray()
                        for word in req.data:
                            data_bytes.extend(word.to_bytes(4, 'little'))
                        data_bits = Bits(bytes=data_bytes)

                        # Perform the write
                        self.mem_backend.write(req.addr, data_bits, len(data_bytes))
                        if self.ahead_latch.ready_for_push():
                            self.ahead_latch.push({
                                "uuid": None,
                                "data": "WRITE_DONE",
                                "warp": None
                            })
                            completed.append(req)

                else:   # Read logic
                    data = self.mem_backend.read(req.addr, req.size)
                    if self.ahead_latch.ready_for_push():
                        self.ahead_latch.push({
                            "uuid": req.uuid,
                            "data": data,
                            "warp": req.warp_id
                        })
                        print(f"[{self.name}] Completed read @0x{req.addr:X}")
                        completed.append(req)

        for c in completed:
            self.inflight.remove(c)

        # --- Accept new requests ---
        if self.behind_latch and self.behind_latch.valid:
            req_info = self.behind_latch.pop()
            mem_req = MemRequest(
                addr=req_info["addr"],
                size=req_info.get("size", 4),
                uuid=req_info.get("uuid", 0),
                warp_id=req_info.get("warp", 0),
                pc = req_info.get("pc", 0),
                remaining=self.latency,
                data = req_info.get("data", None),
                rw_mode = req_info.get("rw_mode", "read")
            )
            self.inflight.append(mem_req)
            print(f"[{self.name}] Accepted mem req @0x{mem_req.addr:X} lat={self.latency}")


# Memory.py — Fully Patched for ICache + MemStage correctness
class Mem:
    def __init__(self, start_pc: int, input_file: str, fmt: str = "bin", block_size=32):
        """
        Simple byte-addressable memory model.
        ICache will request memory using block addresses (block index),
        so this class converts block → byte address automatically.
        """
        self.memory: dict[int, int] = {}
        self.format = fmt
        self.block_size = block_size       # *** REQUIRED FIX ***
        self.start_pc = start_pc

        p = Path(input_file)
        if not p.exists():
            raise FileNotFoundError(f"Program file not found: {p}")

        addr = start_pc
        endianness = "little"

        with p.open("r", encoding="utf-8") as f:
            for line_no, raw in enumerate(f, start=1):
                # Remove comments
                for marker in ("//", "#"):
                    i = raw.find(marker)
                    if i != -1:
                        raw = raw[:i]

                bits = raw.strip().replace("_", "")
                if not bits:
                    continue

                if self.format == "hex":
                    if len(bits) != 8:
                        raise ValueError(f"Line {line_no}: expected 8 hex chars, got {bits!r}")
                    word = int(bits, 16)
                elif self.format == "bin":
                    if len(bits) != 32:
                        raise ValueError(f"Line {line_no}: expected 32 bits, got {bits!r}")
                    word = int(bits, 2)
                else:
                    raise ValueError("Unknown format type (use 'hex' or 'bin')")

                # Split into bytes
                if endianness == "little":
                    b0 = (word >> 0) & 0xFF
                    b1 = (word >> 8) & 0xFF
                    b2 = (word >> 16) & 0xFF
                    b3 = (word >> 24) & 0xFF
                else:
                    b3 = (word >> 0) & 0xFF
                    b2 = (word >> 8) & 0xFF
                    b1 = (word >> 16) & 0xFF
                    b0 = (word >> 24) & 0xFF

                self.memory[addr + 0] = b0
                self.memory[addr + 1] = b1
                self.memory[addr + 2] = b2
                self.memory[addr + 3] = b3
                addr += 4

        atexit.register(self.dump_on_exit)

    # ------------------------------------------------------------
    # Corrected READ — supports block addresses from ICache
    # ------------------------------------------------------------
    def read(self, addr: int, size: int = 4) -> Bits:
        """
        Reads `size` bytes starting at `addr`.

        If addr < start_pc:
            treat addr as a BLOCK INDEX (ICache requests)
        else:
            treat addr as a raw byte address (normal memory reads)
        """

        # Convert block index → byte address
        if addr < self.start_pc:
            byte_addr = addr * self.block_size

            # Debug
            # print(f"[Mem] Treating addr={addr} as block index → byte_addr={hex(byte_addr)}")
        else:
            byte_addr = addr

        data_bytes = []
        for offs in range(size):
            val = self.memory.get(byte_addr + offs, 0)
            if val > 0xFF:
                shift = (offs % 4) * 8
                val = (val >> shift) & 0xFF
            data_bytes.append(val)

        return Bits(bytes=bytes(data_bytes))

    # ------------------------------------------------------------
    # Byte-level write
    # ------------------------------------------------------------
    def write(self, addr: int, data: Bits, bytes_t: int):

        if (addr < self.start_pc):
            byte_addr = addr * self.block_size
        else:
            byte_addr = addr

        data_bytes = data.tobytes()[:bytes_t]
        for i, byte in enumerate(data_bytes):
            self.memory[byte_addr + i] = byte

    # ------------------------------------------------------------
    # Dump on exit
    # ------------------------------------------------------------
    def dump_on_exit(self):
        try:
            self.dump("memsim.hex")
        except Exception:
            print("[Mem] dump failed")

    def dump(self, path="memsim.hex"):
        with open(path, "w", encoding="utf-8") as f:
            if not self.memory:
                return

            min_addr = min(self.memory.keys()) & ~0x3
            max_addr = max(self.memory.keys())

            for base in range(min_addr, max_addr + 1, 4):
                b0 = self.memory.get(base + 0, 0)
                b1 = self.memory.get(base + 1, 0)
                b2 = self.memory.get(base + 2, 0)
                b3 = self.memory.get(base + 3, 0)

                if (b0 | b1 | b2 | b3) == 0:
                    continue

                word = b0 | (b1 << 8) | (b2 << 16) | (b3 << 24)
                f.write(f"{base:#010x} {word:#010x}\n")