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
OUTPUT_FILENAME = "cache_hit_test_log.txt"

# --- Mock Main Memory ---
mock_memory: dict[int, bytearray] = {}

# --- Test Setup ---
# Increase total cycles to accommodate the longer wait
MAX_CYCLES = 300 # Wait (240) + Hit Latency (~4) + Pipeline Delays
next_uuid = 0

# Use the config from the cache module
cache_config = cache_module.cache_config
BLOCK_SIZE = cache_config['block_size']

# --- Create Cache Instance ---
cache = cache_module.L1DataCache(cache_config, mock_memory)

# --- Define Test Requests ---
priming_requests = deque() # First set (will miss)
hit_requests = deque()     # Second set (should hit)
num_banks_to_test = cache.num_banks
all_requests_details: dict[int, cache_module.MemoryRequest] = {} # Store details by UUID
request_states: dict[int, str] = {} # Store status strings by UUID
target_addresses = [] # Store addresses to request again

print(f"Generating {num_banks_to_test} priming requests (misses) and {num_banks_to_test} hit requests...")

for i in range(num_banks_to_test):
    # Construct an address designed to hit bank 'i'
    base_addr = 0x10000000
    addr = base_addr + (i * BLOCK_SIZE) + (i * cache_config['cache_size'])
    target_addresses.append(addr) # Remember address for the hit request

    # Parse to get the block address
    tag, bank_idx, set_idx, block_addr, offset = cache._parse_address(addr)

    # --- Populate Mock Memory ---
    memory_data = bytearray([1] * BLOCK_SIZE) # Fill with 1s
    mock_memory[block_addr] = memory_data

    # Create the priming (miss) request
    req_miss = cache_module.MemoryRequest(
        uuid=next_uuid, warp_id=0, thread_id=i, address=addr, ldMode=False
    )
    priming_requests.append(req_miss)
    all_requests_details[next_uuid] = req_miss
    request_states[next_uuid] = "Generated (Priming Miss)"
    print(f"  Generated Priming Req UUID {next_uuid}: Addr 0x{addr:X} -> Bank {bank_idx}, Set {set_idx}, Block 0x{block_addr:X}")
    next_uuid += 1

    # Create the corresponding hit request (issued later)
    req_hit = cache_module.MemoryRequest(
        uuid=next_uuid, warp_id=1, thread_id=i, address=addr, ldMode=False # Different warp ID
    )
    hit_requests.append(req_hit)
    all_requests_details[next_uuid] = req_hit
    request_states[next_uuid] = "Generated (Hit)"
    next_uuid += 1


total_priming_requests = len(priming_requests)
total_hit_requests = len(hit_requests)
print(f"Total priming requests generated: {total_priming_requests}")
print(f"Total hit requests generated: {total_hit_requests}")
print(f"Mock memory populated with {len(mock_memory)} blocks.")

# --- Simulation Variables ---
global_cycle_counter = 0
issued_uuids = set()
completed_uuids = set()
# --- Increase Wait Time ---
cycles_to_wait_for_misses = 234 # Wait longer

# --- Main Simulation Loop ---
print(f"\n--- Starting Cache Hit Simulation (Outputting to {OUTPUT_FILENAME}) ---")

