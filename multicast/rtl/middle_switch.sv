// middle_switch.sv
// 3-stage Clos network – middle switch (8 inputs × 8 outputs).
//
// Middle switch SWITCH_ID forwards flits exclusively to egress switch
// SWITCH_ID (direct vertical routing).  All 8 ingress switch inputs
// arbitrate via round-robin for the single output towards egress[SWITCH_ID].
// The remaining 7 output ports are unused/tied off; wiring is 1-to-1 in the
// Clos sense but the spec says "routes to egress switch SWITCH_ID", so the
// middle switch has one active output.
//
// For a general non-blocking Clos build-out where each middle switch m fans
// to all 8 egress switches, the spec here constrains: middle switch m only
// feeds egress m.  This matches the 8×8 fully-connected middle plane where
// ingress i picks middle m to reach egress m.
//
// Registered output, round-robin arbitration.

`timescale 1ns/1ps

import clos_pkg::*;

module middle_switch #(
  parameter int unsigned SWITCH_ID = 0   // 0-7
) (
  input  logic clk,
  input  logic rst_n,

  // ---- ingress-switch inputs (8 ports, one from each ingress switch) -------
  input  logic  ing_valid [NUM_INGRESS],
  output logic  ing_ready [NUM_INGRESS],
  input  flit_t ing_flit  [NUM_INGRESS],

  // ---- egress-switch outputs (8 ports, only port SWITCH_ID is active) ------
  output logic  egr_valid [NUM_EGRESS],
  input  logic  egr_ready [NUM_EGRESS],
  output flit_t egr_flit  [NUM_EGRESS]
);

  // ---------------------------------------------------------------------------
  // Output register for the single active output (egress[SWITCH_ID])
  // ---------------------------------------------------------------------------
  logic  out_valid_q;
  flit_t out_flit_q;

  // Round-robin arbitration pointer (across NUM_INGRESS=8 inputs)
  logic [$clog2(NUM_INGRESS)-1:0] rr_ptr_q;

  // ---------------------------------------------------------------------------
  // Combinational arbitration
  // ---------------------------------------------------------------------------
  logic [$clog2(NUM_INGRESS)-1:0] winner;
  logic                            winner_vld;
  logic [$clog2(NUM_INGRESS)-1:0] rr_ptr_nxt;

  always_comb begin
    winner     = '0;
    winner_vld = 1'b0;
    rr_ptr_nxt = rr_ptr_q;

    for (int k = 0; k < NUM_INGRESS; k++) begin
      automatic int idx = (rr_ptr_q + k) % NUM_INGRESS;
      if (!winner_vld && ing_valid[idx]) begin
        winner     = idx[$clog2(NUM_INGRESS)-1:0];
        winner_vld = 1'b1;
      end
    end

    // Advance pointer when the output slot is free or being consumed
    if (winner_vld && (!out_valid_q || egr_ready[SWITCH_ID])) begin
      rr_ptr_nxt = (winner + 1'b1) % NUM_INGRESS;
    end
  end

  // ---------------------------------------------------------------------------
  // Registered output
  // ---------------------------------------------------------------------------
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      out_valid_q <= 1'b0;
      out_flit_q  <= '0;
      rr_ptr_q    <= '0;
    end else begin
      rr_ptr_q <= rr_ptr_nxt;

      if (!out_valid_q || egr_ready[SWITCH_ID]) begin
        out_valid_q <= winner_vld;
        if (winner_vld) begin
          out_flit_q <= ing_flit[winner];
        end
      end
    end
  end

  // ---------------------------------------------------------------------------
  // Output tie-off: only port SWITCH_ID carries traffic
  // ---------------------------------------------------------------------------
  always_comb begin
    for (int e = 0; e < NUM_EGRESS; e++) begin
      if (e == SWITCH_ID) begin
        egr_valid[e] = out_valid_q;
        egr_flit[e]  = out_flit_q;
      end else begin
        egr_valid[e] = 1'b0;
        egr_flit[e]  = '0;
      end
    end
  end

  // ---------------------------------------------------------------------------
  // Back-pressure to ingress switches
  // All inputs are ready when the single output slot is free (or consuming).
  // The winning input is consumed; losers can be accepted next cycle.
  // We stall all inputs while the output is full and not being consumed.
  // ---------------------------------------------------------------------------
  always_comb begin
    automatic logic slot_free = !out_valid_q || egr_ready[SWITCH_ID];
    for (int i = 0; i < NUM_INGRESS; i++) begin
      ing_ready[i] = slot_free;
    end
  end

endmodule : middle_switch
