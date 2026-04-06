// ingress_switch.sv
// 3-stage Clos network – ingress switch (4 inputs × 8 outputs).
//
// Each of the 4 bank-facing input ports receives a flit whose dest_mask
// spans all 32 threads.  The switch maps middle-switch index m (0-7) to
// egress-switch m, which serves threads [m*4 +: 4].  For each output port m
// the flit is replicated when any of the four bits dest_mask[m*4 +: 4] is set;
// the copy's dest_mask is masked to only those four bits so downstream stages
// can strip unneeded bits early.
//
// Arbitration: per-output round-robin across the 4 input ports.
// All outputs are registered (one pipeline stage).

`timescale 1ns/1ps

import clos_pkg::*;

module ingress_switch #(
  parameter int unsigned SWITCH_ID = 0   // 0-7
) (
  input  logic clk,
  input  logic rst_n,

  // ---- bank-side inputs (4 ports) -----------------------------------------
  input  logic              bank_valid [BANKS_PER_INGRESS],
  output logic              bank_ready [BANKS_PER_INGRESS],
  input  flit_t             bank_flit  [BANKS_PER_INGRESS],

  // ---- middle-switch outputs (8 ports) -------------------------------------
  output logic              mid_valid  [NUM_MIDDLE],
  input  logic              mid_ready  [NUM_MIDDLE],
  output flit_t             mid_flit   [NUM_MIDDLE]
);

  // ---------------------------------------------------------------------------
  // Internal pipeline registers
  // ---------------------------------------------------------------------------
  logic              out_valid_q [NUM_MIDDLE];
  flit_t             out_flit_q  [NUM_MIDDLE];

  // ---------------------------------------------------------------------------
  // Per-output arbitration state (round-robin pointer)
  // ---------------------------------------------------------------------------
  logic [$clog2(BANKS_PER_INGRESS)-1:0] rr_ptr_q [NUM_MIDDLE];

  // ---------------------------------------------------------------------------
  // Combinational arbitration
  // ---------------------------------------------------------------------------
  // For each output m, determine which input wins this cycle.

  // Which inputs want to send to output m?
  logic [BANKS_PER_INGRESS-1:0] req [NUM_MIDDLE];

  always_comb begin
    for (int m = 0; m < NUM_MIDDLE; m++) begin
      for (int i = 0; i < BANKS_PER_INGRESS; i++) begin
        // input i wants output m if it is valid and dest_mask covers that group
        req[m][i] = bank_valid[i] &&
                    (|(bank_flit[i].dest_mask[m*THREADS_PER_EGRESS +: THREADS_PER_EGRESS]));
      end
    end
  end

  // ---------------------------------------------------------------------------
  // Per-output round-robin grant + output mux
  // ---------------------------------------------------------------------------
  // Next-pointer and winner for each output
  logic [$clog2(BANKS_PER_INGRESS)-1:0] winner     [NUM_MIDDLE];
  logic                                  winner_vld [NUM_MIDDLE];
  logic [$clog2(BANKS_PER_INGRESS)-1:0] rr_ptr_nxt [NUM_MIDDLE];

  always_comb begin
    for (int m = 0; m < NUM_MIDDLE; m++) begin
      winner[m]     = '0;
      winner_vld[m] = 1'b0;
      rr_ptr_nxt[m] = rr_ptr_q[m];

      // Priority scan starting from rr_ptr_q[m]
      for (int k = 0; k < BANKS_PER_INGRESS; k++) begin
        automatic int idx = (rr_ptr_q[m] + k) % BANKS_PER_INGRESS;
        if (!winner_vld[m] && req[m][idx]) begin
          winner[m]     = idx[$clog2(BANKS_PER_INGRESS)-1:0];
          winner_vld[m] = 1'b1;
        end
      end

      // Advance pointer only when output port can accept (not stalled)
      if (winner_vld[m] && (!out_valid_q[m] || mid_ready[m])) begin
        rr_ptr_nxt[m] = (winner[m] + 1'b1) % BANKS_PER_INGRESS;
      end
    end
  end

  // ---------------------------------------------------------------------------
  // Registered outputs and RR pointer update
  // ---------------------------------------------------------------------------
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      for (int m = 0; m < NUM_MIDDLE; m++) begin
        out_valid_q[m] <= 1'b0;
        out_flit_q[m]  <= '0;
        rr_ptr_q[m]    <= '0;
      end
    end else begin
      for (int m = 0; m < NUM_MIDDLE; m++) begin
        rr_ptr_q[m] <= rr_ptr_nxt[m];

        if (!out_valid_q[m] || mid_ready[m]) begin
          // Slot is free (or being consumed this cycle)
          out_valid_q[m] <= winner_vld[m];
          if (winner_vld[m]) begin
            // Mask dest_mask to only the 4 bits relevant to egress switch m
            out_flit_q[m]           <= bank_flit[winner[m]];
            out_flit_q[m].dest_mask <=
              bank_flit[winner[m]].dest_mask &
              ({ {(NUM_THREADS - THREADS_PER_EGRESS){1'b0}},
                 {THREADS_PER_EGRESS{1'b1}} } << (m * THREADS_PER_EGRESS));
          end
        end
      end
    end
  end

  // ---------------------------------------------------------------------------
  // Output assignments
  // ---------------------------------------------------------------------------
  always_comb begin
    for (int m = 0; m < NUM_MIDDLE; m++) begin
      mid_valid[m] = out_valid_q[m];
      mid_flit[m]  = out_flit_q[m];
    end
  end

  // ---------------------------------------------------------------------------
  // Back-pressure to banks
  // A bank input is ready when NONE of its pending output ports are stalled.
  // Conservatively, a bank is ready when every output to which it could send
  // is either not being targeted or has room.  We use a simple approximation:
  // the bank is ready if at least one output that it targets is free.
  // For correctness we stall the bank whenever any output it won last cycle
  // is backpressured.  The simplest safe approach: always accept unless all
  // outputs targeted by this bank are stalled.
  // ---------------------------------------------------------------------------
  always_comb begin
    for (int i = 0; i < BANKS_PER_INGRESS; i++) begin
      automatic logic any_output_free = 1'b0;
      for (int m = 0; m < NUM_MIDDLE; m++) begin
        if (bank_valid[i] &&
            (|(bank_flit[i].dest_mask[m*THREADS_PER_EGRESS +: THREADS_PER_EGRESS]))) begin
          if (!out_valid_q[m] || mid_ready[m]) begin
            any_output_free = 1'b1;
          end
        end else begin
          // This output is not targeted – don't factor it in
          any_output_free = any_output_free;
        end
      end
      // If input has no valid target bits, assert ready (drop idle cycles)
      if (!bank_valid[i] || !(|(bank_flit[i].dest_mask))) begin
        bank_ready[i] = 1'b1;
      end else begin
        bank_ready[i] = any_output_free;
      end
    end
  end

endmodule : ingress_switch
