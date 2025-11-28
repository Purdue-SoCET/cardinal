"""Unit test bench: This testbench sends a memory request to every bank in the cache. Initially the cache is empty and
every memory request misses. It fetches from main memory that has been prepopulated with 0x01010101 at every address.
Every missed request has a miss penalty of 200 cycles.
"""

import sys
from pathlib import Path

# 1) Add the directory that contains `gpu_sim/` to sys.path
# File: /home/.../gpu/gpu_sim/cyclesim/tests/dcache/readFromAllBanks.py
# parents:
#   0 -> dcache
#   1 -> tests
#   2 -> cyclesim
#   3 -> gpu_sim
#   4 -> gpu   <-- this directory contains the `gpu_sim` package
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

# 2) Now do the package import
import gpu_sim.cyclesim.src.mem.dcache as cache_module  # ✅ now Python can see gpu_sim

from collections import deque


# --- Output File ---
OUTPUT_FILENAME = "readFromAllBanks_log.txt" # Renamed output file

# --- Mock Main Memory ---
mock_memory: dict[int, bytearray] = {}

# --- Test Setup ---
MAX_CYCLES = 300 # Wait (200) + Bank Count (~32) + Pipeline Delays
next_uuid = 0

# Use the config from the cache module
cache_config = cache_module.cache_config
BLOCK_SIZE = cache_config['block_size']

# --- Create Cache Instance ---
cache = cache_module.L1DataCache(cache_config, mock_memory)

# --- Define Test Requests ---
miss_requests = deque() # Only need one set of requests
num_banks_to_test = cache.num_banks
all_requests_details: dict[int, cache_module.MemoryRequest] = {} # Store details by UUID
request_states: dict[int, str] = {} # Store status strings by UUID

print(f"Generating {num_banks_to_test} miss requests, one per bank...")

for i in range(num_banks_to_test):
    # Construct an address designed to hit bank 'i'
    base_addr = 0x10000000
    addr = base_addr + (i * BLOCK_SIZE) + (i * cache_config['cache_size'])

    # Parse to get the block address
    tag, bank_idx, set_idx, block_addr, offset = cache._parse_address(addr)

    # --- Populate Mock Memory ---
    memory_data = bytearray([1] * BLOCK_SIZE) # Fill with 1s
    mock_memory[block_addr] = memory_data

    # Create the miss request
    req_miss = cache_module.MemoryRequest(
        uuid=next_uuid, warp_id=0, thread_id=i, address=addr, ldMode=False
    )
    miss_requests.append(req_miss)
    all_requests_details[next_uuid] = req_miss
    request_states[next_uuid] = "Generated (Miss)"
    print(f"  Generated Miss Req UUID {next_uuid}: Addr 0x{addr:X} -> Bank {bank_idx}, Set {set_idx}, Block 0x{block_addr:X}")
    next_uuid += 1

total_requests_to_issue = len(miss_requests)
print(f"Total requests generated: {total_requests_to_issue}")
print(f"Mock memory populated with {len(mock_memory)} blocks.")

# --- Simulation Variables ---
global_cycle_counter = 0
issued_uuids = set()
completed_uuids = set()

# --- Main Simulation Loop ---
print(f"\n--- Starting Simple Bank Miss Simulation (Outputting to {OUTPUT_FILENAME}) ---")

