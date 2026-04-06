// clos_network.sv
// Top-level 3-stage Clos network: 32 SRAM banks → 32 threads.
//
// Topology
//   8 ingress switches  (4 bank inputs  × 8 middle outputs each)
//   8 middle  switches  (8 ingress inputs × 8 egress outputs, one active)
//   8 egress  switches  (8 middle inputs × 4 thread outputs each)
//
// Bank b → ingress switch  (b / BANKS_PER_INGRESS)  port (b % BANKS_PER_INGRESS)
// Thread t ← egress switch (t / THREADS_PER_EGRESS) port (t % THREADS_PER_EGRESS)
// Ingress i → middle m via wire ing_mid_valid[i][m] / ing_mid_flit[i][m]
// Middle  m → egress  e only when e == m  (direct vertical routing)

`timescale 1ns/1ps

import clos_pkg::*;

module clos_network (
  input  logic clk,
  input  logic rst_n,

  // ---- SRAM bank inputs (32 banks) -----------------------------------------
  input  logic              bank_valid [NUM_BANKS],
  output logic              bank_ready [NUM_BANKS],
  input  flit_t             bank_flit  [NUM_BANKS],

  // ---- Thread outputs (32 threads) -----------------------------------------
  output logic                     thread_valid [NUM_THREADS],
  input  logic                     thread_ready [NUM_THREADS],
  output logic [THREAD_FLIT_W-1:0] thread_flit  [NUM_THREADS]
);

  // ---------------------------------------------------------------------------
  // Ingress ↔ Middle interconnect wires
  //   ing_mid_*[i][m] : ingress i → middle m
  // ---------------------------------------------------------------------------
  logic  ing_mid_valid [NUM_INGRESS][NUM_MIDDLE];
  logic  ing_mid_ready [NUM_INGRESS][NUM_MIDDLE];
  flit_t ing_mid_flit  [NUM_INGRESS][NUM_MIDDLE];

  // ---------------------------------------------------------------------------
  // Middle ↔ Egress interconnect wires
  //   mid_egr_*[m][e] : middle m → egress e
  // ---------------------------------------------------------------------------
  logic  mid_egr_valid [NUM_MIDDLE][NUM_EGRESS];
  logic  mid_egr_ready [NUM_MIDDLE][NUM_EGRESS];
  flit_t mid_egr_flit  [NUM_MIDDLE][NUM_EGRESS];

  // ---------------------------------------------------------------------------
  // Ingress switch bank port slice wires
  // ---------------------------------------------------------------------------
  logic  ing_bank_valid [NUM_INGRESS][BANKS_PER_INGRESS];
  logic  ing_bank_ready [NUM_INGRESS][BANKS_PER_INGRESS];
  flit_t ing_bank_flit  [NUM_INGRESS][BANKS_PER_INGRESS];

  // ---------------------------------------------------------------------------
  // Egress switch thread port slice wires
  // ---------------------------------------------------------------------------
  logic                     egr_thr_valid [NUM_EGRESS][THREADS_PER_EGRESS];
  logic                     egr_thr_ready [NUM_EGRESS][THREADS_PER_EGRESS];
  logic [THREAD_FLIT_W-1:0] egr_thr_flit  [NUM_EGRESS][THREADS_PER_EGRESS];

  // ---------------------------------------------------------------------------
  // Bank → ingress fanout
  // ---------------------------------------------------------------------------
  always_comb begin
    for (int b = 0; b < NUM_BANKS; b++) begin
      automatic int s = b / BANKS_PER_INGRESS;
      automatic int p = b % BANKS_PER_INGRESS;
      ing_bank_valid[s][p] = bank_valid[b];
      bank_ready[b]        = ing_bank_ready[s][p];
      ing_bank_flit[s][p]  = bank_flit[b];
    end
  end

  // ---------------------------------------------------------------------------
  // Egress → thread fanout
  // ---------------------------------------------------------------------------
  always_comb begin
    for (int t = 0; t < NUM_THREADS; t++) begin
      automatic int s = t / THREADS_PER_EGRESS;
      automatic int p = t % THREADS_PER_EGRESS;
      thread_valid[t]      = egr_thr_valid[s][p];
      egr_thr_ready[s][p]  = thread_ready[t];
      thread_flit[t]       = egr_thr_flit[s][p];
    end
  end

  // ---------------------------------------------------------------------------
  // Ingress switch instances (8)
  // ---------------------------------------------------------------------------
  generate
    for (genvar i = 0; i < NUM_INGRESS; i++) begin : gen_ingress
      ingress_switch #(
        .SWITCH_ID (i)
      ) u_ing (
        .clk        (clk),
        .rst_n      (rst_n),
        .bank_valid (ing_bank_valid[i]),
        .bank_ready (ing_bank_ready[i]),
        .bank_flit  (ing_bank_flit[i]),
        .mid_valid  (ing_mid_valid[i]),
        .mid_ready  (ing_mid_ready[i]),
        .mid_flit   (ing_mid_flit[i])
      );
    end
  endgenerate

  // ---------------------------------------------------------------------------
  // Middle switch instances (8)
  // Each middle switch m collects one output from each of the 8 ingress
  // switches (ing_mid_*[i][m]) and drives one output to egress switch m.
  // ---------------------------------------------------------------------------
  generate
    for (genvar m = 0; m < NUM_MIDDLE; m++) begin : gen_middle

      // Flatten per-ingress port arrays for middle switch port connections
      logic  mid_ing_valid_flat [NUM_INGRESS];
      logic  mid_ing_ready_flat [NUM_INGRESS];
      flit_t mid_ing_flit_flat  [NUM_INGRESS];

      always_comb begin
        for (int i = 0; i < NUM_INGRESS; i++) begin
          mid_ing_valid_flat[i]   = ing_mid_valid[i][m];
          ing_mid_ready[i][m]     = mid_ing_ready_flat[i];
          mid_ing_flit_flat[i]    = ing_mid_flit[i][m];
        end
      end

      middle_switch #(
        .SWITCH_ID (m)
      ) u_mid (
        .clk       (clk),
        .rst_n     (rst_n),
        .ing_valid (mid_ing_valid_flat),
        .ing_ready (mid_ing_ready_flat),
        .ing_flit  (mid_ing_flit_flat),
        .egr_valid (mid_egr_valid[m]),
        .egr_ready (mid_egr_ready[m]),
        .egr_flit  (mid_egr_flit[m])
      );
    end
  endgenerate

  // ---------------------------------------------------------------------------
  // Egress switch instances (8)
  // Each egress switch e collects the output from middle switch m==e.
  // ---------------------------------------------------------------------------
  generate
    for (genvar e = 0; e < NUM_EGRESS; e++) begin : gen_egress

      // Flatten per-middle port arrays for egress switch port connections
      logic  egr_mid_valid_flat [NUM_MIDDLE];
      logic  egr_mid_ready_flat [NUM_MIDDLE];
      flit_t egr_mid_flit_flat  [NUM_MIDDLE];

      always_comb begin
        for (int m = 0; m < NUM_MIDDLE; m++) begin
          egr_mid_valid_flat[m]  = mid_egr_valid[m][e];
          mid_egr_ready[m][e]    = egr_mid_ready_flat[m];
          egr_mid_flit_flat[m]   = mid_egr_flit[m][e];
        end
      end

      egress_switch #(
        .SWITCH_ID   (e),
        .BASE_THREAD (e * THREADS_PER_EGRESS)
      ) u_egr (
        .clk       (clk),
        .rst_n     (rst_n),
        .mid_valid (egr_mid_valid_flat),
        .mid_ready (egr_mid_ready_flat),
        .mid_flit  (egr_mid_flit_flat),
        .thr_valid (egr_thr_valid[e]),
        .thr_ready (egr_thr_ready[e]),
        .thr_flit  (egr_thr_flit[e])
      );
    end
  endgenerate

endmodule : clos_network