with open(OUTPUT_FILENAME, 'w') as log_file:
    original_stdout = sys.stdout
    sys.stdout = log_file
    sys.stderr = log_file

    # --- Phase 1: Issue Priming Requests ---
    print("\n--- Phase 1: Issuing Priming Requests ---")
    num_issued_this_phase = 0
    while priming_requests:
         new_request = priming_requests.popleft()
         print(f"[LSU Cycle {global_cycle_counter}] Issuing priming request UUID {new_request.uuid} for Addr 0x{new_request.address:X}")
         cache.accept_request(new_request)
         issued_uuids.add(new_request.uuid)
         request_states[new_request.uuid] = "Issued to Cache Queue (Priming Miss)"
         num_issued_this_phase +=1
    print(f"[LSU Cycle {global_cycle_counter}] Issued {num_issued_this_phase} priming requests.")

    # --- Phase 2: Wait for Priming Misses to Fill Cache ---
    print(f"\n--- Phase 2: Waiting {cycles_to_wait_for_misses} cycles for misses to complete ---")
    start_wait_cycle = global_cycle_counter
    while global_cycle_counter < start_wait_cycle + cycles_to_wait_for_misses:
        print(f"\n--- Cycle {global_cycle_counter} ---")
        # Check Cache Outputs
        while cache.response_queue:
            response = cache.response_queue.popleft(); uuid = response.get("uuid"); data = response.get("data")
            if uuid is not None and uuid in issued_uuids:
                if uuid not in completed_uuids: # Process only once
                    data_str = f'0x{data:X}' if isinstance(data, int) else 'N/A'; request_states[uuid] = f"Completed (Data: {data_str})"; completed_uuids.add(uuid)
                    print(f"[LSU] Received data response for UUID {uuid}, Data: {data_str}")
            else: print(f"[LSU] WARNING: Received response for unknown UUID {uuid}")
        while cache.miss_notification_queue:
            miss_info_req = cache.miss_notification_queue.popleft(); uuid = miss_info_req.uuid
            if uuid in request_states and not request_states[uuid].startswith("Completed"): request_states[uuid] = "Miss Notified (Waiting)"
            print(f"[LSU] Received MISS notification for UUID {uuid} (Warp {miss_info_req.warp_id}, Thread {miss_info_req.thread_id})")
        # Tick Cache
        cache.cycle()
        # Print Status
        print("  Request Status:"); status_counts = {};
        for _, status in request_states.items(): status_counts[status] = status_counts.get(status, 0) + 1
        for status, count in sorted(status_counts.items()): print(f"    - {status}: {count}")
        # Advance Time
        global_cycle_counter += 1

    print(f"\n--- Finished Waiting Phase at Cycle {global_cycle_counter} ---")
    priming_completed_count = 0
    for uuid in all_requests_details:
        if uuid < total_priming_requests and uuid in completed_uuids:
            priming_completed_count += 1
    print(f"Priming requests completed: {priming_completed_count}/{total_priming_requests}")
    if priming_completed_count < total_priming_requests:
         print("WARNING: Not all priming misses completed before issuing hits!")


    # --- Phase 3: Issue Hit Requests ---
    print("\n--- Phase 3: Issuing Hit Requests ---")
    hit_uuids_issued = set()
    num_issued_this_phase = 0
    while hit_requests:
        new_request = hit_requests.popleft()
        print(f"[LSU Cycle {global_cycle_counter}] Issuing hit request UUID {new_request.uuid} for Addr 0x{new_request.address:X}")
        cache.accept_request(new_request)
        issued_uuids.add(new_request.uuid)
        hit_uuids_issued.add(new_request.uuid)
        request_states[new_request.uuid] = "Issued to Cache Queue (Hit)"
        num_issued_this_phase += 1
    print(f"[LSU Cycle {global_cycle_counter}] Issued {num_issued_this_phase} hit requests.")

    # --- Phase 4: Run until Hit Requests Complete ---
    print("\n--- Phase 4: Running until Hit Requests Complete ---")
    hit_requests_completed_count = 0
    start_hit_cycle = global_cycle_counter
    # Count how many of the *hit* UUIDs were already completed (should be 0)
    for uuid in hit_uuids_issued:
        if uuid in completed_uuids:
            hit_requests_completed_count += 1

    while (hit_requests_completed_count < total_hit_requests) and global_cycle_counter < MAX_CYCLES:
        print(f"\n--- Cycle {global_cycle_counter} ---")
        # Check Cache Outputs
        while cache.response_queue:
            response = cache.response_queue.popleft(); uuid = response.get("uuid"); data = response.get("data")
            if uuid is not None and uuid in issued_uuids:
                if uuid not in completed_uuids: # Only process if not already counted
                     data_str = f'0x{data:X}' if isinstance(data, int) else 'N/A'; request_states[uuid] = f"Completed (Data: {data_str})"; completed_uuids.add(uuid)
                     print(f"[LSU] Received data response for UUID {uuid}, Data: {data_str}")
                     if uuid in hit_uuids_issued: # Check if this is one of the hits we are waiting for
                          hit_requests_completed_count += 1
                          # --- Verification ---
                          original_req = all_requests_details.get(uuid)
                          if original_req and not original_req.ldMode:
                               _, _, _, block_addr, offset = cache._parse_address(original_req.address)
                               word_offset = offset & ~0x3
                               expected_word = int.from_bytes(bytes([1, 1, 1, 1]), byteorder='little')
                               if data != expected_word: print(f"  [VERIFICATION FAILED] UUID {uuid}: Expected 0x{expected_word:X}, Received 0x{data:X}")
                # else: print(f"  [Verification OK] UUID {uuid}")
            else: print(f"[LSU] WARNING: Received response for unknown UUID {uuid}")

        while cache.miss_notification_queue: # Should not receive miss notifications in hit phase
            miss_info_req = cache.miss_notification_queue.popleft(); uuid = miss_info_req.uuid
            if uuid in hit_uuids_issued: # Check if it's for one of the expected hits
                 print(f"[LSU] ERROR: Received unexpected MISS notification for hit request UUID {uuid}")
                 request_states[uuid] = "ERROR - Missed on Hit Phase"
            else: # Notification for priming phase (maybe delayed?)
                 if uuid in request_states and not request_states[uuid].startswith("Completed"): request_states[uuid] = "Miss Notified (Delayed?)"
                 print(f"[LSU] Received MISS notification for UUID {uuid} (Warp {miss_info_req.warp_id}, Thread {miss_info_req.thread_id})")

        # Tick Cache
        cache.cycle()
        # Print Status
        print("  Request Status:"); status_counts = {};
        for uuid, status in request_states.items(): status_counts[status] = status_counts.get(status, 0) + 1
        for status, count in sorted(status_counts.items()): print(f"    - {status}: {count}")
        # Advance Time
        global_cycle_counter += 1

    # --- Simulation Finished ---
    print(f"\n--- Simulation Finished ---")
    print(f"Total cycles taken: {global_cycle_counter}")
    print(f"Cycles for hit phase (approx): {global_cycle_counter - start_hit_cycle}")
    print(f"Total requests issued: {len(issued_uuids)}")
    print(f"Total requests completed: {len(completed_uuids)}")
    print(f"Hit requests completed: {hit_requests_completed_count}/{total_hit_requests}")

    if global_cycle_counter >= MAX_CYCLES: print("Warning: Simulation hit MAX_CYCLES limit.")
    if hit_requests_completed_count < total_hit_requests:
        print(f"Warning: Not all hit requests completed ({hit_requests_completed_count}/{total_hit_requests}).")
        print("Remaining hit request states:")
        remaining_counts = {}
        for uuid in hit_uuids_issued:
             if uuid not in completed_uuids:
                  status = request_states.get(uuid, "Unknown")
                  remaining_counts[status] = remaining_counts.get(status, 0) + 1
        for status, count in sorted(remaining_counts.items()): print(f"    - {status}: {count}")


# Restore stdout and stderr
sys.stdout = original_stdout
sys.stderr = original_stdout
print(f"\nCache hit simulation complete. Log written to {OUTPUT_FILENAME}")

