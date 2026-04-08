// egress_switch.sv
// 3-stage Clos network – egress switch (8 inputs × 4 thread outputs).
//
// Each middle switch input carries a flit whose dest_mask is already masked
// to only the 4 bits for this egress group.  The arbiter above guarantees
// all destinations are unique threads, so at most one flit targets any given
// thread output per cycle — no arbitration needed.
//
// For within-group multicast (one flit targeting multiple threads in this
// group), a single flit arrives from one middle switch and is fanned out to
// all targeted thread outputs simultaneously.
//
// Each thread output has its own pipeline register fed directly from the
// middle switch input that targets it.
//
// thread_rx_flit output: flit[38:0] (dest field stripped).

`timescale 1ns/1ps

import clos_pkg::*;

module egress_switch #(
  parameter int unsigned SWITCH_ID   = 0,
  parameter int unsigned BASE_THREAD = SWITCH_ID * THREADS_PER_EGRESS
) (
  input  logic clk,
  input  logic rst_n,

  // ---- middle-switch inputs (8 ports) --------------------------------------
  input  logic  mid_valid [NUM_MIDDLE],
  output logic  mid_ready [NUM_MIDDLE],
  input  flit_t mid_flit  [NUM_MIDDLE],

  // ---- thread outputs (4 ports) -------------------------------------------
  output logic                     thr_valid [THREADS_PER_EGRESS],
  input  logic                     thr_ready [THREADS_PER_EGRESS],
  output logic [THREAD_FLIT_W-1:0] thr_flit  [THREADS_PER_EGRESS]
);

  // ---------------------------------------------------------------------------
  // Per-thread output registers.
  // Each thread t is served by whichever middle switch input carries a flit
  // with dest_mask bit (BASE_THREAD + t) set.  At most one such input exists
  // per cycle (unique-destination guarantee).
  // ---------------------------------------------------------------------------
  logic  out_valid_q [THREADS_PER_EGRESS];
  flit_t out_flit_q  [THREADS_PER_EGRESS];

  // ---------------------------------------------------------------------------
  // Combinational: find the incoming flit (if any) targeting each thread.
  // ---------------------------------------------------------------------------
  logic  in_valid [THREADS_PER_EGRESS];
  flit_t in_flit  [THREADS_PER_EGRESS];

  always_comb begin
    for (int t = 0; t < THREADS_PER_EGRESS; t++) begin
      in_valid[t] = 1'b0;
      in_flit[t]  = '0;
      for (int m = 0; m < NUM_MIDDLE; m++) begin
        if (mid_valid[m] && mid_flit[m].dest_mask[BASE_THREAD + t]) begin
          in_valid[t] = 1'b1;
          in_flit[t]  = mid_flit[m];
        end
      end
    end
  end

  // ---------------------------------------------------------------------------
  // Registered outputs
  // ---------------------------------------------------------------------------
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      for (int t = 0; t < THREADS_PER_EGRESS; t++) begin
        out_valid_q[t] <= 1'b0;
        out_flit_q[t]  <= '0;
      end
    end else begin
      for (int t = 0; t < THREADS_PER_EGRESS; t++) begin
        if (!out_valid_q[t] || thr_ready[t]) begin
          out_valid_q[t] <= in_valid[t];
          if (in_valid[t])
            out_flit_q[t] <= in_flit[t];
        end
      end
    end
  end

  // ---------------------------------------------------------------------------
  // Thread output assignments — dest field stripped
  // ---------------------------------------------------------------------------
  always_comb begin
    for (int t = 0; t < THREADS_PER_EGRESS; t++) begin
      thr_valid[t] = out_valid_q[t];
      thr_flit[t]  = out_flit_q[t][THREAD_FLIT_W-1:0];
    end
  end

  // ---------------------------------------------------------------------------
  // Back-pressure to middle switches.
  // A middle switch input is ready when all thread outputs it targets are free.
  // ---------------------------------------------------------------------------
  always_comb begin
    for (int m = 0; m < NUM_MIDDLE; m++) begin
      automatic logic all_free = 1'b1;
      for (int t = 0; t < THREADS_PER_EGRESS; t++) begin
        if (mid_valid[m] && mid_flit[m].dest_mask[BASE_THREAD + t]) begin
          if (out_valid_q[t] && !thr_ready[t])
            all_free = 1'b0;
        end
      end
      mid_ready[m] = all_free;
    end
  end

endmodule : egress_switch
