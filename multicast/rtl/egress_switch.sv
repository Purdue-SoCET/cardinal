// egress_switch.sv
// 3-stage Clos network – egress switch (8 inputs × 4 thread outputs).
//
// Egress switch SWITCH_ID serves threads [BASE_THREAD +: 4].
// Arbitration: round-robin across 8 middle-switch inputs selects a winner
// flit each cycle.  The winner is latched into an output register; from there
// the flit fans out to all four thread outputs simultaneously wherever the
// corresponding dest_mask bit is set (multicast within the group).
//
// thread_rx_flit output: [38:0] = flit[38:0] (dest field stripped).
// Registered outputs.

`timescale 1ns/1ps

import clos_pkg::*;

module egress_switch #(
  parameter int unsigned SWITCH_ID   = 0,               // 0-7
  parameter int unsigned BASE_THREAD = SWITCH_ID * THREADS_PER_EGRESS  // first thread index
) (
  input  logic clk,
  input  logic rst_n,

  // ---- middle-switch inputs (8 ports) --------------------------------------
  input  logic  mid_valid [NUM_MIDDLE],
  output logic  mid_ready [NUM_MIDDLE],
  input  flit_t mid_flit  [NUM_MIDDLE],

  // ---- thread outputs (4 ports) -------------------------------------------
  output logic                        thr_valid [THREADS_PER_EGRESS],
  input  logic                        thr_ready [THREADS_PER_EGRESS],
  output logic [THREAD_FLIT_W-1:0]    thr_flit  [THREADS_PER_EGRESS]
);

  // ---------------------------------------------------------------------------
  // Output register (holds the arbitration winner)
  // ---------------------------------------------------------------------------
  logic  out_valid_q;
  flit_t out_flit_q;

  // Round-robin pointer
  logic [$clog2(NUM_MIDDLE)-1:0] rr_ptr_q;

  // ---------------------------------------------------------------------------
  // Per-thread valid derived from registered flit
  // A thread output is valid when the stored flit targets that thread.
  // ---------------------------------------------------------------------------
  // We track which thread outputs have been serviced (consumed) so we can
  // retire the flit only after all targeted threads accept it.
  // pending_q[i] = 1 means thread i still needs this flit.
  logic [THREADS_PER_EGRESS-1:0] pending_q;

  // ---------------------------------------------------------------------------
  // Combinational: arbitration
  // ---------------------------------------------------------------------------
  logic [$clog2(NUM_MIDDLE)-1:0] winner;
  logic                           winner_vld;
  logic [$clog2(NUM_MIDDLE)-1:0] rr_ptr_nxt;

  // Which pending bits will remain after this clock edge?
  logic [THREADS_PER_EGRESS-1:0] pending_nxt;
  logic                           all_served;    // all targets accepted

  always_comb begin
    // Compute which threads have consumed their copy this cycle
    for (int t = 0; t < THREADS_PER_EGRESS; t++) begin
      if (pending_q[t] && thr_ready[t]) begin
        pending_nxt[t] = 1'b0;   // consumed
      end else begin
        pending_nxt[t] = pending_q[t];
      end
    end

    all_served = (pending_nxt == '0);

    // Arbitrate for next flit only when current slot will be free next cycle
    winner     = '0;
    winner_vld = 1'b0;
    rr_ptr_nxt = rr_ptr_q;

    if (!out_valid_q || all_served) begin
      for (int k = 0; k < NUM_MIDDLE; k++) begin
        automatic int idx = (rr_ptr_q + k) % NUM_MIDDLE;
        if (!winner_vld && mid_valid[idx]) begin
          winner     = idx[$clog2(NUM_MIDDLE)-1:0];
          winner_vld = 1'b1;
        end
      end
      if (winner_vld) begin
        rr_ptr_nxt = (winner + 1'b1) % NUM_MIDDLE;
      end
    end
  end

  // ---------------------------------------------------------------------------
  // Registered output
  // ---------------------------------------------------------------------------
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      out_valid_q <= 1'b0;
      out_flit_q  <= '0;
      pending_q   <= '0;
      rr_ptr_q    <= '0;
    end else begin
      rr_ptr_q <= rr_ptr_nxt;

      // Update pending bits (consume acknowledged threads)
      if (out_valid_q) begin
        if (all_served) begin
          // All targets served; slot becomes free – load next if available
          out_valid_q <= winner_vld;
          if (winner_vld) begin
            out_flit_q  <= mid_flit[winner];
            // Compute pending mask for new flit: bits [BASE_THREAD +: 4]
            for (int t = 0; t < THREADS_PER_EGRESS; t++) begin
              pending_q[t] <= mid_flit[winner].dest_mask[BASE_THREAD + t];
            end
          end else begin
            pending_q <= '0;
          end
        end else begin
          // Still waiting for some threads
          pending_q <= pending_nxt;
        end
      end else begin
        // Slot was empty; load winner if available
        out_valid_q <= winner_vld;
        if (winner_vld) begin
          out_flit_q  <= mid_flit[winner];
          for (int t = 0; t < THREADS_PER_EGRESS; t++) begin
            pending_q[t] <= mid_flit[winner].dest_mask[BASE_THREAD + t];
          end
        end else begin
          pending_q <= '0;
        end
      end
    end
  end

  // ---------------------------------------------------------------------------
  // Thread output assignments
  // thr_flit[t] = flit[38:0]  (dest field stripped)
  // ---------------------------------------------------------------------------
  always_comb begin
    for (int t = 0; t < THREADS_PER_EGRESS; t++) begin
      thr_valid[t] = out_valid_q && pending_q[t];
      thr_flit[t]  = out_flit_q[THREAD_FLIT_W-1:0];
    end
  end

  // ---------------------------------------------------------------------------
  // Back-pressure to middle switches
  // Accept a new flit only when the current slot is free (or becoming free).
  // The winning input is consumed; stall others.
  // ---------------------------------------------------------------------------
  always_comb begin
    for (int m = 0; m < NUM_MIDDLE; m++) begin
      mid_ready[m] = (!out_valid_q || all_served) &&
                     winner_vld &&
                     (winner == m[$clog2(NUM_MIDDLE)-1:0]);
    end
  end

endmodule : egress_switch
