Cycle : 1
[MemController] Aging inflight requests: []
[MemController] After aging: []

[Scheduler] Issuing an instruction for warp group: 0, warp: 0, pc: 0x00000000, state: WarpState.READY
Cycle : 2
[MemController] Aging inflight requests: []
[MemController] After aging: []

[I$] Memrequest ACCEPTED by Memory
Cycle : 3
[MemController] Aging inflight requests: []
[MemController] After aging: []

[I$] waiting on memory
Cycle : 4
[MemController] Aging inflight requests: [(0, 4)]
[MemController] After aging: [(0, 3)]

[I$] waiting on memory
Cycle : 5
[MemController] Aging inflight requests: [(0, 3)]
[MemController] After aging: [(0, 2)]

[I$] waiting on memory
Cycle : 6
[MemController] Aging inflight requests: [(0, 2)]
[MemController] After aging: [(0, 1)]

[I$] waiting on memory
Cycle : 7
[MemController] Aging inflight requests: [(0, 1)]
[MemController] After aging: [(0, 0)]

[Memory] Returning data: 00000000 from base address: 00000000
[Scheduler] Issuing an instruction for warp group: 0, warp: 1, pc: 0x00000000, state: WarpState.READY
Cycle : 8
[Decode]: Received Raw Instruction Data: 00000000
[MemController] Aging inflight requests: []
[MemController] After aging: []

Cycle : 1
[MemController] Aging inflight requests: []
[MemController] After aging: []

[Scheduler] Issuing an instruction for warp group: 0, warp: 0, pc: 0x00000000, state: WarpState.READY
Cycle : 2
[MemController] Aging inflight requests: []
[MemController] After aging: []

[I$] Memrequest ACCEPTED by Memory
Cycle : 3
[MemController] Aging inflight requests: []
[MemController] After aging: []

[I$] waiting on memory
Cycle : 4
[MemController] Aging inflight requests: [(0, 2)]
[MemController] After aging: [(0, 1)]

[I$] waiting on memory
Cycle : 5
[MemController] Aging inflight requests: [(0, 1)]
[MemController] After aging: [(0, 0)]

[Memory] Returning data: 00000000 from base address: 00000000
[Scheduler] Issuing an instruction for warp group: 0, warp: 1, pc: 0x00000000, state: WarpState.READY
Cycle : 6
[Decode]: Received Raw Instruction Data: 00000000
[MemController] Aging inflight requests: []
[MemController] After aging: []

// correclty added two cycle delay difference as expected 