import yaml
from bitstring import Bits
from simulator.sm import SMConfig


def load_yaml(path):
    with open(path, "r") as f:
        return yaml.safe_load(f)

from pathlib import Path

def load_sm_config(path):

    cfg = load_yaml(path)

    sm = cfg["sm"]
    mem = cfg["memory"]
    kern = cfg["kernel"]
    icache = cfg["icache"]
    prog = cfg["program"]

    return SMConfig(
        sm_no=sm["sm_no"],

        test_file=Path(prog["file"]),
        test_file_type=prog["format"],

        num_warps=sm["num_warps"],
        num_preds=sm["num_preds"],
        threads_per_warp=sm["threads_per_warp"],

        mem_start_pc=mem["start_pc"],
        mem_lat=mem["latency"],
        mem_mod=None,
        memc_policy=mem["policy"],

        kern_init=kern,
        icache_config=icache,

        fu_config=None,
        wb_config=None,
        rf_config=None,
        prf_rf_config=None,

        custom_regfile_init=None,
        custom_prf_init=None,

        stage_order=None
    )


def initialize_register_file(regfile, path, quiet: bool = False):

    cfg = load_yaml(path)

    warp = cfg.get("warp_id", 0)
    threads = regfile.threads_per_warp

    if not quiet:
        print("\n===== Register File Initialization =====")
        print(f"Warp: {warp}")
        print(f"Threads per warp: {threads}\n")

    for reg_name, reg_data in cfg["registers"].items():

        reg_num = int(reg_name[1:])

        if not quiet:
            print(f"Initializing {reg_name}")

        # --------------------------------------------------
        # Read current register values so unspecified threads remain unchanged
        # --------------------------------------------------
        values = []

        for t in range(threads):

            val = regfile.read_thread_gran(
                warp_id=warp,
                src_operand=Bits(uint=reg_num, length=32),
                thread_id=t
            )

            values.append(val.int if val else 0)

        # --------------------------------------------------
        # CASE 1: explicit list
        # --------------------------------------------------
        if "values" in reg_data and isinstance(reg_data["values"], list):

            vlist = reg_data["values"]

            if len(vlist) == 1:
                # broadcast
                for t in range(threads):
                    values[t] = vlist[0]
                    if not quiet:
                        print(f"  thread {t:02d} -> {vlist[0]}")
            else:
                for t, val in enumerate(vlist):
                    if t >= threads:
                        break
                    values[t] = val
                    if not quiet:
                        print(f"  thread {t:02d} -> {val}")

        # --------------------------------------------------
        # CASE 2: pattern generation
        # --------------------------------------------------
        elif "values" in reg_data and isinstance(reg_data["values"], dict):

            vcfg = reg_data["values"]

            start = vcfg["start"]
            step = vcfg["step"]
            count = vcfg["count"]

            for i in range(count):

                if i >= threads:
                    break

                val = start + step * i
                values[i] = val

                if not quiet:
                    print(f"  thread {i:02d} -> {val}")

        # --------------------------------------------------
        # CASE 3: ranges
        # --------------------------------------------------
        if "ranges" in reg_data:

            for r in reg_data["ranges"]:

                start = r["start"]
                end = r["end"]
                val = r["value"]

                if end >= threads:
                    raise ValueError(
                        f"Thread index {end} exceeds warp size {threads}"
                    )

                for t in range(start, end + 1):

                    values[t] = val

                    if not quiet:
                        print(f"  thread {t:02d} -> {val}")

        # --------------------------------------------------
        # CASE 4: individual thread overrides
        # --------------------------------------------------
        if "threads" in reg_data:

            for t, val in reg_data["threads"].items():

                t = int(t)

                if t >= threads:
                    raise ValueError(
                        f"Thread index {t} exceeds warp size {threads}"
                    )

                values[t] = val

                if not quiet:
                    print(f"  thread {t:02d} -> {val}")

        # --------------------------------------------------
        # Write results back to register file
        # --------------------------------------------------
        data = [Bits(int=v, length=32) for v in values]

        regfile.write_warp_gran(
            warp_id=warp,
            dest_operand=Bits(uint=reg_num, length=32),
            data=data
        )

        if not quiet:
            print("  ✓ written\n")

    if not quiet:
        print("===== Register File Initialization Complete =====\n")
     
from bitstring import Bits


def initialize_memory(mem, path):

    cfg = load_yaml(path)

    print("\n===== Memory Initialization =====")
    print(f"Instruction start PC: 0x{mem.start_pc:08X}\n")

    for entry in cfg["memory"]:

        addr_val = entry["address"]
        val_val = entry["value"]

        # Support both YAML ints and strings like "0x1000"
        addr = int(addr_val, 0) if isinstance(addr_val, str) else int(addr_val)
        val  = int(val_val, 0) if isinstance(val_val, str) else int(val_val)

        # --------------------------------------------------
        # Check if writing into instruction memory
        # --------------------------------------------------
        if addr >= mem.start_pc:

            print("\n⚠ WARNING: You are modifying instruction memory!")
            print(f"Address: 0x{addr:08X}")
            print(f"Value  : {mem.read(addr)} -> 0x{val:08X}")
            print(f"Instruction region begins at 0x{mem.start_pc:08X}")

            confirm = input("Press ENTER to continue modifying instruction memory (Ctrl+C to abort)")

        # --------------------------------------------------
        # Perform memory write (aligned with Mem.write)
        # --------------------------------------------------
        data_bits = Bits(uintle=val, length=32)
        
        mem.write(addr, data_bits, 4)

        print(f"  Wrote 0x{val:08X} -> 0x{addr:08X}")

    print("\n===== Memory Initialization Complete =====\n")