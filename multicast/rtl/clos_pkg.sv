// clos_pkg.sv
// Package containing all parameters and type definitions for the Clos network.

package clos_pkg;

  // ---------------------------------------------------------------------------
  // Flit field widths
  // ---------------------------------------------------------------------------
  parameter int unsigned FLIT_W   = 66;   // total flit width [65:0]
  parameter int unsigned DEST_W   = 32;   // destination bitmask [65:34]
  parameter int unsigned DATA_W   = 32;   // read-data           [33: 2]
  parameter int unsigned ERR_W    = 2;    // error-code          [ 1: 0]

  // ---------------------------------------------------------------------------
  // Network sizing
  // ---------------------------------------------------------------------------
  parameter int unsigned NUM_BANKS          = 32;
  parameter int unsigned NUM_THREADS        = 32;
  parameter int unsigned NUM_INGRESS        = 8;
  parameter int unsigned NUM_MIDDLE         = 8;
  parameter int unsigned NUM_EGRESS         = 8;
  parameter int unsigned BANKS_PER_INGRESS  = 4;   // inputs  per ingress switch
  parameter int unsigned THREADS_PER_EGRESS = 4;   // outputs per egress  switch

  // ---------------------------------------------------------------------------
  // Flit layout
  //   [65:34] dest_mask  (DEST_W = 32 bits)
  //   [33: 2] data       (DATA_W = 32 bits)
  //   [ 1: 0] error      (ERR_W  =  2 bits)
  // ---------------------------------------------------------------------------
  typedef struct packed {
    logic [DEST_W-1:0] dest_mask;   // [65:34]
    logic [DATA_W-1:0] data;        // [33: 2]
    logic [ERR_W-1:0]  error;       // [ 1: 0]
  } flit_t;                         // 66 bits total

  // Thread-facing word: dest stripped → flit[33:0] = {data[31:0], error[1:0]}
  parameter int unsigned THREAD_FLIT_W = 34;   // DATA_W + ERR_W

endpackage : clos_pkg