with open(OUTPUT_FILENAME, 'w') as log_file:
    original_stdout = sys.stdout
    sys.stdout = log_file
    sys.stderr = log_file

    # --- Phase 1: Issue All Requests ---
    print("\n--- Phase 1: Issuing All Requests ---")
    num_issued_this_phase = 0
    while miss_requests:
         new_request = miss_requests.popleft()
         print(f"[LSU Cycle {global_cycle_counter}] Issuing request UUID {new_request.uuid} for Addr 0x{new_request.address:X}")
         cache.accept_request(new_request)
         issued_uuids.add(new_request.uuid)
         request_states[new_request.uuid] = "Issued to Cache Queue"
         num_issued_this_phase +=1
    print(f"[LSU Cycle {global_cycle_counter}] Issued {num_issued_this_phase} requests.")


    # --- Phase 2: Run until Misses Complete ---
    print(f"\n--- Phase 2: Running until {total_requests_to_issue} requests complete ---")
    start_run_cycle = global_cycle_counter

    # Run until all issued requests are completed
    while (len(completed_uuids) < total_requests_to_issue) and global_cycle_counter < MAX_CYCLES:
        print(f"\n--- Cycle {global_cycle_counter} ---")
        # Check Cache Outputs
        while cache.response_queue:
            response = cache.response_queue.popleft(); uuid = response.get("uuid"); data = response.get("data")
            if uuid is not None and uuid in issued_uuids:
                if uuid not in completed_uuids: # Process only once
                    data_str = f'0x{data:X}' if isinstance(data, int) else 'N/A'; request_states[uuid] = f"Completed (Data: {data_str})"; completed_uuids.add(uuid)
                    print(f"[LSU] Received data response for UUID {uuid}, Data: {data_str}")
                    # --- Verification ---
                    original_req = all_requests_details.get(uuid)
                    if original_req and not original_req.ldMode:
                         _, _, _, block_addr, offset = cache._parse_address(original_req.address)
                         word_offset = offset & ~0x3
                         expected_word = int.from_bytes(bytes([1, 1, 1, 1]), byteorder='little')
                         if data != expected_word: print(f"  [VERIFICATION FAILED] UUID {uuid}: Expected 0x{expected_word:X}, Received 0x{data:X}")
            else: print(f"[LSU] WARNING: Received response for unknown UUID {uuid}")

        while cache.miss_notification_queue:
            miss_info_req = cache.miss_notification_queue.popleft(); uuid = miss_info_req.uuid
            if uuid in request_states and not request_states[uuid].startswith("Completed"): request_states[uuid] = "Miss Notified (Waiting)"
            print(f"[LSU] Received MISS notification for UUID {uuid} (Warp {miss_info_req.warp_id}, Thread {miss_info_req.thread_id})")

        # Tick Cache
        cache.cycle()

        # Update Request States
        active_miss_uuids = set()
        queued_miss_uuids = set()
        for bank_idx in range(cache.num_banks):
            if cache.active_misses[bank_idx]:
                 active_miss_uuids.update(cache.active_misses[bank_idx].requestor_uuids)
            for entry in cache.mshr_queues[bank_idx]:
                 queued_miss_uuids.update(entry.requestor_uuids)

        for uuid in issued_uuids:
             if uuid in completed_uuids: continue
             current_state = request_states[uuid]
             if uuid in active_miss_uuids and current_state != "Active Miss Fetch":
                  request_states[uuid] = "Active Miss Fetch"
             elif uuid in queued_miss_uuids and current_state != "Waiting in MSHR Queue":
                  request_states[uuid] = "Waiting in MSHR Queue"
             elif uuid not in active_miss_uuids and uuid not in queued_miss_uuids and "Issued to Cache Queue" in current_state:
                  request_states[uuid] = "Waiting in Request Queue (Stalled?)"


        # Print Status
        print("  Request Status:"); status_counts = {};
        for _, status in request_states.items(): status_counts[status] = status_counts.get(status, 0) + 1
        for status, count in sorted(status_counts.items()): print(f"    - {status}: {count}")
        # Advance Time
        global_cycle_counter += 1

    # --- Simulation Finished ---
    print(f"\n--- Simulation Finished ---")
    print(f"Total cycles taken: {global_cycle_counter}")
    print(f"Total requests issued: {len(issued_uuids)}")
    print(f"Total requests completed: {len(completed_uuids)}")

    if global_cycle_counter >= MAX_CYCLES: print("Warning: Simulation hit MAX_CYCLES limit.")
    if len(completed_uuids) < total_requests_to_issue:
        print(f"Warning: Not all requests completed ({len(completed_uuids)}/{total_requests_to_issue}).")
        print("Remaining states:")
        remaining_counts = {}
        for uuid, status in request_states.items():
             if uuid not in completed_uuids:
                  remaining_counts[status] = remaining_counts.get(status, 0) + 1
        for status, count in sorted(remaining_counts.items()): print(f"    - {status}: {count}")


# Restore stdout and stderr
sys.stdout = original_stdout
sys.stderr = original_stdout
print(f"\nSimple bank miss simulation complete. Log written to {OUTPUT_FILENAME}")
