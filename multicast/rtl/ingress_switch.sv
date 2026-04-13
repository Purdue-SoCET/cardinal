// ingress_switch.sv
// 3-stage Clos network – ingress switch (4 inputs × 8 outputs).
//
// Diagonal routing: ingress s sends egress group e via middle switch
//   m = (s + e) & (NUM_MIDDLE - 1)
//
// For each middle output port m, the egress group it serves is:
//   e_m = (m - SWITCH_ID + NUM_MIDDLE) & (NUM_MIDDLE - 1)
//       = (m + NUM_MIDDLE - SWITCH_ID) & (NUM_MIDDLE - 1)
//
// Since NUM_MIDDLE and THREADS_PER_EGRESS are powers of 2, all index
// arithmetic uses bitwise AND and shifts — no modulus or multiply.
// With genvar + localparam the egress-group bit range for each output
// port collapses to a compile-time constant, so the part-select is pure
// wiring with zero logic gates.
//
// Arbitration: the arbiter above guarantees at most one bank per ingress
// targets any given egress group per cycle, so no arbitration is needed here.
//
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
  // Output registers — one per middle switch output port
  // ---------------------------------------------------------------------------
  logic  out_valid_q [NUM_MIDDLE];
  flit_t out_flit_q  [NUM_MIDDLE];

  // ---------------------------------------------------------------------------
  // Combinational routing + registered outputs — one generate block per
  // middle output port m.
  //
  // For port m:
  //   E_M    = egress group served  (compile-time constant)
  //   GRP_LO = LSB of that group's bits in dest_mask (compile-time constant)
  //
  // The part-select [GRP_LO +: THREADS_PER_EGRESS] is therefore a fixed wire
  // slice — the synthesiser sees it as simple bit selection, no logic.
  // ---------------------------------------------------------------------------
  generate
    for (genvar m = 0; m < NUM_MIDDLE; m++) begin : gen_mid_port

      localparam int unsigned E_M    = (m + NUM_MIDDLE - SWITCH_ID) & (NUM_MIDDLE - 1);
      localparam int unsigned GRP_LO = E_M << $clog2(THREADS_PER_EGRESS);

      // -- Combinational: find which bank (if any) targets this port ----------
      logic  in_valid;
      flit_t in_flit;

      always_comb begin
        in_valid = 1'b0;
        in_flit  = '0;
        for (int i = 0; i < BANKS_PER_INGRESS; i++) begin
          if (bank_valid[i] && |bank_flit[i].dest_mask[GRP_LO +: THREADS_PER_EGRESS]) begin
            in_valid                                          = 1'b1;
            in_flit                                           = bank_flit[i];
            in_flit.dest_mask                                 = '0;
            in_flit.dest_mask[GRP_LO +: THREADS_PER_EGRESS]  =
                bank_flit[i].dest_mask[GRP_LO +: THREADS_PER_EGRESS];
          end
        end
      end

      // -- Pipeline register --------------------------------------------------
      always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
          out_valid_q[m] <= 1'b0;
          out_flit_q[m]  <= '0;
        end else if (!out_valid_q[m] || mid_ready[m]) begin
          out_valid_q[m] <= in_valid;
          if (in_valid)
            out_flit_q[m] <= in_flit;
        end
      end

      // -- Output assignment --------------------------------------------------
      assign mid_valid[m] = out_valid_q[m];
      assign mid_flit[m]  = out_flit_q[m];

    end
  endgenerate

  // ---------------------------------------------------------------------------
  // Back-pressure: bank i is ready when every middle port it targets is free.
  // Each bank can span multiple egress groups (multicast), so we check all 8.
  // ---------------------------------------------------------------------------
  generate
    for (genvar i = 0; i < BANKS_PER_INGRESS; i++) begin : gen_bank_ready

      always_comb begin
        bank_ready[i] = 1'b1;
        for (int m = 0; m < NUM_MIDDLE; m++) begin
          // E_M and GRP_LO are functions of the loop variable m and the
          // compile-time SWITCH_ID — synthesised as constant selectors.
          automatic int unsigned e_m    = (m + NUM_MIDDLE - SWITCH_ID) & (NUM_MIDDLE - 1);
          automatic int unsigned grp_lo = e_m << $clog2(THREADS_PER_EGRESS);
          if (bank_valid[i] && |bank_flit[i].dest_mask[grp_lo +: THREADS_PER_EGRESS])
            if (out_valid_q[m] && !mid_ready[m])
              bank_ready[i] = 1'b0;
        end
      end

    end
  endgenerate

endmodule : ingress_switch
